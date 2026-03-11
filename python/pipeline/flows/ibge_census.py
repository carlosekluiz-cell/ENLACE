"""IBGE Census pipeline — municipalities, states, boundaries, population.

Downloads ALL ~5,570 municipalities and 27 states from IBGE REST APIs.
This pipeline MUST run before all others since it populates admin_level_1
and admin_level_2 tables that other pipelines reference.

Sources:
  - Municipalities: GET /api/v1/localidades/municipios
  - States: GET /api/v1/localidades/estados
  - Boundaries: GET /api/v3/malhas/estados/{UF}?formato=application/vnd.geo+json
  - Population: GET /api/v3/agregados/4714/periodos/2022/variaveis/93?localidades=N6[all]
"""
import json
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs, STATE_ABBREVIATIONS
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


class IBGECensusPipeline(BasePipeline):
    """Load all Brazilian municipalities, states, boundaries, and census population."""

    def __init__(self):
        super().__init__("ibge_census")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        # Re-run if we have fewer than 5000 municipalities (seed only has ~45)
        return count < 5000

    def download(self) -> dict:
        """Download municipalities, states, and population from IBGE APIs."""
        with PipelineHTTPClient(timeout=120) as http:
            logger.info("Fetching all municipalities from IBGE...")
            municipalities = http.get_json(self.urls.ibge_municipalities)
            logger.info(f"Got {len(municipalities)} municipalities")

            logger.info("Fetching all states from IBGE...")
            states = http.get_json(self.urls.ibge_states)
            logger.info(f"Got {len(states)} states")

            # Fetch state boundaries as GeoJSON
            logger.info("Fetching state boundaries...")
            state_boundaries = {}
            for state in states:
                uf_id = str(state["id"])
                try:
                    url = self.urls.ibge_state_boundaries.format(uf=uf_id)
                    geojson = http.get_json(url)
                    state_boundaries[uf_id] = geojson
                except Exception as e:
                    logger.warning(f"Could not fetch boundary for state {uf_id}: {e}")

            # Fetch census 2022 population by municipality
            logger.info("Fetching census 2022 population data...")
            try:
                pop_data = http.get_json(self.urls.ibge_census_population)
            except Exception as e:
                logger.warning(f"Could not fetch population data: {e}")
                pop_data = []

        return {
            "municipalities": municipalities,
            "states": states,
            "state_boundaries": state_boundaries,
            "population": pop_data,
        }

    def validate_raw(self, data: dict) -> None:
        if not data["municipalities"]:
            raise ValueError("No municipalities returned from IBGE API")
        if not data["states"]:
            raise ValueError("No states returned from IBGE API")
        if len(data["municipalities"]) < 5000:
            raise ValueError(
                f"Expected ~5,570 municipalities, got {len(data['municipalities'])}"
            )
        logger.info(
            f"Raw data: {len(data['municipalities'])} municipalities, "
            f"{len(data['states'])} states, "
            f"{len(data['population'])} population records"
        )

    def transform(self, raw_data: dict) -> dict:
        """Transform IBGE API responses into database-ready format."""
        # Build population lookup: municipality code -> population
        pop_lookup = {}
        for record in raw_data["population"]:
            # Flat view: each record has localidade (code), and V (value)
            mun_code = record.get("localidade", record.get("D3C", ""))
            value = record.get("V", record.get("valor", "0"))
            try:
                pop_lookup[str(mun_code)] = int(value)
            except (ValueError, TypeError):
                pass

        # Transform states
        states_rows = []
        for s in raw_data["states"]:
            uf_id = str(s["id"])
            boundary_geojson = raw_data["state_boundaries"].get(uf_id)
            geom_json = None
            if boundary_geojson:
                features = boundary_geojson.get("features", [])
                if features:
                    geom_json = json.dumps(features[0].get("geometry", {}))

            states_rows.append({
                "code": uf_id,
                "name": s["nome"],
                "abbreviation": STATE_ABBREVIATIONS.get(uf_id, s["sigla"]),
                "country_code": "BR",
                "geom_json": geom_json,
            })

        # Transform municipalities
        mun_rows = []
        for m in raw_data["municipalities"]:
            mun_id = str(m["id"])
            # Extract state code: try microrregiao path, then regiao-imediata,
            # then fall back to first 2 digits of municipality code (IBGE convention)
            try:
                uf_id = str(m["microrregiao"]["mesorregiao"]["UF"]["id"])
            except (TypeError, KeyError):
                try:
                    uf_id = str(m["regiao-imediata"]["regiao-intermediaria"]["UF"]["id"])
                except (TypeError, KeyError):
                    uf_id = mun_id[:2]
                    logger.warning(f"Using code prefix for state of municipality {mun_id} ({m.get('nome', '?')})")
            mun_name = m["nome"]
            population = pop_lookup.get(mun_id, 0)

            mun_rows.append({
                "code": mun_id,
                "name": mun_name,
                "state_code": uf_id,
                "country_code": "BR",
                "population": population,
            })

        self.rows_processed = len(states_rows) + len(mun_rows)
        return {
            "states": pd.DataFrame(states_rows),
            "municipalities": pd.DataFrame(mun_rows),
        }

    def load(self, data: dict) -> None:
        """Upsert states into admin_level_1 and municipalities into admin_level_2."""
        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        # --- Load states into admin_level_1 ---
        states_df = data["states"]
        state_values = []
        for _, row in states_df.iterrows():
            state_values.append((
                row["code"], row["name"], row["country_code"],
            ))

        # Upsert states
        execute_values(cur, """
            INSERT INTO admin_level_1 (code, name, country_code)
            VALUES %s
            ON CONFLICT (code, country_code) DO UPDATE
            SET name = EXCLUDED.name
        """, state_values, page_size=100)
        conn.commit()

        # Update boundaries where we have GeoJSON
        for _, row in states_df.iterrows():
            if row["geom_json"]:
                try:
                    cur.execute("""
                        UPDATE admin_level_1
                        SET geom = ST_Multi(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326))
                        WHERE code = %s AND country_code = 'BR'
                    """, (row["geom_json"], row["code"]))
                except Exception as e:
                    logger.warning(f"Could not set boundary for state {row['code']}: {e}")
                    conn.rollback()
        conn.commit()

        # Build state code -> l1_id map
        cur.execute("SELECT code, id FROM admin_level_1 WHERE country_code = 'BR'")
        state_id_map = {code: l1_id for code, l1_id in cur.fetchall()}

        # --- Load municipalities into admin_level_2 ---
        mun_df = data["municipalities"]
        mun_values = []
        for _, row in mun_df.iterrows():
            l1_id = state_id_map.get(row["state_code"])
            if l1_id is None:
                continue
            mun_values.append((
                row["code"], row["name"], row["country_code"],
                l1_id, row["population"],
            ))

        if mun_values:
            execute_values(cur, """
                INSERT INTO admin_level_2 (code, name, country_code, l1_id, population)
                VALUES %s
                ON CONFLICT (code, country_code) DO UPDATE
                SET name = EXCLUDED.name,
                    l1_id = EXCLUDED.l1_id,
                    population = EXCLUDED.population
            """, mun_values, page_size=1000)
            conn.commit()

        self.rows_inserted = len(state_values) + len(mun_values)
        self.rows_updated = 0
        cur.close()
        conn.close()
        logger.info(
            f"Loaded {len(state_values)} states, {len(mun_values)} municipalities"
        )
