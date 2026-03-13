#!/usr/bin/env python3
"""Continuous CNPJ enrichment — processes all active ISPs via BrasilAPI.

Queries all active providers (those with broadband_subscribers) that lack
provider_details, then processes them sequentially with 1s delay between
requests. Inserts/upserts each record immediately. Handles 429 with backoff.

Also stores QSA (partner) data in provider_partners table.
"""
import logging
import sys
import time

import httpx
import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/home/dev/enlace/logs/cnpj_enrichment_all.log"),
    ],
)
logger = logging.getLogger(__name__)

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
RECEITAWS_URL = "https://receitaws.com.br/v1/cnpj/{cnpj}"
RATE_LIMIT_DELAY = 1.0
BACKOFF_429 = 5.0
MAX_RETRIES = 3
BATCH_SIZE = 500


def get_pending_providers(conn, limit=BATCH_SIZE):
    """Get next batch of active providers needing enrichment."""
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.national_id
        FROM providers p
        JOIN broadband_subscribers bs ON bs.provider_id = p.id
        LEFT JOIN provider_details pd ON p.id = pd.provider_id
        WHERE pd.id IS NULL
          AND p.national_id IS NOT NULL
          AND LENGTH(TRIM(p.national_id)) >= 11
        GROUP BY p.id, p.national_id
        ORDER BY p.id
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows


def fetch_cnpj(client, cnpj_clean):
    """Fetch CNPJ data from BrasilAPI with ReceitaWS fallback."""
    data = None
    source = None

    for attempt in range(MAX_RETRIES):
        try:
            url = BRASILAPI_URL.format(cnpj=cnpj_clean)
            resp = client.get(url)
            if resp.status_code == 429:
                wait = BACKOFF_429 * (attempt + 1)
                logger.warning(f"429 from BrasilAPI for {cnpj_clean}, waiting {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code == 200:
                data = resp.json()
                source = "brasilapi"
                break
            elif resp.status_code == 404:
                # CNPJ not found in BrasilAPI, try fallback
                break
            else:
                logger.warning(f"BrasilAPI returned {resp.status_code} for {cnpj_clean}")
                break
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            logger.warning(f"Connection error for BrasilAPI {cnpj_clean}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
            continue
        except Exception as e:
            logger.warning(f"Unexpected error for BrasilAPI {cnpj_clean}: {e}")
            break

    # Fallback to ReceitaWS if BrasilAPI failed
    if data is None or source is None:
        for attempt in range(MAX_RETRIES):
            try:
                url = RECEITAWS_URL.format(cnpj=cnpj_clean)
                resp = client.get(url)
                if resp.status_code == 429:
                    wait = BACKOFF_429 * (attempt + 1)
                    logger.warning(f"429 from ReceitaWS for {cnpj_clean}, waiting {wait}s")
                    time.sleep(wait)
                    continue
                if resp.status_code == 200:
                    data = resp.json()
                    source = "receitaws"
                    break
                else:
                    break
            except Exception as e:
                logger.warning(f"ReceitaWS error for {cnpj_clean}: {e}")
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 * (attempt + 1))
                continue

    return data, source


def parse_response(provider_id, data, source):
    """Parse BrasilAPI or ReceitaWS response into a row dict."""
    if not isinstance(data, dict):
        return None

    if source == "brasilapi" and data.get("cnpj"):
        capital = data.get("capital_social", 0)
        try:
            capital = float(str(capital).replace(",", ".")) if capital else 0.0
        except (ValueError, TypeError):
            capital = 0.0

        founding = data.get("data_inicio_atividade", "")
        # BrasilAPI returns YYYY-MM-DD
        if founding and len(str(founding)) < 8:
            founding = None

        return {
            "provider_id": provider_id,
            "status": str(data.get("descricao_situacao_cadastral", ""))[:50],
            "capital_social": capital,
            "founding_date": founding or None,
            "address_cep": str(data.get("cep", ""))[:10],
            "address_city": str(data.get("municipio", ""))[:200],
            "partner_count": len(data.get("qsa", [])),
            "simples_nacional": bool(data.get("opcao_pelo_simples", False) or False),
            "cnae_primary": str(data.get("cnae_fiscal", ""))[:20],
        }
    elif source == "receitaws" and data.get("status") != "ERROR":
        capital = data.get("capital_social", "0")
        try:
            capital = float(str(capital).replace(",", ".")) if capital else 0.0
        except (ValueError, TypeError):
            capital = 0.0

        founding = data.get("abertura", "")
        # ReceitaWS returns DD/MM/YYYY — convert to YYYY-MM-DD
        if founding and "/" in str(founding):
            parts = str(founding).split("/")
            if len(parts) == 3:
                founding = f"{parts[2]}-{parts[1]}-{parts[0]}"

        simples = False
        simples_data = data.get("simples")
        if isinstance(simples_data, dict):
            simples = bool(simples_data.get("optante", False))

        cnae = ""
        ativ = data.get("atividade_principal")
        if ativ and isinstance(ativ, list) and len(ativ) > 0:
            cnae = str(ativ[0].get("code", ""))[:20]

        return {
            "provider_id": provider_id,
            "status": str(data.get("situacao", ""))[:50],
            "capital_social": capital,
            "founding_date": founding or None,
            "address_cep": str(data.get("cep", ""))[:10],
            "address_city": str(data.get("municipio", ""))[:200],
            "partner_count": len(data.get("qsa", [])),
            "simples_nacional": simples,
            "cnae_primary": cnae,
        }

    return None


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


def upsert_partners(conn, provider_id, qsa_list):
    """Insert/update partner records for a provider from QSA data."""
    if not qsa_list:
        return 0

    cur = conn.cursor()
    inserted = 0

    for partner in qsa_list:
        if not isinstance(partner, dict):
            continue

        partner_name = partner.get("nome_socio", "").strip()
        if not partner_name:
            continue

        partner_document = partner.get("cnpj_cpf_do_socio", "").strip() or None
        partner_type = determine_partner_type(partner_document)
        role_code = str(partner.get("codigo_qualificacao_socio", "")).strip() or None
        role_description = partner.get("qualificacao_socio", "").strip() or None
        entry_date = parse_entry_date(partner.get("data_entrada_sociedade", ""))
        age_range = partner.get("faixa_etaria", "").strip() or None
        legal_rep_name = partner.get("nome_representante_legal", "").strip() or None
        legal_rep_document = partner.get("cpf_representante_legal", "").strip() or None

        try:
            cur.execute("SAVEPOINT partner_sp")

            if partner_document:
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
                    provider_id, partner_name, partner_document, partner_type,
                    role_code, role_description, entry_date, age_range,
                    legal_rep_name, legal_rep_document,
                ))
            else:
                # No document — handle by name-based lookup
                cur.execute("""
                    SELECT id FROM provider_partners
                    WHERE provider_id = %s AND partner_name = %s AND partner_document IS NULL
                """, (provider_id, partner_name))
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE provider_partners SET
                            partner_type = %s, role_code = %s, role_description = %s,
                            entry_date = %s, age_range = %s, legal_rep_name = %s,
                            legal_rep_document = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (
                        partner_type, role_code, role_description,
                        entry_date, age_range, legal_rep_name,
                        legal_rep_document, existing[0],
                    ))
                else:
                    cur.execute("""
                        INSERT INTO provider_partners
                            (provider_id, partner_name, partner_document, partner_type,
                             role_code, role_description, entry_date, age_range,
                             legal_rep_name, legal_rep_document, updated_at)
                        VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        provider_id, partner_name, partner_type,
                        role_code, role_description, entry_date, age_range,
                        legal_rep_name, legal_rep_document,
                    ))

            cur.execute("RELEASE SAVEPOINT partner_sp")
            inserted += 1
        except Exception as e:
            logger.warning(f"Failed to upsert partner for provider {provider_id}: {e}")
            cur.execute("ROLLBACK TO SAVEPOINT partner_sp")
            continue

    conn.commit()
    cur.close()
    return inserted


def upsert_record(conn, row):
    """Upsert a single provider_details record."""
    cur = conn.cursor()
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
            row["provider_id"],
            row["status"],
            row["capital_social"],
            row["founding_date"],
            row["address_cep"],
            row["address_city"],
            row["partner_count"],
            row["simples_nacional"],
            row["cnae_primary"],
        ))
        cur.execute("RELEASE SAVEPOINT row_sp")
        conn.commit()
        return True
    except Exception as e:
        logger.warning(f"Failed to upsert provider {row['provider_id']}: {e}")
        cur.execute("ROLLBACK TO SAVEPOINT row_sp")
        conn.commit()
        return False
    finally:
        cur.close()


def main():
    conn = psycopg2.connect("dbname=enlace user=enlace")

    # Ensure tables exist
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
    cur.close()

    total_enriched = 0
    total_failed = 0
    total_skipped = 0
    total_partners = 0
    batch_num = 0
    start_time = time.time()

    client = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=15.0),
        follow_redirects=True,
        headers={"User-Agent": "ENLACE-Pipeline/1.0"},
    )

    try:
        while True:
            batch_num += 1
            providers = get_pending_providers(conn)

            if not providers:
                logger.info("All active providers have been enriched!")
                break

            logger.info(f"=== Batch {batch_num}: processing {len(providers)} providers ===")

            for i, (provider_id, cnpj) in enumerate(providers):
                cnpj_clean = cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
                if len(cnpj_clean) < 11:
                    total_skipped += 1
                    continue

                data, source = fetch_cnpj(client, cnpj_clean)
                row = parse_response(provider_id, data, source) if data else None

                if row:
                    if upsert_record(conn, row):
                        total_enriched += 1

                        # Store QSA partner data
                        qsa = data.get("qsa", []) if isinstance(data, dict) else []
                        if qsa:
                            partner_count = upsert_partners(conn, provider_id, qsa)
                            total_partners += partner_count
                            if partner_count > 0:
                                logger.debug(
                                    f"Stored {partner_count} partners for provider {provider_id}"
                                )
                    else:
                        total_failed += 1
                else:
                    total_skipped += 1
                    # Insert a placeholder so we don't retry this CNPJ endlessly
                    placeholder_cur = conn.cursor()
                    try:
                        placeholder_cur.execute("SAVEPOINT ph_sp")
                        placeholder_cur.execute("""
                            INSERT INTO provider_details
                                (provider_id, status, capital_social, updated_at)
                            VALUES (%s, 'NOT_FOUND', 0, NOW())
                            ON CONFLICT (provider_id) DO UPDATE SET
                                status = 'NOT_FOUND', updated_at = NOW()
                        """, (provider_id,))
                        placeholder_cur.execute("RELEASE SAVEPOINT ph_sp")
                        conn.commit()
                    except Exception:
                        placeholder_cur.execute("ROLLBACK TO SAVEPOINT ph_sp")
                        conn.commit()
                    finally:
                        placeholder_cur.close()

                # Progress logging every 50 records
                count = (batch_num - 1) * BATCH_SIZE + i + 1
                if count % 50 == 0:
                    elapsed = time.time() - start_time
                    rate = total_enriched / elapsed * 3600 if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {count} processed | "
                        f"{total_enriched} enriched | "
                        f"{total_partners} partners | "
                        f"{total_failed} failed | "
                        f"{total_skipped} skipped | "
                        f"Rate: {rate:.0f}/hr | "
                        f"Elapsed: {elapsed/60:.1f}min"
                    )

                # Rate limit between requests (not between batches)
                time.sleep(RATE_LIMIT_DELAY)

            logger.info(
                f"Batch {batch_num} complete. Running totals: "
                f"{total_enriched} enriched, {total_partners} partners, "
                f"{total_failed} failed, {total_skipped} skipped"
            )

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        client.close()
        conn.close()
        elapsed = time.time() - start_time
        logger.info(
            f"DONE. Total: {total_enriched} enriched, {total_partners} partners, "
            f"{total_failed} failed, {total_skipped} skipped in {elapsed/60:.1f} minutes"
        )


if __name__ == "__main__":
    main()
