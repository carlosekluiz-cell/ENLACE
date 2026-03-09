"""SNIS sanitation infrastructure pipeline.

Source: Sistema Nacional de Informacoes sobre Saneamento (SNIS)
URL: http://apidadosabertos.snis.gov.br/v1/
Format: REST JSON (paginated)
Fields: water coverage %, sewage coverage %, population served

Sanitation infrastructure data is a strong proxy for ISP deployment
potential — municipalities with good water/sewage infrastructure tend
to have easier fiber deployment (existing ducts, utility corridors).
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

SNIS_BASE = "http://apidadosabertos.snis.gov.br/v1"


class SNISSanitationPipeline(BasePipeline):
    """Ingest SNIS sanitation indicators per municipality."""

    def __init__(self):
        super().__init__("snis_sanitation")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        # Create table if not exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sanitation_indicators (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                year INTEGER NOT NULL,
                water_coverage_pct NUMERIC(5,2),
                sewage_coverage_pct NUMERIC(5,2),
                population_served_water INTEGER,
                population_served_sewage INTEGER,
                water_losses_pct NUMERIC(5,2),
                source VARCHAR(100) DEFAULT 'snis',
                UNIQUE(municipality_code, year)
            )
        """)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM sanitation_indicators WHERE source = 'snis'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> list[dict]:
        """Fetch sanitation data from SNIS open data API.

        SNIS provides per-municipality water and sewage indicators.
        We fetch the latest available year's aggregated data.
        """
        with PipelineHTTPClient(timeout=120) as http:
            logger.info("Fetching water indicators from SNIS...")
            all_records = []
            try:
                # SNIS water indicators endpoint
                water_data = http.get_json(
                    f"{SNIS_BASE}/agua/municipios",
                    params={"ano": "2022", "pagina": "1", "quantidade": "5570"},
                )
                if isinstance(water_data, list):
                    all_records.extend(water_data)
                elif isinstance(water_data, dict):
                    items = water_data.get("data", water_data.get("registros", []))
                    if isinstance(items, list):
                        all_records.extend(items)
            except Exception as e:
                logger.warning(f"SNIS water API call failed: {e}")

            if not all_records:
                # Fallback: try SNIS CKAN on dados.gov.br
                logger.info("Trying SNIS via dados.gov.br CKAN...")
                try:
                    url = http.resolve_ckan_resource_url(
                        "snis-serie-historica-agua",
                        resource_format="CSV",
                    )
                    df = http.get_csv(url, sep=";", encoding="latin-1")
                    # Convert DataFrame rows to dicts
                    for _, row in df.head(5570).iterrows():
                        all_records.append(row.to_dict())
                except Exception as e:
                    logger.warning(f"SNIS CKAN fallback failed: {e}")

            if not all_records:
                # Final fallback: use IBGE SIDRA sanitation proxy
                # (PNAD Contínua has water/sewage access questions)
                logger.info("Using IBGE SIDRA sanitation proxy...")
                try:
                    data = http.get_json(
                        "https://servicodados.ibge.gov.br/api/v3/agregados/6691"
                        "/periodos/-1/variaveis/9808"
                        "?localidades=N6[all]&view=flat"
                    )
                    if isinstance(data, list):
                        all_records = data
                except Exception as e:
                    logger.warning(f"IBGE SIDRA sanitation proxy failed: {e}")

            logger.info(f"Fetched {len(all_records)} sanitation records")
            return all_records

    def validate_raw(self, data: list[dict]) -> None:
        if not data:
            raise ValueError("No sanitation data returned from any source")
        logger.info(f"Validating {len(data)} sanitation records")

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Normalize sanitation records into a standard schema."""
        rows = []
        for record in raw_data:
            # Handle multiple possible field names from different sources
            code = str(
                record.get("codigo_municipio", "")
                or record.get("municipio", {}).get("id", "")
                or record.get("localidade", {}).get("id", "")
                or record.get("cod_municipio", "")
            ).strip()

            if not code or len(code) < 6:
                continue

            # Normalize to 7-digit IBGE code
            code = code[:7]

            year = 2022
            for key in ("ano", "referencia", "periodo"):
                val = record.get(key)
                if val:
                    try:
                        year = int(str(val)[:4])
                        break
                    except (ValueError, TypeError):
                        pass

            water_pct = self._extract_numeric(record, [
                "IN055", "atendimento_agua_pct", "cobertura_agua",
                "V", "valor",
            ])
            sewage_pct = self._extract_numeric(record, [
                "IN056", "atendimento_esgoto_pct", "cobertura_esgoto",
            ])
            pop_water = self._extract_numeric(record, [
                "AG001", "populacao_atendida_agua",
            ])
            pop_sewage = self._extract_numeric(record, [
                "ES001", "populacao_atendida_esgoto",
            ])
            losses = self._extract_numeric(record, [
                "IN049", "perdas_distribuicao_pct",
            ])

            rows.append({
                "municipality_code": code,
                "year": year,
                "water_coverage_pct": water_pct,
                "sewage_coverage_pct": sewage_pct,
                "population_served_water": int(pop_water) if pop_water else None,
                "population_served_sewage": int(pop_sewage) if pop_sewage else None,
                "water_losses_pct": losses,
                "source": "snis",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} sanitation records")
        return pd.DataFrame(rows)

    @staticmethod
    def _extract_numeric(record: dict, keys: list[str]):
        """Try multiple field names, return first valid numeric value."""
        for key in keys:
            val = record.get(key)
            if val is not None:
                try:
                    return float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    pass
        return None

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No sanitation data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Resolve l2_id from municipality_code
        loaded = 0
        for _, row in data.iterrows():
            code = row["municipality_code"]
            cur.execute(
                "SELECT id FROM admin_level_2 WHERE code = %s LIMIT 1",
                (code,),
            )
            result = cur.fetchone()
            l2_id = result[0] if result else None

            cur.execute("""
                INSERT INTO sanitation_indicators
                (l2_id, municipality_code, year, water_coverage_pct, sewage_coverage_pct,
                 population_served_water, population_served_sewage, water_losses_pct, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (municipality_code, year) DO UPDATE SET
                    water_coverage_pct = EXCLUDED.water_coverage_pct,
                    sewage_coverage_pct = EXCLUDED.sewage_coverage_pct,
                    population_served_water = EXCLUDED.population_served_water,
                    population_served_sewage = EXCLUDED.population_served_sewage,
                    water_losses_pct = EXCLUDED.water_losses_pct
            """, (
                l2_id, code, row["year"],
                row["water_coverage_pct"], row["sewage_coverage_pct"],
                row["population_served_water"], row["population_served_sewage"],
                row["water_losses_pct"], row["source"],
            ))
            loaded += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} sanitation records")
