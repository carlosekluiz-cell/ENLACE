"""IBGE Population projections pipeline.

Source: IBGE Agregados API — Tabela 6579 (Estimativas de Populacao)
  + State projections from /api/v1/projecoes/populacao/{UF}
Format: JSON
Update: Annual estimates published mid-year

Strategy:
  1. Fetch municipal population estimates from agregados 6579
  2. Fetch state-level growth rates from projecoes API
  3. Apply state growth rates to municipal base populations for 2025-2035
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs, STATE_ABBREVIATIONS
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)


class IBGEProjectionsPipeline(BasePipeline):
    """Ingest real IBGE population estimates and project forward."""

    def __init__(self):
        super().__init__("ibge_projections")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM population_projections WHERE source = 'ibge_projections'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 5000

    def download(self) -> dict:
        """Download population estimates and state growth projections."""
        with PipelineHTTPClient(timeout=180) as http:
            logger.info("Fetching municipal population estimates from IBGE...")
            estimates = http.get_json(self.urls.ibge_population_estimates)
            logger.info(f"Got {len(estimates)} population estimate records")

            # Fetch state-level growth rates
            logger.info("Fetching state population projections...")
            state_projections = {}
            for uf_code in STATE_ABBREVIATIONS.keys():
                try:
                    url = self.urls.ibge_population_projections.format(uf=uf_code)
                    proj = http.get_json(url)
                    # Extract growth rate from projection data
                    if isinstance(proj, list) and proj:
                        proj = proj[0]
                    pop_data = proj.get("projecao", {}).get("populacao", {})
                    if pop_data:
                        state_projections[uf_code] = pop_data
                except Exception as e:
                    logger.warning(f"Could not fetch projection for state {uf_code}: {e}")

            logger.info(f"Got projections for {len(state_projections)} states")

        return {
            "estimates": estimates,
            "state_projections": state_projections,
        }

    def validate_raw(self, data: dict) -> None:
        if not data["estimates"]:
            raise ValueError("No population estimates returned from IBGE API")

    def transform(self, raw_data: dict) -> pd.DataFrame:
        """Build population projections for 2025-2035."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Build code -> (l2_id, state_code) mapping
        cur.execute("""
            SELECT al2.code, al2.id, al1.code as state_code
            FROM admin_level_2 al2
            JOIN admin_level_1 al1 ON al2.l1_id = al1.id
            WHERE al2.country_code = 'BR'
        """)
        mun_info = {code: (l2_id, state_code) for code, l2_id, state_code in cur.fetchall()}
        cur.close()
        conn.close()

        # Parse base population from estimates
        base_pop = {}
        for record in raw_data["estimates"]:
            mun_code = str(record.get("D3C", record.get("localidade", "")))
            value_str = record.get("V", record.get("valor", ""))
            info = mun_info.get(mun_code)
            if info is None:
                continue
            l2_id, state_code = info
            try:
                population = int(value_str)
            except (ValueError, TypeError):
                continue
            base_pop[l2_id] = (population, state_code)

        # Calculate state-level average annual growth rates from projections
        state_growth = {}
        for uf_code, pop_series in raw_data["state_projections"].items():
            if isinstance(pop_series, dict):
                years = sorted(pop_series.keys())
                if len(years) >= 2:
                    try:
                        first_year = int(years[0])
                        last_year = int(years[-1])
                        first_pop = float(pop_series[years[0]])
                        last_pop = float(pop_series[years[-1]])
                        if first_pop > 0 and last_year > first_year:
                            annual_rate = (last_pop / first_pop) ** (1 / (last_year - first_year)) - 1
                            state_growth[uf_code] = annual_rate
                    except (ValueError, TypeError):
                        pass

        default_growth = 0.007  # 0.7% default if no projection available

        # Project forward
        rows = []
        projection_years = list(range(2025, 2036))
        for l2_id, (population, state_code) in base_pop.items():
            growth_rate = state_growth.get(state_code, default_growth)
            current_pop = population

            for year in projection_years:
                current_pop = int(current_pop * (1 + growth_rate))
                rows.append({
                    "l2_id": l2_id,
                    "year": year,
                    "projected_population": current_pop,
                    "growth_rate": round(growth_rate, 5),
                    "source": "ibge_projections",
                })

        self.rows_processed = len(rows)
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert population projection records."""
        if data.empty:
            logger.warning("No population projections to load")
            return

        columns = ["l2_id", "year", "projected_population", "growth_rate", "source"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="population_projections",
            columns=columns,
            values=values,
            conflict_columns=["l2_id", "year"],
            update_columns=["projected_population", "growth_rate", "source"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} new, updated {updated} population projections")
