"""Anatel quality indicators (IDA) pipeline.

Source: Anatel open data on dados.gov.br (CKAN)
Dataset: "indicadores-de-qualidade"
Format: CSV (semicolon-delimited, ISO-8859-1)
Metrics: IDA metrics mapped to download_speed, upload_speed, latency,
         availability, complaint_rate

Downloads quality indicator CSV, maps IDA metric names to schema types,
and loads per municipality/provider/month.
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# Map Anatel IDA metric names to our schema metric types
IDA_METRIC_MAP = {
    "ida_disponibilidade": "availability_pct",
    "ida_velocidade": "download_speed_mbps",
    "ida_latencia": "latency_ms",
    "ida_jitter": "latency_ms",
    "ida_perda_pacotes": "availability_pct",
    "ida": "availability_pct",
    "velocidade media download": "download_speed_mbps",
    "velocidade media upload": "upload_speed_mbps",
    "latencia media": "latency_ms",
    "disponibilidade": "availability_pct",
    "taxa de reclamacao": "complaint_rate",
}


class AnatelQualityPipeline(BasePipeline):
    """Ingest real Anatel quality indicator data from CKAN."""

    def __init__(self):
        super().__init__("anatel_quality")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM quality_indicators WHERE source = 'anatel_ida'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 1000

    def download(self) -> pd.DataFrame:
        """Download quality indicators CSV from dados.gov.br CKAN."""
        with PipelineHTTPClient(timeout=300) as http:
            logger.info("Resolving Anatel quality CKAN resource URL...")
            csv_url = http.resolve_ckan_resource_url(
                self.urls.anatel_quality_dataset,
                resource_format="CSV",
                ckan_base=self.urls.anatel_ckan_base,
            )
            logger.info(f"Downloading quality CSV from {csv_url}")
            df = http.get_csv(csv_url, sep=";", encoding="iso-8859-1")
            logger.info(f"Downloaded {len(df)} quality records")

        return df

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Empty quality indicators CSV")
        logger.info(f"Quality CSV columns: {list(data.columns)}")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Map IDA metrics to schema and resolve lookups."""
        df = raw_data.copy()
        df.columns = [c.strip() for c in df.columns]

        # Find columns
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "ibge" in cl or "codigo" in cl:
                col_map["ibge_code"] = c
            elif "cnpj" in cl:
                col_map["cnpj"] = c
            elif "ano" in cl:
                col_map["ano"] = c
            elif "mes" in cl or "mês" in cl:
                col_map["mes"] = c
            elif "indicador" in cl or "metrica" in cl or "métrica" in cl:
                col_map["metric"] = c
            elif "valor" in cl or "value" in cl:
                col_map["value"] = c
            elif "resultado" in cl:
                col_map.setdefault("value", c)

        # Build lookups
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_l2 = {code: l2_id for code, l2_id in cur.fetchall()}
        cur.execute("SELECT national_id, id FROM providers WHERE country_code = 'BR'")
        cnpj_to_provider = {nid: pid for nid, pid in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        for _, row in df.iterrows():
            ibge_code = str(row.get(col_map.get("ibge_code", ""), "")).strip()
            l2_id = code_to_l2.get(ibge_code)
            if l2_id is None:
                continue

            cnpj = str(row.get(col_map.get("cnpj", ""), "")).strip()
            provider_id = cnpj_to_provider.get(cnpj)
            if provider_id is None:
                continue

            # Build year_month
            ano = str(row.get(col_map.get("ano", ""), "")).strip()
            mes = str(row.get(col_map.get("mes", ""), "")).strip()
            try:
                year_month = f"{int(ano)}-{int(mes):02d}"
            except (ValueError, TypeError):
                continue

            # Map metric
            metric_raw = str(row.get(col_map.get("metric", ""), "")).strip().lower()
            metric_type = None
            for pattern, mapped in IDA_METRIC_MAP.items():
                if pattern in metric_raw:
                    metric_type = mapped
                    break
            if metric_type is None:
                metric_type = "availability_pct"  # default

            # Parse value
            value_raw = str(row.get(col_map.get("value", ""), "")).strip()
            try:
                value = float(value_raw.replace(",", "."))
            except (ValueError, TypeError):
                continue

            if value < 0:
                continue

            rows.append({
                "l2_id": l2_id,
                "provider_id": provider_id,
                "year_month": year_month,
                "metric_type": metric_type,
                "value": round(value, 2),
                "source": "anatel_ida",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} quality indicators")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Insert quality indicator records."""
        if data.empty:
            logger.warning("No quality indicators to load")
            return

        # Clear existing real data to avoid duplicates on re-run
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM quality_indicators WHERE source = 'anatel_ida'")
        conn.commit()
        cur.close()
        conn.close()

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
