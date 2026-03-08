"""IBGE Municipal GDP (PIB) pipeline.

Source: IBGE Contas Nacionais - PIB dos Municipios
URL: https://www.ibge.gov.br/estatisticas/economicas/contas-nacionais/
     9088-produto-interno-bruto-dos-municipios.html
Format: XLSX/CSV with municipal GDP by sector
Update: Annual, ~2 year lag (2023 data released in 2025)

Real download would fetch the PIB Municipal spreadsheet and extract
GDP, GDP per capita, and sector breakdowns per municipality.
"""
import json
import logging
import random

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# Approximate GDP ranges by region (in BRL thousands)
GDP_RANGES = {
    "SP": (500000, 50000000),
    "RJ": (300000, 30000000),
    "MG": (200000, 10000000),
    "PR": (200000, 8000000),
    "SC": (200000, 6000000),
    "RS": (200000, 8000000),
    "BA": (100000, 5000000),
    "CE": (100000, 3000000),
    "PE": (100000, 4000000),
    "default": (50000, 2000000),
}


class IBGEPIBPipeline(BasePipeline):
    """Ingest IBGE municipal GDP data."""

    def __init__(self):
        super().__init__("ibge_pib")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM economic_indicators")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 50

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real IBGE PIB download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate realistic municipal GDP data."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.code, al2.name, al1.code as state_code
            FROM admin_level_2 al2
            JOIN admin_level_1 al1 ON al2.l1_id = al1.id
            WHERE al2.country_code = 'BR'
        """)
        municipalities = cur.fetchall()

        # Get population data for per-capita calculation
        cur.execute("""
            SELECT ct.l2_id, SUM(cd.total_population) as pop
            FROM census_demographics cd
            JOIN census_tracts ct ON cd.tract_id = ct.id
            GROUP BY ct.l2_id
        """)
        pop_data = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        conn.close()

        random.seed(45)
        rows = []
        years = [2021, 2022, 2023]

        for l2_id, code, mun_name, state_code in municipalities:
            # Get state-appropriate GDP range
            state_abbr = state_code[:2] if len(state_code) >= 2 else "default"
            gdp_range = GDP_RANGES.get(state_abbr, GDP_RANGES["default"])
            base_pib = random.uniform(*gdp_range) * 1000  # Convert to BRL

            population = pop_data.get(l2_id, random.randint(50000, 500000))

            for year in years:
                growth = 1.0 + (year - 2021) * random.uniform(0.02, 0.06)
                pib = round(base_pib * growth, 2)
                per_capita = round(pib / max(population, 1), 2) if population else None
                formal_employment = int(population * random.uniform(0.15, 0.40))

                sector_breakdown = json.dumps({
                    "agropecuaria_pct": round(random.uniform(2, 20), 1),
                    "industria_pct": round(random.uniform(10, 35), 1),
                    "servicos_pct": round(random.uniform(45, 75), 1),
                    "administracao_publica_pct": round(random.uniform(10, 25), 1),
                })

                rows.append({
                    "l2_id": l2_id,
                    "year": year,
                    "pib_municipal_brl": pib,
                    "pib_per_capita_brl": per_capita,
                    "formal_employment": formal_employment,
                    "sector_breakdown": sector_breakdown,
                    "source": "ibge_pib_synthetic",
                })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["l2_id", "year", "pib_municipal_brl"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")
        if (data["pib_municipal_brl"] <= 0).any():
            raise ValueError("Non-positive GDP values found")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Upsert economic indicator records."""
        columns = ["l2_id", "year", "pib_municipal_brl", "pib_per_capita_brl",
                    "formal_employment", "sector_breakdown", "source"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="economic_indicators",
            columns=columns,
            values=values,
            conflict_columns=["l2_id", "year"],
            update_columns=["pib_municipal_brl", "pib_per_capita_brl",
                            "formal_employment", "sector_breakdown", "source"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} new, updated {updated} economic indicators")
