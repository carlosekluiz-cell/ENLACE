"""IBGE Municipal GDP (PIB) pipeline.

Source: IBGE Agregados API — Tabela 5938 (PIB dos Municipios)
URL: https://servicodados.ibge.gov.br/api/v3/agregados/5938/periodos/-1/variaveis/37?localidades=N6[all]&view=flat
Format: JSON (flat view with D3C=municipality code, V=value)
Update: Annual, ~2 year lag
"""
import json
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)


class IBGEPIBPipeline(BasePipeline):
    """Ingest real IBGE municipal GDP data from Agregados API."""

    def __init__(self):
        super().__init__("ibge_pib")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM economic_indicators WHERE source = 'ibge_pib'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 5000

    def download(self) -> dict:
        """Download municipal GDP from IBGE Agregados API."""
        with PipelineHTTPClient(timeout=180) as http:
            logger.info("Fetching municipal GDP from IBGE Agregados API...")
            pib_data = http.get_json(self.urls.ibge_pib_municipal)
            logger.info(f"Got {len(pib_data)} PIB records")

        return {"pib": pib_data}

    def validate_raw(self, data: dict) -> None:
        if not data["pib"]:
            raise ValueError("No PIB data returned from IBGE API")
        if len(data["pib"]) < 5000:
            raise ValueError(f"Expected ~5,570 PIB records, got {len(data['pib'])}")

    def transform(self, raw_data: dict) -> pd.DataFrame:
        """Parse IBGE flat-view response into economic indicator rows."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Build municipality code -> l2_id mapping
        cur.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_l2 = {code: l2_id for code, l2_id in cur.fetchall()}

        # Get population for per-capita calculation
        cur.execute("SELECT id, population FROM admin_level_2 WHERE country_code = 'BR'")
        l2_pop = {l2_id: pop for l2_id, pop in cur.fetchall() if pop}

        cur.close()
        conn.close()

        rows = []
        for record in raw_data["pib"]:
            mun_code = str(record.get("D3C", record.get("localidade", "")))
            value_str = record.get("V", record.get("valor", ""))
            period = record.get("D2C", record.get("periodo", ""))

            l2_id = code_to_l2.get(mun_code)
            if l2_id is None:
                continue

            try:
                pib_value = float(value_str) * 1000  # IBGE reports in R$ thousands
            except (ValueError, TypeError):
                continue

            # Extract year from period
            try:
                year = int(str(period)[:4])
            except (ValueError, TypeError):
                year = 2022

            population = l2_pop.get(l2_id, 0)
            per_capita = round(pib_value / max(population, 1), 2) if population else None

            rows.append({
                "l2_id": l2_id,
                "year": year,
                "pib_municipal_brl": round(pib_value, 2),
                "pib_per_capita_brl": per_capita,
                "source": "ibge_pib",
            })

        self.rows_processed = len(rows)
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert economic indicator records."""
        if data.empty:
            logger.warning("No PIB data to load")
            return

        columns = ["l2_id", "year", "pib_municipal_brl", "pib_per_capita_brl", "source"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="economic_indicators",
            columns=columns,
            values=values,
            conflict_columns=["l2_id", "year"],
            update_columns=["pib_municipal_brl", "pib_per_capita_brl", "source"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} new, updated {updated} economic indicators")
