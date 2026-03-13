#!/usr/bin/env python3
"""QSA Partner Backfill — re-fetches BrasilAPI for already-enriched providers
to store QSA (partner/shareholder) data that was previously discarded.

This script does NOT touch provider_details. It only populates provider_partners
for providers that already have a provider_details record but zero partner rows.

Usage:
    python3 /home/dev/enlace/scripts/enrich_qsa_partners.py [--limit N] [--delay SECONDS]
"""
import argparse
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
        logging.FileHandler("/home/dev/enlace/logs/qsa_backfill.log"),
    ],
)
logger = logging.getLogger(__name__)

BRASILAPI_URL = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
RATE_LIMIT_DELAY = 1.0
BACKOFF_429 = 5.0
MAX_RETRIES = 3
BATCH_SIZE = 200


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


def get_providers_needing_qsa(conn, limit=BATCH_SIZE):
    """Get providers that have provider_details but NO provider_partners rows."""
    cur = conn.cursor()
    cur.execute("""
        SELECT p.id, p.national_id, pd.partner_count
        FROM providers p
        JOIN provider_details pd ON p.id = pd.provider_id
        LEFT JOIN provider_partners pp ON p.id = pp.provider_id
        WHERE pp.id IS NULL
          AND pd.status != 'NOT_FOUND'
          AND pd.partner_count > 0
          AND p.national_id IS NOT NULL
          AND LENGTH(TRIM(p.national_id)) >= 11
        GROUP BY p.id, p.national_id, pd.partner_count
        ORDER BY pd.partner_count DESC, p.id
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows


def fetch_qsa(client, cnpj_clean):
    """Fetch CNPJ data from BrasilAPI and return the QSA array."""
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
                return data.get("qsa", [])
            elif resp.status_code == 404:
                logger.debug(f"CNPJ {cnpj_clean} not found on BrasilAPI")
                return []
            else:
                logger.warning(f"BrasilAPI returned {resp.status_code} for {cnpj_clean}")
                return []
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as e:
            logger.warning(f"Connection error for {cnpj_clean}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 * (attempt + 1))
            continue
        except Exception as e:
            logger.warning(f"Unexpected error for {cnpj_clean}: {e}")
            return []
    return []


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
                    provider_id, partner_name[:300], partner_document,
                    partner_type, role_code[:10] if role_code else None,
                    role_description[:200] if role_description else None,
                    entry_date, age_range[:50] if age_range else None,
                    legal_rep_name[:300] if legal_rep_name else None,
                    legal_rep_document[:20] if legal_rep_document else None,
                ))
            else:
                # No document — handle by name-based lookup to avoid duplicates
                cur.execute("""
                    SELECT id FROM provider_partners
                    WHERE provider_id = %s AND partner_name = %s AND partner_document IS NULL
                """, (provider_id, partner_name[:300]))
                existing = cur.fetchone()
                if existing:
                    cur.execute("""
                        UPDATE provider_partners SET
                            partner_type = %s, role_code = %s, role_description = %s,
                            entry_date = %s, age_range = %s, legal_rep_name = %s,
                            legal_rep_document = %s, updated_at = NOW()
                        WHERE id = %s
                    """, (
                        partner_type, role_code[:10] if role_code else None,
                        role_description[:200] if role_description else None,
                        entry_date, age_range[:50] if age_range else None,
                        legal_rep_name[:300] if legal_rep_name else None,
                        legal_rep_document[:20] if legal_rep_document else None,
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
                        provider_id, partner_name[:300], partner_type,
                        role_code[:10] if role_code else None,
                        role_description[:200] if role_description else None,
                        entry_date, age_range[:50] if age_range else None,
                        legal_rep_name[:300] if legal_rep_name else None,
                        legal_rep_document[:20] if legal_rep_document else None,
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


def main():
    parser = argparse.ArgumentParser(description="Backfill QSA partner data for already-enriched providers")
    parser.add_argument("--limit", type=int, default=5000, help="Max providers to process (default: 5000)")
    parser.add_argument("--delay", type=float, default=RATE_LIMIT_DELAY, help="Delay between API requests in seconds (default: 1.0)")
    args = parser.parse_args()

    conn = psycopg2.connect("dbname=enlace user=enlace")

    # Ensure table and indexes exist (idempotent)
    cur = conn.cursor()
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

    total_providers = 0
    total_partners = 0
    total_skipped = 0
    total_api_errors = 0
    start_time = time.time()

    client = httpx.Client(
        timeout=httpx.Timeout(30.0, connect=15.0),
        follow_redirects=True,
        headers={"User-Agent": "ENLACE-QSA-Backfill/1.0"},
    )

    try:
        processed = 0
        while processed < args.limit:
            batch_limit = min(BATCH_SIZE, args.limit - processed)
            providers = get_providers_needing_qsa(conn, limit=batch_limit)

            if not providers:
                logger.info("All eligible providers have QSA data backfilled!")
                break

            logger.info(f"Processing batch of {len(providers)} providers (offset {processed})")

            for i, (provider_id, cnpj, expected_partners) in enumerate(providers):
                cnpj_clean = cnpj.strip().replace(".", "").replace("/", "").replace("-", "")
                if len(cnpj_clean) < 11:
                    total_skipped += 1
                    processed += 1
                    continue

                qsa = fetch_qsa(client, cnpj_clean)

                if qsa:
                    partner_count = upsert_partners(conn, provider_id, qsa)
                    total_partners += partner_count
                    if partner_count > 0:
                        logger.debug(
                            f"Provider {provider_id}: stored {partner_count} partners "
                            f"(expected {expected_partners})"
                        )
                    total_providers += 1
                elif expected_partners and expected_partners > 0:
                    # API returned no QSA but we expected partners -- could be API issue
                    total_api_errors += 1
                    logger.debug(
                        f"Provider {provider_id}: expected {expected_partners} partners "
                        f"but got empty QSA"
                    )
                else:
                    total_skipped += 1

                processed += 1

                # Progress logging every 25 records
                if processed % 25 == 0:
                    elapsed = time.time() - start_time
                    rate = processed / elapsed * 3600 if elapsed > 0 else 0
                    logger.info(
                        f"Progress: {processed} processed | "
                        f"{total_providers} with partners | "
                        f"{total_partners} total partners | "
                        f"{total_skipped} skipped | "
                        f"{total_api_errors} API mismatches | "
                        f"Rate: {rate:.0f}/hr | "
                        f"Elapsed: {elapsed/60:.1f}min"
                    )

                # Rate limit
                time.sleep(args.delay)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        client.close()
        conn.close()
        elapsed = time.time() - start_time
        logger.info(
            f"DONE. Processed {total_providers} providers, "
            f"stored {total_partners} partners, "
            f"{total_skipped} skipped, {total_api_errors} API mismatches "
            f"in {elapsed/60:.1f} minutes"
        )


if __name__ == "__main__":
    main()
