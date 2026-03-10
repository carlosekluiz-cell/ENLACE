"""Anatel provider registry pipeline.

Source: Anatel open data on dados.gov.br (CKAN)
Dataset: "prestadoras"
Format: CSV (semicolon-delimited, ISO-8859-1)
Columns: CNPJ, Razao Social, Nome Fantasia, Servicos, Situacao

Downloads ALL providers from the registry, normalizes names, and upserts.
"""
import json
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.transformers.provider_normalizer import (
    classify_provider,
    normalize_provider_name,
)

logger = logging.getLogger(__name__)


class AnatelProvidersPipeline(BasePipeline):
    """Ingest real Anatel provider registry from CKAN."""

    def __init__(self):
        super().__init__("anatel_providers")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        return True  # Always re-check provider registry

    def download(self) -> pd.DataFrame:
        """Download provider registry CSV. Tries direct Anatel ZIP first, falls back to CKAN."""
        with PipelineHTTPClient(timeout=300) as http:
            # Try direct ZIP download first (dados.gov.br CKAN is blocked by AWS WAF)
            try:
                logger.info(f"Downloading providers ZIP from {self.urls.anatel_providers_zip}")
                df = http.get_csv_from_zip(
                    self.urls.anatel_providers_zip, sep=";", encoding="iso-8859-1"
                )
                logger.info(f"Downloaded {len(df)} provider records from direct ZIP")
                return df
            except Exception as e:
                logger.warning(f"Direct ZIP download failed: {e}, trying CKAN fallback...")

            # Fallback to CKAN
            logger.info("Resolving Anatel providers CKAN resource URL...")
            csv_url = http.resolve_ckan_resource_url(
                self.urls.anatel_providers_dataset,
                resource_format="CSV",
                ckan_base=self.urls.anatel_ckan_base,
            )
            logger.info(f"Downloading providers CSV from {csv_url}")
            df = http.get_csv(csv_url, sep=";", encoding="iso-8859-1")
            logger.info(f"Downloaded {len(df)} provider records")

        return df

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Empty provider registry CSV")
        logger.info(f"Provider CSV columns: {list(data.columns)}")
        # Check for essential columns (names vary between datasets)
        has_cnpj = any("cnpj" in c.lower() for c in data.columns)
        has_name = any("raz" in c.lower() or "nome" in c.lower() for c in data.columns)
        if not has_cnpj:
            raise ValueError("No CNPJ column found in provider CSV")
        if not has_name:
            raise ValueError("No name column found in provider CSV")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Normalize provider names, extract CNPJ, classify."""
        df = raw_data.copy()
        # Normalize column names to lowercase
        df.columns = [c.strip().lower() for c in df.columns]

        # Find the right columns (Anatel CSVs may vary)
        cnpj_col = next((c for c in df.columns if "cnpj" in c), None)
        name_col = next((c for c in df.columns if "raz" in c), None)
        if name_col is None:
            name_col = next((c for c in df.columns if "nome" in c), None)
        status_col = next((c for c in df.columns if "situa" in c), None)
        services_col = next((c for c in df.columns if "servic" in c or "serviç" in c), None)

        rows = []
        seen_cnpj = set()
        for _, row in df.iterrows():
            cnpj = str(row.get(cnpj_col, "")).strip()
            name = str(row.get(name_col, "")).strip()
            if not cnpj or not name or cnpj == "nan":
                continue
            # Deduplicate by CNPJ
            if cnpj in seen_cnpj:
                continue
            seen_cnpj.add(cnpj)

            status = str(row.get(status_col, "Ativa")).strip() if status_col else "active"
            services = str(row.get(services_col, "")).strip() if services_col else ""

            # Map status
            status_lower = status.lower()
            if "ativa" in status_lower or "ativo" in status_lower:
                db_status = "active"
            elif "cancelad" in status_lower:
                db_status = "inactive"
            else:
                db_status = "active"

            name_normalized = normalize_provider_name(name)

            rows.append({
                "national_id": cnpj,
                "name": name,
                "name_normalized": name_normalized,
                "classification": "PPP",  # Will be reclassified when subscriber data arrives
                "services": json.dumps([s.strip() for s in services.split(",") if s.strip()]) if services else "[]",
                "status": db_status,
                "country_code": "BR",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} unique providers")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert provider records by CNPJ (national_id)."""
        if data.empty:
            logger.warning("No providers to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        values = []
        for _, row in data.iterrows():
            values.append((
                row["national_id"], row["name"], row["name_normalized"],
                row["classification"], row["services"],
                row["status"], row["country_code"],
            ))

        execute_values(cur, """
            INSERT INTO providers
            (national_id, name, name_normalized, classification, services, status, country_code)
            VALUES %s
            ON CONFLICT (national_id) DO UPDATE
            SET name = EXCLUDED.name,
                name_normalized = EXCLUDED.name_normalized,
                services = EXCLUDED.services,
                status = EXCLUDED.status,
                updated_at = NOW()
        """, values, page_size=1000)
        conn.commit()

        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Upserted {len(values)} provider records")
