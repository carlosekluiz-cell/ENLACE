"""Portal da Transparência CEIS/CNEP sanctions check pipeline.

Source: Portal da Transparência — Controladoria-Geral da União (CGU)
APIs:
  CEIS: https://api.portaldatransparencia.gov.br/api-de-dados/ceis
  CNEP: https://api.portaldatransparencia.gov.br/api-de-dados/cnep

CEIS = Cadastro Nacional de Empresas Inidôneas e Suspensas
  (companies barred from government contracts)
CNEP = Cadastro Nacional de Empresas Punidas
  (companies penalized under anti-corruption law)

Each API accepts `codigoSancionado` with a **formatted** CNPJ
(XX.XXX.XXX/XXXX-XX) and returns a JSON array of sanction records.
Pagination via `pagina` param (15 results/page).

Rate limit: 80 requests/minute => 0.75s between requests.
Since we check both CEIS and CNEP per CNPJ, each provider costs ~2 requests
(~1.5s). With 13,500+ active providers, a full scan takes ~5.6 hours.
We limit each run to 2,000 providers and track progress via updated_at
so subsequent runs pick up where we left off.

Schedule: Weekly (suggested: Sunday at 03:00 UTC)
"""
import logging
import re
import time
from datetime import datetime, date, timedelta
from typing import Any, Optional

import httpx

from python.pipeline.base import BasePipeline

logger = logging.getLogger(__name__)

# Portal da Transparência API configuration
TRANSPARENCIA_API_KEY = "eca00a12fee105721404aae5d34e0539"
TRANSPARENCIA_BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"

# Endpoints for the two sanctions lists
SANCTIONS_LISTS = {
    "CEIS": f"{TRANSPARENCIA_BASE_URL}/ceis",
    "CNEP": f"{TRANSPARENCIA_BASE_URL}/cnep",
}

# Rate limiting: 80 req/min = 0.75s between requests
REQUEST_DELAY_SECONDS = 0.75

# Max providers to check per run (avoids multi-hour runs)
MAX_PROVIDERS_PER_RUN = 2000

# Freshness threshold: skip if last run < 7 days ago
FRESHNESS_DAYS = 7

# Regex to strip CNPJ formatting: 10.496.760/0001-95 -> 10496760000195
CNPJ_STRIP_RE = re.compile(r"[.\-/\s]")


def strip_cnpj(raw: str) -> str:
    """Remove formatting from a CNPJ string, keeping only digits."""
    return CNPJ_STRIP_RE.sub("", raw.strip())


def format_cnpj(digits: str) -> str:
    """Format a 14-digit CNPJ string into XX.XXX.XXX/XXXX-XX.

    The Portal da Transparência API requires formatted CNPJs for the
    `codigoSancionado` parameter. Unformatted digits return no results.
    """
    d = digits.strip()
    if len(d) < 14:
        # Pad with leading zeros if needed (some CNPJs stored without them)
        d = d.zfill(14)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"


def parse_br_date(date_str: str) -> Optional[date]:
    """Parse a Brazilian date string (DD/MM/YYYY) to a Python date.

    Returns None for empty, 'Sem informação', or unparseable strings.
    """
    if not date_str or date_str.strip().lower().startswith("sem"):
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, TypeError):
            continue
    return None


class SanctionsCheckPipeline(BasePipeline):
    """Check ISP providers against CEIS and CNEP sanctions lists.

    Downloads sanction records from Portal da Transparência for each
    provider with an active broadband presence. Results are upserted
    into the provider_sanctions table keyed on (cnpj, list_type, process_number).

    To avoid excessive API calls, each run processes up to 2,000 providers,
    prioritizing those never checked or least recently checked.
    """

    def __init__(self):
        super().__init__("sanctions_check")
        self._providers: list[tuple[int, str]] = []  # (provider_id, cnpj_digits)

    def check_for_updates(self) -> bool:
        """Check if provider_sanctions has been updated in the last 7 days.

        Returns True (should run) if:
        - No records exist yet, OR
        - The most recent update is older than FRESHNESS_DAYS, OR
        - There are unchecked providers (never scanned)
        """
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*), MAX(updated_at) FROM provider_sanctions")
        count, last_update = cur.fetchone()

        if count == 0:
            logger.info("No sanctions data yet — will run full scan")
            cur.close()
            conn.close()
            return True

        if last_update:
            age_days = (datetime.utcnow() - last_update).days
            if age_days < FRESHNESS_DAYS:
                # Even if recent, check if there are unchecked providers
                cur.execute("""
                    SELECT COUNT(DISTINCT p.id)
                    FROM providers p
                    JOIN broadband_subscribers bs ON bs.provider_id = p.id
                    WHERE p.national_id IS NOT NULL
                      AND LENGTH(p.national_id) >= 11
                      AND p.id NOT IN (
                          SELECT DISTINCT provider_id FROM provider_sanctions
                      )
                """)
                unchecked = cur.fetchone()[0]
                if unchecked > 0:
                    logger.info(
                        f"Sanctions data is {age_days} days old but "
                        f"{unchecked} providers unchecked — will continue scan"
                    )
                    cur.close()
                    conn.close()
                    return True

                logger.info(
                    f"Sanctions data is {age_days} days old and all providers "
                    f"checked — skipping"
                )
                cur.close()
                conn.close()
                return False
            else:
                logger.info(
                    f"Sanctions data is {age_days} days old — will refresh"
                )

        cur.close()
        conn.close()
        return True

    def download(self) -> list[dict]:
        """Query CEIS and CNEP for each provider's CNPJ.

        Loads up to MAX_PROVIDERS_PER_RUN providers, prioritizing those
        never checked (not in provider_sanctions) then oldest-checked.
        For each CNPJ, queries both CEIS and CNEP endpoints using the
        formatted CNPJ (XX.XXX.XXX/XXXX-XX) via the codigoSancionado param.

        Returns a list of raw sanction records with provider_id attached.
        """
        self._providers = self._load_provider_cnpjs()
        if not self._providers:
            logger.warning("No providers with CNPJs found")
            return []

        logger.info(
            f"Will check {len(self._providers)} providers against "
            f"CEIS and CNEP sanctions lists"
        )

        all_sanctions = []
        checked_count = 0
        sanctions_found = 0

        headers = {"chave-api-dados": TRANSPARENCIA_API_KEY}

        with httpx.Client(
            timeout=httpx.Timeout(30.0, connect=15.0),
            follow_redirects=True,
            headers=headers,
        ) as client:
            for provider_id, cnpj in self._providers:
                checked_count += 1

                for list_type, url in SANCTIONS_LISTS.items():
                    try:
                        records = self._query_sanctions_list(
                            client, url, list_type, cnpj, provider_id
                        )
                        if records:
                            all_sanctions.extend(records)
                            sanctions_found += len(records)
                        # Rate limit between requests
                        time.sleep(REQUEST_DELAY_SECONDS)
                    except Exception as e:
                        logger.warning(
                            f"Error querying {list_type} for CNPJ {cnpj} "
                            f"(provider {provider_id}): {e}"
                        )
                        time.sleep(REQUEST_DELAY_SECONDS)

                if checked_count % 100 == 0:
                    logger.info(
                        f"Progress: {checked_count}/{len(self._providers)} "
                        f"providers checked, {sanctions_found} sanctions found"
                    )

        self.rows_processed = checked_count
        logger.info(
            f"Checked {checked_count} providers, found "
            f"{sanctions_found} sanction records"
        )
        return all_sanctions

    def _query_sanctions_list(
        self,
        client: httpx.Client,
        url: str,
        list_type: str,
        cnpj: str,
        provider_id: int,
    ) -> list[dict]:
        """Query a single sanctions list for a CNPJ, handling pagination.

        The Portal da Transparência API requires the `codigoSancionado`
        parameter with a formatted CNPJ (XX.XXX.XXX/XXXX-XX).
        Returns raw records with provider_id, cnpj, and list_type attached.
        """
        all_records = []
        page = 1
        max_pages = 10  # Safety limit (150 sanctions per CNPJ should be enough)
        formatted = format_cnpj(cnpj)

        while page <= max_pages:
            resp = client.get(
                url,
                params={
                    "codigoSancionado": formatted,
                    "pagina": page,
                    "tamanhoPagina": 15,
                },
            )

            if resp.status_code == 429:
                # Rate limited — back off and retry
                retry_after = int(resp.headers.get("Retry-After", "60"))
                logger.warning(
                    f"Rate limited on {list_type}, sleeping {retry_after}s"
                )
                time.sleep(retry_after)
                continue

            resp.raise_for_status()
            data = resp.json()

            if not data or not isinstance(data, list):
                break

            for item in data:
                item["_provider_id"] = provider_id
                item["_cnpj"] = cnpj
                item["_list_type"] = list_type
                all_records.append(item)

            # If fewer than 15 results, we've reached the last page
            if len(data) < 15:
                break

            page += 1
            time.sleep(REQUEST_DELAY_SECONDS)

        return all_records

    def _load_provider_cnpjs(self) -> list[tuple[int, str]]:
        """Load provider CNPJs to check, prioritizing unchecked providers.

        Returns up to MAX_PROVIDERS_PER_RUN tuples of (provider_id, cnpj_digits).
        Order: unchecked providers first, then oldest-checked providers.
        """
        conn = self._get_connection()
        cur = conn.cursor()

        # Get active broadband providers with valid CNPJs, ordered by
        # check recency (NULL = never checked = highest priority)
        cur.execute("""
            WITH active_providers AS (
                SELECT DISTINCT p.id, p.national_id
                FROM providers p
                JOIN broadband_subscribers bs ON bs.provider_id = p.id
                WHERE p.national_id IS NOT NULL
                  AND LENGTH(p.national_id) >= 11
            ),
            last_checked AS (
                SELECT provider_id, MAX(updated_at) AS last_check
                FROM provider_sanctions
                GROUP BY provider_id
            )
            SELECT ap.id, ap.national_id
            FROM active_providers ap
            LEFT JOIN last_checked lc ON lc.provider_id = ap.id
            ORDER BY lc.last_check ASC NULLS FIRST
            LIMIT %s
        """, (MAX_PROVIDERS_PER_RUN,))

        providers = []
        for row in cur.fetchall():
            provider_id = row[0]
            cnpj = strip_cnpj(row[1])
            if len(cnpj) >= 11:
                providers.append((provider_id, cnpj))

        cur.close()
        conn.close()
        logger.info(f"Loaded {len(providers)} providers for sanctions check")
        return providers

    def transform(self, raw_data: list[dict]) -> list[dict]:
        """Parse and normalize raw API responses into load-ready dicts.

        Extracts structured fields from the nested API response and
        parses DD/MM/YYYY dates into Python date objects.
        """
        if not raw_data:
            return []

        transformed = []
        for item in raw_data:
            provider_id = item["_provider_id"]
            cnpj = item["_cnpj"]
            list_type = item["_list_type"]

            # Extract sanction type
            tipo_sancao = item.get("tipoSancao") or {}
            sanction_type = (
                tipo_sancao.get("descricaoResumida", "")
                or tipo_sancao.get("descricaoPortal", "")
            )

            # Extract sanctioning authority
            orgao = item.get("orgaoSancionador") or {}
            sanctioning_authority = orgao.get("nome", "")

            # Fallback to source authority if sanctioning body is empty
            if not sanctioning_authority:
                fonte = item.get("fonteSancao") or {}
                sanctioning_authority = fonte.get("nomeExibicao", "")

            # Parse dates
            start_date = parse_br_date(item.get("dataInicioSancao", ""))
            end_date = parse_br_date(item.get("dataFimSancao", ""))

            # Extract legal basis (first fundamentacao entry, truncated)
            fundamentacao = item.get("fundamentacao") or []
            legal_basis = ""
            if fundamentacao and isinstance(fundamentacao, list):
                legal_basis = fundamentacao[0].get("descricao", "")

            # Process number
            process_number = (item.get("numeroProcesso") or "").strip()

            # Build source URL for Portal da Transparência detail page
            record_id = item.get("id", "")
            source_url = (
                f"https://portaldatransparencia.gov.br/sancoes/"
                f"{list_type.lower()}/{record_id}"
            )

            transformed.append({
                "provider_id": provider_id,
                "cnpj": cnpj[:20],
                "list_type": list_type,
                "sanction_type": sanction_type[:500] if sanction_type else None,
                "sanctioning_authority": (
                    sanctioning_authority[:500]
                    if sanctioning_authority else None
                ),
                "sanction_start_date": start_date,
                "sanction_end_date": end_date,
                "legal_basis": legal_basis[:500] if legal_basis else None,
                "process_number": process_number[:200] if process_number else None,
                "source_url": source_url[:500],
            })

        logger.info(f"Transformed {len(transformed)} sanction records")
        return transformed

    def load(self, data: list[dict]) -> None:
        """Upsert sanction records into provider_sanctions.

        Uses the UNIQUE(cnpj, list_type, process_number) constraint for
        conflict resolution — updates existing records and inserts new ones.

        Also inserts a sentinel record for each checked provider that had
        zero sanctions, so we can track which providers have been scanned
        (important for incremental progress across runs).
        """
        conn = self._get_connection()
        cur = conn.cursor()

        inserted = 0
        updated = 0
        skipped = 0

        # Upsert actual sanction records
        for row in data:
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO provider_sanctions
                    (provider_id, cnpj, list_type, sanction_type,
                     sanctioning_authority, sanction_start_date,
                     sanction_end_date, legal_basis, process_number,
                     source_url, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (cnpj, list_type, process_number)
                    DO UPDATE SET
                        sanction_type = EXCLUDED.sanction_type,
                        sanctioning_authority = EXCLUDED.sanctioning_authority,
                        sanction_start_date = EXCLUDED.sanction_start_date,
                        sanction_end_date = EXCLUDED.sanction_end_date,
                        legal_basis = EXCLUDED.legal_basis,
                        source_url = EXCLUDED.source_url,
                        updated_at = NOW()
                    RETURNING (xmax = 0) AS is_insert
                """, (
                    row["provider_id"],
                    row["cnpj"],
                    row["list_type"],
                    row["sanction_type"],
                    row["sanctioning_authority"],
                    row["sanction_start_date"],
                    row["sanction_end_date"],
                    row["legal_basis"],
                    row["process_number"],
                    row["source_url"],
                ))
                result = cur.fetchone()
                if result and result[0]:
                    inserted += 1
                else:
                    updated += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.debug(f"Skipping sanction row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                skipped += 1

        conn.commit()

        # For providers that were checked but had zero sanctions,
        # insert a sentinel record so check_for_updates knows they were scanned.
        # list_type='CLEAN' with process_number='__sentinel__' marks clean providers.
        providers_with_sanctions = set()
        for row in data:
            providers_with_sanctions.add(row["provider_id"])

        clean_count = 0
        for provider_id, cnpj in self._providers:
            if provider_id not in providers_with_sanctions:
                try:
                    cur.execute("SAVEPOINT sentinel_sp")
                    cur.execute("""
                        INSERT INTO provider_sanctions
                        (provider_id, cnpj, list_type, process_number, updated_at)
                        VALUES (%s, %s, 'CLEAN', '__sentinel__', NOW())
                        ON CONFLICT (cnpj, list_type, process_number)
                        DO UPDATE SET updated_at = NOW()
                    """, (provider_id, cnpj[:20]))
                    clean_count += 1
                    cur.execute("RELEASE SAVEPOINT sentinel_sp")
                except Exception as e:
                    logger.debug(f"Skipping sentinel for provider {provider_id}: {e}")
                    cur.execute("ROLLBACK TO SAVEPOINT sentinel_sp")

        conn.commit()
        cur.close()
        conn.close()

        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(
            f"Loaded {inserted} new + {updated} updated sanction records "
            f"({skipped} skipped). {clean_count} clean providers marked."
        )

    def post_load(self) -> None:
        """Log summary statistics after loading."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Count actual sanctions (exclude sentinel records)
        cur.execute("""
            SELECT list_type, COUNT(*), COUNT(DISTINCT provider_id)
            FROM provider_sanctions
            WHERE list_type != 'CLEAN'
            GROUP BY list_type
            ORDER BY list_type
        """)
        for row in cur.fetchall():
            list_type, count, providers = row
            logger.info(
                f"  {list_type}: {count} sanctions across {providers} providers"
            )

        # Overall summary
        cur.execute("""
            SELECT
                COUNT(DISTINCT CASE WHEN list_type != 'CLEAN'
                    THEN provider_id END) AS sanctioned,
                COUNT(DISTINCT CASE WHEN list_type = 'CLEAN'
                    THEN provider_id END) AS clean,
                COUNT(CASE WHEN list_type != 'CLEAN' THEN 1 END) AS total_sanctions
            FROM provider_sanctions
        """)
        sanctioned, clean, total = cur.fetchone()
        logger.info(
            f"Sanctions summary: {sanctioned} providers with {total} sanctions, "
            f"{clean} providers clean"
        )

        # Active sanctions (end_date is NULL or in the future)
        cur.execute("""
            SELECT COUNT(*)
            FROM provider_sanctions
            WHERE list_type != 'CLEAN'
              AND (sanction_end_date IS NULL OR sanction_end_date >= CURRENT_DATE)
        """)
        active = cur.fetchone()[0]
        logger.info(f"  Active (current) sanctions: {active}")

        cur.close()
        conn.close()
