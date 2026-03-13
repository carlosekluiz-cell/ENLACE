"""CNPJ Enrichment Pipeline — provider company details from BrasilAPI.

Source: BrasilAPI (https://brasilapi.com.br/api/cnpj/v1/{cnpj})
Fallback: ReceitaWS free API (https://receitaws.com.br/v1/cnpj/{cnpj})
Fields: company status, capital social, founding date, partner count, CNAE, Simples Nacional

Enriches every provider in the providers table with official Receita Federal
company data. Runs incrementally — only queries providers not yet enriched
or with data older than 30 days.

Also stores QSA (partner/shareholder) data in provider_partners table.
"""
import logging
import time

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
RECEITAWS_URL = "https://receitaws.com.br/v1/cnpj/{cnpj}"
RATE_LIMIT_DELAY = 1  # BrasilAPI is much more permissive


def determine_partner_type(document):
    """Determine if partner is PF or PJ based on document length."""
    if not document:
        return None
    doc_clean = document.strip().replace(".", "").replace("/", "").replace("-", "")
    if len(doc_clean) >= 14:
        return "PJ"
    elif len(doc_clean) >= 11:
        return "PF"
    return None


def parse_entry_date(date_str):
    """Parse entry date (YYYY-MM-DD format)."""
    if not date_str or not isinstance(date_str, str) or len(date_str) < 8:
        return None
    try:
        parts = date_str.split("-")
        if len(parts) == 3:
            return date_str
    except Exception:
        pass
    return None


def extract_qsa_rows(provider_id, qsa_list, source="brasilapi"):
    """Extract partner rows from QSA array.

    Returns list of dicts ready for insertion into provider_partners.
    """
    rows = []
    if not qsa_list:
        return rows

    for partner in qsa_list:
        if not isinstance(partner, dict):
            continue

        if source == "brasilapi":
            partner_name = partner.get("nome_socio", "").strip()
            partner_document = partner.get("cnpj_cpf_do_socio", "").strip() or None
            role_code = str(partner.get("codigo_qualificacao_socio", "")).strip() or None
            role_description = partner.get("qualificacao_socio", "").strip() or None
            entry_date = parse_entry_date(partner.get("data_entrada_sociedade", ""))
            age_range = partner.get("faixa_etaria", "").strip() or None
            legal_rep_name = partner.get("nome_representante_legal", "").strip() or None
            legal_rep_document = partner.get("cpf_representante_legal", "").strip() or None
        elif source == "receitaws":
            partner_name = partner.get("nome", "").strip()
            partner_document = partner.get("qual", "").strip() or None
            # ReceitaWS has different field names and less detail
            role_code = None
            role_description = partner.get("qual", "").strip() or None
            entry_date = None
            age_range = None
            legal_rep_name = None
            legal_rep_document = None
        else:
            continue

        if not partner_name:
            continue

        rows.append({
            "provider_id": provider_id,
            "partner_name": partner_name[:300],
            "partner_document": partner_document,
            "partner_type": determine_partner_type(partner_document),
            "role_code": role_code[:10] if role_code else None,
            "role_description": role_description[:200] if role_description else None,
            "entry_date": entry_date,
            "age_range": age_range[:50] if age_range else None,
            "legal_rep_name": legal_rep_name[:300] if legal_rep_name else None,
            "legal_rep_document": legal_rep_document[:20] if legal_rep_document else None,
        })

    return rows


class CNPJEnrichmentPipeline(BasePipeline):
    """Enrich provider records with Receita Federal company details."""

    def __init__(self):
        super().__init__("cnpj_enrichment")
        self._qsa_rows = []  # Collected QSA partner rows for loading

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS provider_partners (
                id SERIAL PRIMARY KEY,
                provider_id INTEGER NOT NULL REFERENCES providers(id),
                partner_name VARCHAR(300) NOT NULL,
                partner_document VARCHAR(20),
                partner_type VARCHAR(50),
                role_code VARCHAR(10),
                role_description VARCHAR(200),
                entry_date DATE,
                age_range VARCHAR(50),
                legal_rep_name VARCHAR(300),
                legal_rep_document VARCHAR(20),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(provider_id, partner_document)
            );
            CREATE INDEX IF NOT EXISTS idx_provider_partners_provider ON provider_partners(provider_id);
            CREATE INDEX IF NOT EXISTS idx_provider_partners_document ON provider_partners(partner_document);
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
        """Fetch unenriched provider CNPJs and query BrasilAPI/ReceitaWS."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Get providers needing enrichment — prioritize active ISPs (with subscribers)
        cur.execute("""
            SELECT p.id, p.national_id
            FROM providers p
            LEFT JOIN provider_details pd ON p.id = pd.provider_id
            WHERE (pd.id IS NULL OR pd.updated_at < NOW() - INTERVAL '30 days')
              AND p.national_id IS NOT NULL
              AND LENGTH(TRIM(p.national_id)) >= 11
            ORDER BY
                CASE WHEN EXISTS (
                    SELECT 1 FROM broadband_subscribers bs WHERE bs.provider_id = p.id
                ) THEN 0 ELSE 1 END,
                pd.updated_at ASC NULLS FIRST
            LIMIT 500
        """)
        providers = cur.fetchall()
        cur.close()
        conn.close()

        if not providers:
            logger.info("No providers need enrichment")
            return pd.DataFrame()

        logger.info(f"Querying BrasilAPI for {len(providers)} providers")
        rows = []
        self._qsa_rows = []  # Reset QSA collection

        with PipelineHTTPClient(timeout=30) as http:
            for i, (provider_id, cnpj) in enumerate(providers):
                cnpj_clean = cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
                if len(cnpj_clean) < 11:
                    continue

                data = None
                source = None
                try:
                    # Try BrasilAPI first (faster, no strict rate limit)
                    url = BRASILAPI_URL.format(cnpj=cnpj_clean)
                    data = http.get_json(url)
                    source = "brasilapi"
                except Exception:
                    try:
                        # Fallback to ReceitaWS
                        url = RECEITAWS_URL.format(cnpj=cnpj_clean)
                        data = http.get_json(url)
                        source = "receitaws"
                    except Exception as e:
                        logger.warning(f"Failed to query CNPJ {cnpj_clean}: {e}")

                if isinstance(data, dict):
                    if source == "brasilapi" and data.get("cnpj"):
                        rows.append({
                            "provider_id": provider_id,
                            "status": data.get("descricao_situacao_cadastral", ""),
                            "capital_social": str(data.get("capital_social", "0")),
                            "founding_date": data.get("data_inicio_atividade", ""),
                            "address_cep": data.get("cep", ""),
                            "address_city": data.get("municipio", ""),
                            "partner_count": len(data.get("qsa", [])),
                            "simples_nacional": data.get("opcao_pelo_simples", False) or False,
                            "cnae_primary": str(data.get("cnae_fiscal", "")),
                        })
                        # Collect QSA partner data
                        qsa = data.get("qsa", [])
                        if qsa:
                            self._qsa_rows.extend(
                                extract_qsa_rows(provider_id, qsa, source="brasilapi")
                            )
                    elif source == "receitaws" and data.get("status") != "ERROR":
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
                        # Collect QSA partner data from ReceitaWS
                        qsa = data.get("qsa", [])
                        if qsa:
                            self._qsa_rows.extend(
                                extract_qsa_rows(provider_id, qsa, source="receitaws")
                            )

                # Rate limit
                if i < len(providers) - 1:
                    time.sleep(RATE_LIMIT_DELAY)

                if (i + 1) % 10 == 0:
                    logger.info(f"Enriched {i + 1}/{len(providers)} providers ({len(rows)} successful, {len(self._qsa_rows)} partners)")

        logger.info(f"Downloaded {len(rows)} CNPJ enrichment records with {len(self._qsa_rows)} QSA partners")
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

        # Parse founding_date (BrasilAPI: YYYY-MM-DD, ReceitaWS: DD/MM/YYYY)
        if "founding_date" in raw_data.columns:
            raw_data["founding_date"] = pd.to_datetime(
                raw_data["founding_date"], format="mixed", errors="coerce"
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

        # Load provider_details
        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
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
                cur.execute("RELEASE SAVEPOINT row_sp")
                loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load provider {row.get('provider_id')}: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                continue

        conn.commit()

        # Load QSA partner data
        partners_loaded = 0
        for partner_row in self._qsa_rows:
            try:
                cur.execute("SAVEPOINT partner_sp")

                if partner_row["partner_document"]:
                    cur.execute("""
                        INSERT INTO provider_partners
                            (provider_id, partner_name, partner_document, partner_type,
                             role_code, role_description, entry_date, age_range,
                             legal_rep_name, legal_rep_document, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (provider_id, partner_document) DO UPDATE SET
                            partner_name = EXCLUDED.partner_name,
                            partner_type = EXCLUDED.partner_type,
                            role_code = EXCLUDED.role_code,
                            role_description = EXCLUDED.role_description,
                            entry_date = EXCLUDED.entry_date,
                            age_range = EXCLUDED.age_range,
                            legal_rep_name = EXCLUDED.legal_rep_name,
                            legal_rep_document = EXCLUDED.legal_rep_document,
                            updated_at = NOW()
                    """, (
                        partner_row["provider_id"],
                        partner_row["partner_name"],
                        partner_row["partner_document"],
                        partner_row["partner_type"],
                        partner_row["role_code"],
                        partner_row["role_description"],
                        partner_row["entry_date"],
                        partner_row["age_range"],
                        partner_row["legal_rep_name"],
                        partner_row["legal_rep_document"],
                    ))
                else:
                    # No document — handle by name-based lookup
                    cur.execute("""
                        SELECT id FROM provider_partners
                        WHERE provider_id = %s AND partner_name = %s AND partner_document IS NULL
                    """, (partner_row["provider_id"], partner_row["partner_name"]))
                    existing = cur.fetchone()
                    if existing:
                        cur.execute("""
                            UPDATE provider_partners SET
                                partner_type = %s, role_code = %s, role_description = %s,
                                entry_date = %s, age_range = %s, legal_rep_name = %s,
                                legal_rep_document = %s, updated_at = NOW()
                            WHERE id = %s
                        """, (
                            partner_row["partner_type"],
                            partner_row["role_code"],
                            partner_row["role_description"],
                            partner_row["entry_date"],
                            partner_row["age_range"],
                            partner_row["legal_rep_name"],
                            partner_row["legal_rep_document"],
                            existing[0],
                        ))
                    else:
                        cur.execute("""
                            INSERT INTO provider_partners
                                (provider_id, partner_name, partner_document, partner_type,
                                 role_code, role_description, entry_date, age_range,
                                 legal_rep_name, legal_rep_document, updated_at)
                            VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, NOW())
                        """, (
                            partner_row["provider_id"],
                            partner_row["partner_name"],
                            partner_row["partner_type"],
                            partner_row["role_code"],
                            partner_row["role_description"],
                            partner_row["entry_date"],
                            partner_row["age_range"],
                            partner_row["legal_rep_name"],
                            partner_row["legal_rep_document"],
                        ))

                cur.execute("RELEASE SAVEPOINT partner_sp")
                partners_loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load partner for provider {partner_row.get('provider_id')}: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT partner_sp")
                continue

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} CNPJ enrichment records and {partners_loaded} QSA partners")
