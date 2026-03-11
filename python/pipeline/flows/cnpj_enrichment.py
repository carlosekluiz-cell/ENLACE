"""CNPJ Enrichment Pipeline — provider company details from ReceitaWS.

Source: ReceitaWS free API (https://receitaws.com.br/v1/cnpj/{cnpj})
Rate limit: 3 requests per minute (free tier)
Fields: company status, capital social, founding date, partner count, CNAE, Simples Nacional

Enriches every provider in the providers table with official Receita Federal
company data. Runs incrementally — only queries providers not yet enriched
or with data older than 30 days.
"""
import logging
import time

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

RECEITAWS_URL = "https://receitaws.com.br/v1/cnpj/{cnpj}"
RATE_LIMIT_DELAY = 21  # ~3 req/min → 20s between requests + safety margin


class CNPJEnrichmentPipeline(BasePipeline):
    """Enrich provider records with Receita Federal company details."""

    def __init__(self):
        super().__init__("cnpj_enrichment")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS provider_details (
                id SERIAL PRIMARY KEY,
                provider_id INTEGER NOT NULL REFERENCES providers(id),
                status VARCHAR(50),
                capital_social NUMERIC,
                founding_date DATE,
                address_cep VARCHAR(10),
                address_city VARCHAR(200),
                partner_count INTEGER,
                simples_nacional BOOLEAN,
                cnae_primary VARCHAR(20),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE (provider_id)
            )
        """)
        conn.commit()

        # Check how many providers lack enrichment or have stale data
        cur.execute("""
            SELECT COUNT(*) FROM providers p
            LEFT JOIN provider_details pd ON p.id = pd.provider_id
            WHERE pd.id IS NULL
               OR pd.updated_at < NOW() - INTERVAL '30 days'
        """)
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        logger.info(f"{count} providers need CNPJ enrichment")
        return count > 0

    def download(self) -> pd.DataFrame:
        """Fetch unenriched provider CNPJs and query ReceitaWS."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Get providers needing enrichment (limit batch to avoid hours-long runs)
        cur.execute("""
            SELECT p.id, p.national_id
            FROM providers p
            LEFT JOIN provider_details pd ON p.id = pd.provider_id
            WHERE (pd.id IS NULL OR pd.updated_at < NOW() - INTERVAL '30 days')
              AND p.national_id IS NOT NULL
              AND LENGTH(TRIM(p.national_id)) >= 11
            ORDER BY pd.updated_at ASC NULLS FIRST
            LIMIT 200
        """)
        providers = cur.fetchall()
        cur.close()
        conn.close()

        if not providers:
            logger.info("No providers need enrichment")
            return pd.DataFrame()

        logger.info(f"Querying ReceitaWS for {len(providers)} providers")
        rows = []

        with PipelineHTTPClient(timeout=30) as http:
            for i, (provider_id, cnpj) in enumerate(providers):
                cnpj_clean = cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
                if len(cnpj_clean) < 11:
                    continue

                try:
                    url = RECEITAWS_URL.format(cnpj=cnpj_clean)
                    data = http.get_json(url)

                    if isinstance(data, dict) and data.get("status") != "ERROR":
                        rows.append({
                            "provider_id": provider_id,
                            "status": data.get("situacao", ""),
                            "capital_social": data.get("capital_social", "0"),
                            "founding_date": data.get("abertura", ""),
                            "address_cep": data.get("cep", ""),
                            "address_city": data.get("municipio", ""),
                            "partner_count": len(data.get("qsa", [])),
                            "simples_nacional": data.get("simples", {}).get("optante", False)
                            if isinstance(data.get("simples"), dict) else False,
                            "cnae_primary": data.get("atividade_principal", [{}])[0].get("code", "")
                            if data.get("atividade_principal") else "",
                        })
                    else:
                        logger.debug(f"ReceitaWS error for {cnpj_clean}: {data.get('message', 'unknown')}")

                except Exception as e:
                    logger.warning(f"Failed to query CNPJ {cnpj_clean}: {e}")

                # Rate limit: wait between requests
                if i < len(providers) - 1:
                    time.sleep(RATE_LIMIT_DELAY)

                if (i + 1) % 10 == 0:
                    logger.info(f"Enriched {i + 1}/{len(providers)} providers ({len(rows)} successful)")

        logger.info(f"Downloaded {len(rows)} CNPJ enrichment records")
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        if raw_data.empty:
            return raw_data

        # Parse capital_social to numeric
        if "capital_social" in raw_data.columns:
            raw_data["capital_social"] = pd.to_numeric(
                raw_data["capital_social"].astype(str).str.replace(",", "."),
                errors="coerce",
            ).fillna(0)

        # Parse founding_date
        if "founding_date" in raw_data.columns:
            raw_data["founding_date"] = pd.to_datetime(
                raw_data["founding_date"], format="%d/%m/%Y", errors="coerce"
            )

        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No CNPJ enrichment data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("""
                    INSERT INTO provider_details
                        (provider_id, status, capital_social, founding_date,
                         address_cep, address_city, partner_count,
                         simples_nacional, cnae_primary, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (provider_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        capital_social = EXCLUDED.capital_social,
                        founding_date = EXCLUDED.founding_date,
                        address_cep = EXCLUDED.address_cep,
                        address_city = EXCLUDED.address_city,
                        partner_count = EXCLUDED.partner_count,
                        simples_nacional = EXCLUDED.simples_nacional,
                        cnae_primary = EXCLUDED.cnae_primary,
                        updated_at = NOW()
                """, (
                    int(row["provider_id"]),
                    str(row.get("status", ""))[:50],
                    float(row.get("capital_social", 0)),
                    row.get("founding_date") if pd.notna(row.get("founding_date")) else None,
                    str(row.get("address_cep", ""))[:10],
                    str(row.get("address_city", ""))[:200],
                    int(row.get("partner_count", 0)),
                    bool(row.get("simples_nacional", False)),
                    str(row.get("cnae_primary", ""))[:20],
                ))
                loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load provider {row.get('provider_id')}: {e}")
                conn.rollback()
                continue

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} CNPJ enrichment records")
