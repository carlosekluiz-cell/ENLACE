"""Anatel quality indicators (IDA) pipeline.

Source: Anatel quality data
URL: https://dados.gov.br/dados/conjuntos-dados/indicadores-de-qualidade
Metrics: download_speed_mbps, upload_speed_mbps, latency_ms,
         availability_pct, complaint_rate

Real download would fetch the IDA (Indicador de Desempenho no Atendimento)
and SMP quality reports published quarterly by Anatel.
"""
import logging
import random

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# Realistic quality metric ranges by provider classification
QUALITY_PROFILES = {
    "PGP": {
        "download_speed_mbps": (50, 300),
        "upload_speed_mbps": (10, 100),
        "latency_ms": (8, 30),
        "availability_pct": (95.0, 99.9),
        "complaint_rate": (0.5, 3.0),
    },
    "PMP": {
        "download_speed_mbps": (30, 200),
        "upload_speed_mbps": (5, 50),
        "latency_ms": (12, 45),
        "availability_pct": (92.0, 99.5),
        "complaint_rate": (1.0, 5.0),
    },
    "PPP": {
        "download_speed_mbps": (10, 100),
        "upload_speed_mbps": (2, 30),
        "latency_ms": (15, 60),
        "availability_pct": (88.0, 98.0),
        "complaint_rate": (2.0, 8.0),
    },
}

METRIC_TYPES = [
    "download_speed_mbps",
    "upload_speed_mbps",
    "latency_ms",
    "availability_pct",
    "complaint_rate",
]


class AnatelQualityPipeline(BasePipeline):
    """Ingest Anatel quality indicator data per municipality per provider."""

    def __init__(self):
        super().__init__("anatel_quality")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM quality_indicators")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real Anatel quality data download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate realistic quality metrics per municipality/provider/month."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.name
            FROM admin_level_2 al2
            WHERE al2.country_code = 'BR'
        """)
        municipalities = cur.fetchall()
        cur.execute("SELECT id, name, classification FROM providers WHERE country_code = 'BR'")
        providers = cur.fetchall()
        cur.close()
        conn.close()

        random.seed(44)
        rows = []

        for l2_id, mun_name in municipalities:
            # Each municipality has 2-4 providers with quality data
            num_providers = random.randint(2, min(4, len(providers)))
            mun_providers = random.sample(providers, num_providers)

            for month_offset in range(4):  # Quarterly data: 4 quarters
                year = 2025
                month = (month_offset * 3) + 3  # March, June, Sept, Dec
                ym = f"{year}-{month:02d}"

                for prov_id, prov_name, prov_class in mun_providers:
                    profile = QUALITY_PROFILES.get(prov_class, QUALITY_PROFILES["PPP"])

                    for metric_type in METRIC_TYPES:
                        low, high = profile[metric_type]
                        value = round(random.uniform(low, high), 2)
                        rows.append({
                            "l2_id": l2_id,
                            "provider_id": prov_id,
                            "year_month": ym,
                            "metric_type": metric_type,
                            "value": value,
                            "source": "anatel_ida_synthetic",
                        })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["l2_id", "provider_id", "year_month", "metric_type", "value"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")
        if (data["value"] < 0).any():
            raise ValueError("Negative quality metric values found")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        df = raw_data.copy()
        self.rows_processed = len(df)
        return df

    def load(self, data: pd.DataFrame) -> None:
        """Insert quality indicator records."""
        conn = self._get_connection()
        cur = conn.cursor()
        # Clear existing to avoid duplicates on re-run
        cur.execute("DELETE FROM quality_indicators WHERE source = 'anatel_ida_synthetic'")
        conn.commit()

        columns = ["l2_id", "provider_id", "year_month", "metric_type", "value", "source"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="quality_indicators",
            columns=columns,
            values=values,
            conflict_columns=["id"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} quality indicator records")
