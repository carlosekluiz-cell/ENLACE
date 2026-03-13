"""PNCP Government Contracts pipeline — telecom public procurement tracking.

Source: Portal Nacional de Contratacoes Publicas (PNCP)
URL: https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
Format: REST JSON (paginated via pagina parameter, 10 results per page)
Key fields: orgaoEntidade, objetoCompra, valorTotalEstimado/Homologado, unidadeOrgao

Government telecom contracts reveal where public investment is happening
in broadband, fiber, and network infrastructure. This data is critical
for ISPs to identify upcoming CAPEX-funded projects, co-investment
opportunities, and regulated market segments.

The API requires codigoModalidadeContratacao (modality code) and date range.
We pass telecom keywords via the q= parameter as a server-side hint and also
apply strict local keyword matching on objetoCompra to guarantee only
telecom-related contracts are retained.

Local filter patterns: telecomunicacao, telecomunicacoes, fibra optica,
    banda larga, internet, conectividade, rede optica, backbone,
    provedor de internet, infraestrutura de rede, torre de comunicacao,
    radiofrequencia, link dedicado, wifi, inclusao digital

We query across the main procurement modalities (Pregao Eletronico, Dispensa,
Inexigibilidade, Concorrencia, Credenciamento) and break the 12-month window
into monthly chunks to stay within API pagination limits.  Each (modality, month)
pair is paginated up to MAX_PAGES pages (10 results per page).

Schedule: Daily at 02:30 UTC
"""
import logging
import re
import time
from datetime import datetime, timedelta, date

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

PNCP_BASE_URL = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"

# Keywords passed via the q= parameter as a server-side hint.
# The API does not reliably filter on q=, so we cycle through these keywords
# to maximise the chance of surfacing telecom results in the first pages.
# Local regex filtering (see _TELECOM_RE below) is the authoritative filter.
SEARCH_KEYWORDS = [
    "telecomunicacao",
    "fibra optica",
    "banda larga",
    "internet",
    "conectividade",
]

# Patterns for LOCAL filtering on objetoCompra (case-insensitive).
# These are broader than SEARCH_KEYWORDS and catch accented variants.
_TELECOM_PATTERNS = [
    r"telecomunica",      # telecomunicacao, telecomunicacoes, telecomunicacoes
    r"fibra\s*[oó]ptica",
    r"banda\s*larga",
    r"conectividade",
    r"rede\s*[oó]ptica",
    r"backbone",
    r"provedor.*internet",
    r"infraestrutura\s*(de\s*)?rede",
    r"torre.*comunica",
    r"radiofrequ[eê]ncia",
    r"servi[cç]o.*internet",
    r"link\s*dedicado",
    r"acesso.*internet",
    r"rede\s*metropolitana",
    r"wifi|wi-fi",
    r"inclus[aã]o\s*digital",
]
_TELECOM_RE = re.compile("|".join(_TELECOM_PATTERNS), re.IGNORECASE)

# Government spheres mapped from PNCP esferaId codes
SPHERE_MAP = {
    "F": "federal",
    "E": "estadual",
    "M": "municipal",
    "D": "distrital",
}

# Procurement modality codes to search (the API requires one per request).
# 4=Concorrencia Eletronica, 6=Pregao Eletronico, 8=Dispensa,
# 9=Inexigibilidade, 12=Credenciamento
MODALITY_CODES = ["6", "8", "9", "4", "12"]

# Maximum pages to fetch per (modality, month, keyword) combination.
# The API returns 10 results per page.
MAX_PAGES = 500

# Polite delay between paginated requests (seconds)
REQUEST_DELAY = 0.3


def _is_telecom(objeto: str) -> bool:
    """Return True if the objetoCompra text matches telecom-related patterns."""
    return bool(_TELECOM_RE.search(objeto))


def _month_ranges(start: date, end: date) -> list[tuple[str, str]]:
    """Break a date range into monthly chunks as (YYYYMMDD, YYYYMMDD) tuples."""
    ranges = []
    cursor = start.replace(day=1)
    while cursor <= end:
        month_start = max(cursor, start)
        # Last day of the month
        if cursor.month == 12:
            month_end = cursor.replace(year=cursor.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = cursor.replace(month=cursor.month + 1, day=1) - timedelta(days=1)
        month_end = min(month_end, end)
        ranges.append((month_start.strftime("%Y%m%d"), month_end.strftime("%Y%m%d")))
        # Advance to next month
        if cursor.month == 12:
            cursor = cursor.replace(year=cursor.year + 1, month=1)
        else:
            cursor = cursor.replace(month=cursor.month + 1)
    return ranges


class PNCPContractsPipeline(BasePipeline):
    """Ingest government telecom contracts from PNCP (Portal Nacional de Contratacoes Publicas).

    Downloads public procurement contracts from the PNCP API across multiple
    modalities and monthly date windows, filters locally for telecom-related
    contracts using pattern matching on objetoCompra, and resolves municipality
    IBGE codes to l2_id via admin_level_2.code.

    If the PNCP API is unavailable, this pipeline raises an error.
    No synthetic data is generated.
    """

    def __init__(self):
        super().__init__("pncp_contracts")

    def check_for_updates(self) -> bool:
        """Create the government_contracts table if needed and check for staleness."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS government_contracts (
                id SERIAL PRIMARY KEY,
                contracting_entity_cnpj VARCHAR(20),
                contracting_entity_name VARCHAR(300),
                sphere VARCHAR(20),
                winner_cnpj VARCHAR(20),
                winner_name VARCHAR(300),
                object_description TEXT,
                value_brl NUMERIC,
                state_code VARCHAR(2),
                municipality_code VARCHAR(10),
                l2_id INTEGER REFERENCES admin_level_2(id),
                published_date DATE,
                source VARCHAR(50),
                pncp_control_number VARCHAR(100),
                modality VARCHAR(100),
                status VARCHAR(100),
                UNIQUE(pncp_control_number)
            )
        """)
        # Add columns if upgrading from old schema
        for col, coldef in [
            ("pncp_control_number", "VARCHAR(100)"),
            ("modality", "VARCHAR(100)"),
            ("status", "VARCHAR(100)"),
        ]:
            try:
                cur.execute("SAVEPOINT alter_sp")
                cur.execute(f"""
                    ALTER TABLE government_contracts ADD COLUMN IF NOT EXISTS {col} {coldef}
                """)
                cur.execute("RELEASE SAVEPOINT alter_sp")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT alter_sp")
        conn.commit()

        # Check if we have recent data (within last 1 day)
        cur.execute("""
            SELECT MAX(published_date) FROM government_contracts
            WHERE source = 'pncp'
        """)
        latest = cur.fetchone()[0]
        cur.close()
        conn.close()

        if not latest:
            return True
        return (datetime.utcnow().date() - latest).days >= 1

    def download(self) -> list[dict]:
        """Fetch telecom-related government contracts from the PNCP publicacao API.

        Iterates over modality codes and monthly date windows.  For each
        (modality, month) pair, cycles through SEARCH_KEYWORDS as the q=
        parameter and paginates through all available pages.  Applies local
        keyword filtering on objetoCompra and deduplicates by
        numeroControlePNCP.

        Raises RuntimeError if the API is unreachable or returns no telecom contracts.
        """
        end_date = datetime.utcnow().date()
        start_date = end_date - timedelta(days=365)
        months = _month_ranges(start_date, end_date)

        all_contracts = []
        seen_control_numbers = set()
        total_api_calls = 0
        total_scanned = 0
        errors = []

        with PipelineHTTPClient(timeout=120) as http:
            for modality_code in MODALITY_CODES:
                modality_contracts = 0
                for data_inicial, data_final in months:
                    # Cycle through keywords as server-side hints.
                    # The API doesn't reliably filter on q=, so results overlap
                    # heavily between keywords.  We deduplicate via control number.
                    for keyword in SEARCH_KEYWORDS:
                        try:
                            contracts, scanned, calls = self._fetch_chunk(
                                http,
                                modality_code,
                                data_inicial,
                                data_final,
                                keyword,
                                seen_control_numbers,
                            )
                            all_contracts.extend(contracts)
                            total_api_calls += calls
                            total_scanned += scanned
                            modality_contracts += len(contracts)
                            if contracts:
                                logger.info(
                                    f"Modality {modality_code}, {data_inicial}-{data_final}, "
                                    f"q='{keyword}': {len(contracts)} new telecom contracts "
                                    f"(scanned {scanned})"
                                )
                        except Exception as e:
                            msg = (
                                f"modality={modality_code}, "
                                f"{data_inicial}-{data_final}, "
                                f"q='{keyword}': {e}"
                            )
                            logger.warning(f"PNCP chunk failed: {msg}")
                            errors.append(msg)

                logger.info(
                    f"Modality {modality_code} complete: {modality_contracts} telecom contracts"
                )

        if not all_contracts:
            error_detail = "; ".join(errors[:10]) if errors else "No telecom results matched"
            raise RuntimeError(
                f"PNCP API returned no telecom contracts for the last 12 months. "
                f"Scanned {total_scanned} total records across {total_api_calls} API calls. "
                f"Errors ({len(errors)} total): {error_detail}"
            )

        logger.info(
            f"Total PNCP telecom contracts: {len(all_contracts)} "
            f"(scanned {total_scanned} records in {total_api_calls} API calls, "
            f"{len(MODALITY_CODES)} modalities x {len(months)} months)"
        )
        return all_contracts

    def _fetch_chunk(
        self,
        http: PipelineHTTPClient,
        modality_code: str,
        data_inicial: str,
        data_final: str,
        keyword: str,
        seen_control_numbers: set,
    ) -> tuple[list[dict], int, int]:
        """Paginate through one (modality, date range, keyword) combination.

        Returns (telecom_contracts, total_scanned, api_call_count).
        """
        contracts = []
        scanned = 0
        page = 1
        api_calls = 0

        while page <= MAX_PAGES:
            params = {
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": modality_code,
                "pagina": page,
                "q": keyword,
            }

            try:
                data = http.get_json(PNCP_BASE_URL, params=params)
                api_calls += 1
            except Exception as e:
                if page == 1:
                    raise
                logger.debug(
                    f"PNCP page {page} failed for modality={modality_code}, "
                    f"q='{keyword}': {e}. Stopping."
                )
                break

            if not isinstance(data, dict):
                break

            items = data.get("data", [])
            if not isinstance(items, list) or not items:
                break

            total_paginas = data.get("totalPaginas") or 0

            for item in items:
                scanned += 1

                # Local keyword filtering on objetoCompra
                objeto = item.get("objetoCompra", "") or ""
                if not _is_telecom(objeto):
                    continue

                # Deduplicate by control number
                control_number = item.get("numeroControlePNCP", "")
                if not control_number:
                    orgao = item.get("orgaoEntidade", {}) or {}
                    control_number = (
                        f"{orgao.get('cnpj', '')}|"
                        f"{item.get('dataPublicacaoPncp', '')}|"
                        f"{item.get('valorTotalEstimado', '')}"
                    )

                if control_number in seen_control_numbers:
                    continue
                seen_control_numbers.add(control_number)
                contracts.append(item)

            # Stop if we've reached the last page
            if total_paginas and page >= total_paginas:
                break

            page += 1
            time.sleep(REQUEST_DELAY)

        return contracts, scanned, api_calls

    def validate_raw(self, data: list[dict]) -> None:
        """Validate that we have contract data to process."""
        if not data:
            raise ValueError("No government contract data returned from PNCP API")

        sample = data[0]
        if not isinstance(sample, dict):
            raise ValueError(f"Expected dict records, got {type(sample)}")

        # Verify records have the expected PNCP structure
        has_orgao = sum(1 for r in data[:100] if r.get("orgaoEntidade"))
        if has_orgao == 0:
            raise ValueError(
                "None of the first 100 records have 'orgaoEntidade' field. "
                "PNCP API response format may have changed."
            )

        logger.info(f"Validated {len(data)} government contract records from PNCP")

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Normalize PNCP API responses into government_contracts schema.

        Maps PNCP publicacao field names to our schema, extracts municipality
        IBGE codes from unidadeOrgao.codigoIbge, and resolves to l2_id.
        """
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_l2 = {}
        for code, l2_id in cur.fetchall():
            code_to_l2[str(code)] = l2_id
            # Also store 6-digit version (without IBGE check digit)
            if code and len(str(code)) == 7:
                code_to_l2[str(code)[:6]] = l2_id
        cur.close()
        conn.close()

        rows = []
        skipped_no_value = 0
        resolved_l2 = 0

        for record in raw_data:
            orgao = record.get("orgaoEntidade", {}) or {}
            unidade = record.get("unidadeOrgao", {}) or {}

            # Contracting entity
            entity_cnpj = str(orgao.get("cnpj", "") or "").strip()
            entity_name = str(orgao.get("razaoSocial", "") or "").strip()

            # Sphere (government level)
            esfera_id = str(orgao.get("esferaId", "") or "").strip()
            sphere = SPHERE_MAP.get(esfera_id, esfera_id.lower() if esfera_id else "")

            # Object description
            description = str(record.get("objetoCompra", "") or "").strip()

            # Value: prefer homologado (actual awarded), fall back to estimado
            value_raw = record.get("valorTotalHomologado") or record.get("valorTotalEstimado")
            try:
                value_brl = float(value_raw) if value_raw is not None else 0
            except (ValueError, TypeError):
                value_brl = 0

            if value_brl <= 0:
                skipped_no_value += 1
                continue

            # Location from unidadeOrgao
            state_code = str(unidade.get("ufSigla", "") or "").strip()[:2]
            municipality_code = str(unidade.get("codigoIbge", "") or "").strip()

            # Resolve l2_id from IBGE code
            l2_id = None
            if municipality_code:
                l2_id = code_to_l2.get(municipality_code)
                if not l2_id and len(municipality_code) == 7:
                    l2_id = code_to_l2.get(municipality_code[:6])
                if l2_id:
                    resolved_l2 += 1

            # Published date
            date_raw = str(record.get("dataPublicacaoPncp", "") or "").strip()
            published_date = None
            if date_raw:
                try:
                    published_date = datetime.strptime(date_raw[:10], "%Y-%m-%d").date()
                except (ValueError, TypeError, IndexError):
                    pass

            # Additional PNCP metadata
            control_number = str(record.get("numeroControlePNCP", "") or "").strip()
            modality = str(record.get("modalidadeNome", "") or "").strip()
            status = str(record.get("situacaoCompraNome", "") or "").strip()

            rows.append({
                "contracting_entity_cnpj": entity_cnpj or None,
                "contracting_entity_name": entity_name[:300] if entity_name else None,
                "sphere": sphere[:20] if sphere else None,
                "winner_cnpj": None,  # Not in publicacao listing
                "winner_name": None,  # Not in publicacao listing
                "object_description": description or None,
                "value_brl": value_brl,
                "state_code": state_code or None,
                "municipality_code": municipality_code or None,
                "l2_id": l2_id,
                "published_date": published_date,
                "source": "pncp",
                "pncp_control_number": control_number or None,
                "modality": modality[:100] if modality else None,
                "status": status[:100] if status else None,
            })

        self.rows_processed = len(rows)
        logger.info(
            f"Transformed {len(rows)} government contract records "
            f"(skipped {skipped_no_value} with no value, "
            f"resolved {resolved_l2} to l2_id)"
        )
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert government contracts into the database."""
        if data.empty:
            logger.warning("No government contract data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Ensure table exists (check_for_updates may be skipped with force=True)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS government_contracts (
                id SERIAL PRIMARY KEY,
                contracting_entity_cnpj VARCHAR(20),
                contracting_entity_name VARCHAR(300),
                sphere VARCHAR(20),
                winner_cnpj VARCHAR(20),
                winner_name VARCHAR(300),
                object_description TEXT,
                value_brl NUMERIC,
                state_code VARCHAR(2),
                municipality_code VARCHAR(10),
                l2_id INTEGER REFERENCES admin_level_2(id),
                published_date DATE,
                source VARCHAR(50),
                pncp_control_number VARCHAR(100),
                modality VARCHAR(100),
                status VARCHAR(100),
                UNIQUE(pncp_control_number)
            )
        """)
        conn.commit()

        loaded = 0
        skipped = 0
        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO government_contracts
                    (contracting_entity_cnpj, contracting_entity_name, sphere,
                     winner_cnpj, winner_name, object_description, value_brl,
                     state_code, municipality_code, l2_id, published_date, source,
                     pncp_control_number, modality, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (pncp_control_number) DO UPDATE SET
                        contracting_entity_name = EXCLUDED.contracting_entity_name,
                        object_description = EXCLUDED.object_description,
                        value_brl = EXCLUDED.value_brl,
                        l2_id = EXCLUDED.l2_id,
                        status = EXCLUDED.status,
                        source = EXCLUDED.source
                """, (
                    row["contracting_entity_cnpj"],
                    row["contracting_entity_name"],
                    row["sphere"],
                    row["winner_cnpj"],
                    row["winner_name"],
                    row["object_description"],
                    row["value_brl"],
                    row["state_code"],
                    row["municipality_code"],
                    row["l2_id"],
                    row["published_date"],
                    row["source"],
                    row["pncp_control_number"],
                    row["modality"],
                    row["status"],
                ))
                cur.execute("RELEASE SAVEPOINT row_sp")
                loaded += 1
            except Exception as e:
                logger.debug(f"Skipping contract row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                skipped += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} government contract records ({skipped} skipped)")
