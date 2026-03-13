"""Portal da Transparência — FUST/telecom federal spending pipeline.

Source: CGU bulk CSV downloads (no API key required)
URL:    https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/despesas-execucao/{YYYYMM}_Despesas.zip
Format: Semicolon-delimited CSV, ISO-8859-1 encoded, inside ZIP archive

Downloads monthly federal expenditure bulk files and filters for
telecom-related spending:
  - Órgão Superior 41000 (Ministério das Comunicações)
  - Subfunção 722 (Telecomunicações)

This captures FUST, FUNTTEL, ANATEL, Telebras, and all federal
telecom infrastructure spending (Conecta Brasil, Wi-Fi Brasil, etc.).

Each monthly ZIP is ~5MB compressed (~40MB uncompressed CSV).

Schedule: Weekly (Sunday 04:30 UTC)
Requires: nothing (public open data, no API key)
Optional: TRANSPARENCIA_API_KEY (reserved for future use, not required)
"""
import csv
import io
import logging
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

# Bulk CSV download URL pattern
BULK_CSV_URL = (
    "https://dadosabertos-download.cgu.gov.br"
    "/PortalDaTransparencia/saida/despesas-execucao/{yyyymm}_Despesas.zip"
)

# Months to download: 2024-01 through 2025-03 (15 months)
START_YEAR = 2024
START_MONTH = 1
END_YEAR = 2025
END_MONTH = 3

# Filter criteria: rows matching ANY of these are kept
FILTER_ORG_SUPERIOR = "41000"  # Ministério das Comunicações
FILTER_SUBFUNCAO_CODE = "722"  # Telecomunicações

# CSV column indices (from the bulk file header)
COL_ANO_MES = 0           # "Ano e mês do lançamento" — format "YYYY/MM"
COL_ORG_SUP_CODE = 1      # "Código Órgão Superior"
COL_ORG_SUP_NAME = 2      # "Nome Órgão Superior"
COL_ORG_SUB_CODE = 3      # "Código Órgão Subordinado"
COL_ORG_SUB_NAME = 4      # "Nome Órgão Subordinado"
COL_SUBFUNCAO_CODE = 13   # "Código Subfução"
COL_SUBFUNCAO_NAME = 14   # "Nome Subfunção"
COL_PROGRAMA_CODE = 15    # "Código Programa Orçamentário"
COL_PROGRAMA_NAME = 16    # "Nome Programa Orçamentário"
COL_ACAO_CODE = 17        # "Código Ação"
COL_ACAO_NAME = 18        # "Nome Ação"
COL_UF = 23               # "UF"
COL_EMPENHADO = 41        # "Valor Empenhado (R$)"
COL_LIQUIDADO = 42        # "Valor Liquidado (R$)"
COL_PAGO = 43             # "Valor Pago (R$)"

# Minimum columns a valid row must have
MIN_COLS = 44


def _generate_month_range(
    start_year: int, start_month: int, end_year: int, end_month: int
) -> list[tuple[int, int]]:
    """Generate list of (year, month) tuples for the date range."""
    months = []
    y, m = start_year, start_month
    while (y, m) <= (end_year, end_month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _parse_brazilian_number(value: str) -> float:
    """Parse Brazilian number format: '1.234.567,89' -> 1234567.89

    Also handles:
      - Empty/whitespace -> 0.0
      - Already decimal format -> float
      - Negative values with parentheses -> negative float
    """
    if not value or not value.strip():
        return 0.0
    s = value.strip().strip('"')
    # Handle parenthesized negatives: (1.234,56) -> -1234.56
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    # Remove thousand separators (dots) and convert decimal comma
    s = s.replace(".", "").replace(",", ".")
    try:
        result = float(s)
        return -result if negative else result
    except (ValueError, TypeError):
        return 0.0


class TransparenciaFustPipeline(BasePipeline):
    """Ingest telecom federal spending from Portal da Transparência bulk CSVs.

    Downloads monthly ZIP files containing all federal expenditure, then
    filters for telecom-related rows (Ministério das Comunicações or
    subfunção Telecomunicações). Maps to fust_spending table.

    No API key required — uses publicly available bulk CSV downloads.
    """

    def __init__(self):
        super().__init__("transparencia_fust")
        # Keep optional API key reference for future use
        self._api_key = os.getenv("TRANSPARENCIA_API_KEY", "")

    def check_for_updates(self) -> bool:
        """Check if we need to download more data.

        Returns True if:
          - Table has fewer rows than expected (< 50 per covered month)
          - Any month in the target range has no data yet
        """
        conn = self._get_connection()
        cur = conn.cursor()

        # Ensure table exists with the correct schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fust_spending (
                id SERIAL PRIMARY KEY,
                year INTEGER,
                month INTEGER,
                org_code VARCHAR(10),
                org_name VARCHAR(200),
                program_code VARCHAR(20),
                action_code VARCHAR(20),
                value_committed_brl NUMERIC,
                value_paid_brl NUMERIC,
                creditor_cnpj VARCHAR(20),
                creditor_name VARCHAR(300),
                state_code VARCHAR(2),
                source VARCHAR(50)
            )
        """)
        conn.commit()

        # Check how many months have data
        cur.execute("""
            SELECT COUNT(DISTINCT (year, month))
            FROM fust_spending
            WHERE source = 'transparencia_csv'
        """)
        months_with_data = cur.fetchone()[0]
        cur.close()
        conn.close()

        target_months = len(
            _generate_month_range(START_YEAR, START_MONTH, END_YEAR, END_MONTH)
        )
        if months_with_data < target_months:
            logger.info(
                f"Have data for {months_with_data}/{target_months} months — "
                f"update needed"
            )
            return True

        logger.info(
            f"All {target_months} months already loaded — no update needed"
        )
        return False

    def download(self) -> list[dict]:
        """Download monthly ZIP files and extract telecom spending rows.

        For each month in the target range:
          1. Download the ZIP file (with resume support + disk cache)
          2. Extract the CSV (ISO-8859-1, semicolon-delimited)
          3. Filter rows where org_superior=41000 OR subfuncao=722
          4. Parse Brazilian number format for financial values
          5. Return list of dicts ready for transform
        """
        months = _generate_month_range(
            START_YEAR, START_MONTH, END_YEAR, END_MONTH
        )
        all_records: list[dict] = []

        with PipelineHTTPClient(timeout=300) as http:
            for year, month in months:
                yyyymm = f"{year}{month:02d}"
                url = BULK_CSV_URL.format(yyyymm=yyyymm)
                zip_filename = f"{yyyymm}_Despesas.zip"
                cache_path = get_cache_path(zip_filename)

                try:
                    logger.info(f"Downloading {url} ...")
                    http.download_file(url, cache_path, resume=True)
                    records = self._extract_telecom_rows(
                        cache_path, year, month
                    )
                    all_records.extend(records)
                    logger.info(
                        f"{yyyymm}: {len(records)} telecom spending rows"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to process {yyyymm}: {e}"
                    )
                    continue

        if not all_records:
            raise RuntimeError(
                "No telecom spending data extracted from any month. "
                "Check network connectivity and CGU download availability."
            )

        logger.info(
            f"Total telecom spending records extracted: {len(all_records)}"
        )
        return all_records

    def _extract_telecom_rows(
        self, zip_path: Path, year: int, month: int
    ) -> list[dict]:
        """Extract telecom-related rows from a monthly expenditure ZIP.

        Filters for:
          - Código Órgão Superior = 41000 (Min. Comunicações)
          - Código Subfunção = 722 (Telecomunicações)

        Skips rows where all financial values are zero.
        """
        records = []

        with zipfile.ZipFile(zip_path) as zf:
            csv_files = [
                n for n in zf.namelist()
                if n.lower().endswith(".csv")
                and "_colunas" not in n.lower()
            ]
            if not csv_files:
                raise ValueError(
                    f"No CSV found in {zip_path}. Contents: {zf.namelist()}"
                )

            csv_name = csv_files[0]
            logger.info(
                f"Extracting {csv_name} "
                f"({zf.getinfo(csv_name).file_size:,} bytes)"
            )

            with zf.open(csv_name) as f:
                raw = f.read()

            # Decode: try UTF-8-sig first, then ISO-8859-1
            for enc in ("utf-8-sig", "iso-8859-1"):
                try:
                    text = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = raw.decode("iso-8859-1", errors="replace")

            reader = csv.reader(
                io.StringIO(text), delimiter=";", quotechar='"'
            )
            # Skip header
            try:
                next(reader)
            except StopIteration:
                return records

            for row in reader:
                if len(row) < MIN_COLS:
                    continue

                org_sup_code = row[COL_ORG_SUP_CODE].strip()
                subfuncao_code = row[COL_SUBFUNCAO_CODE].strip()

                # Filter: Ministério das Comunicações OR Telecomunicações
                if (
                    org_sup_code != FILTER_ORG_SUPERIOR
                    and subfuncao_code != FILTER_SUBFUNCAO_CODE
                ):
                    continue

                empenhado = _parse_brazilian_number(row[COL_EMPENHADO])
                pago = _parse_brazilian_number(row[COL_PAGO])

                # Skip rows with zero financial impact
                if empenhado == 0.0 and pago == 0.0:
                    liquidado = _parse_brazilian_number(row[COL_LIQUIDADO])
                    if liquidado == 0.0:
                        continue

                # Parse year/month from the CSV date column (format "YYYY/MM")
                ano_mes = row[COL_ANO_MES].strip().strip('"')
                try:
                    parts = ano_mes.split("/")
                    csv_year = int(parts[0])
                    csv_month = int(parts[1])
                except (ValueError, IndexError):
                    csv_year = year
                    csv_month = month

                records.append({
                    "year": csv_year,
                    "month": csv_month,
                    "org_sup_code": org_sup_code,
                    "org_sup_name": row[COL_ORG_SUP_NAME].strip(),
                    "org_sub_code": row[COL_ORG_SUB_CODE].strip(),
                    "org_sub_name": row[COL_ORG_SUB_NAME].strip(),
                    "subfuncao_code": subfuncao_code,
                    "subfuncao_name": row[COL_SUBFUNCAO_NAME].strip(),
                    "programa_code": row[COL_PROGRAMA_CODE].strip(),
                    "programa_name": row[COL_PROGRAMA_NAME].strip(),
                    "acao_code": row[COL_ACAO_CODE].strip(),
                    "acao_name": row[COL_ACAO_NAME].strip(),
                    "uf": row[COL_UF].strip(),
                    "empenhado": empenhado,
                    "pago": pago,
                })

        return records

    def validate_raw(self, data: list[dict]) -> None:
        """Validate that we have reasonable telecom spending data."""
        if not data:
            raise ValueError("No telecom spending data extracted")

        # Sanity checks
        years = {r["year"] for r in data}
        months_covered = {(r["year"], r["month"]) for r in data}
        total_committed = sum(r["empenhado"] for r in data)

        logger.info(
            f"Validation: {len(data)} records, "
            f"years={sorted(years)}, "
            f"{len(months_covered)} months covered, "
            f"total committed=R$ {total_committed:,.2f}"
        )

        if total_committed < 0:
            raise ValueError(
                f"Total committed value is negative (R$ {total_committed:,.2f})"
                " — likely a parsing error"
            )

    def transform(self, raw_data: list[dict]) -> pd.DataFrame:
        """Map extracted CSV rows to fust_spending table schema.

        Builds org_code from subordinate org (more specific than superior),
        and org_name as a descriptive combination.
        """
        rows = []
        for rec in raw_data:
            # Use subordinate org code (more granular) as the primary org_code
            org_code = rec["org_sub_code"][:10] if rec["org_sub_code"] else rec["org_sup_code"][:10]

            # Build descriptive org_name
            org_name = rec["org_sub_name"] or rec["org_sup_name"]
            if org_name:
                org_name = org_name[:200]

            # Program and action codes
            programa = rec["programa_code"][:20] if rec["programa_code"] else None
            acao = rec["acao_code"][:20] if rec["acao_code"] else None

            # UF (state code), may be empty
            uf = rec["uf"][:2] if rec["uf"] else None

            rows.append({
                "year": rec["year"],
                "month": rec["month"],
                "org_code": org_code,
                "org_name": org_name,
                "program_code": programa,
                "action_code": acao,
                "value_committed_brl": rec["empenhado"],
                "value_paid_brl": rec["pago"],
                "creditor_cnpj": None,    # Not in bulk execution CSV
                "creditor_name": None,    # Not in bulk execution CSV
                "state_code": uf,
                "source": "transparencia_csv",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} telecom spending records")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Load telecom spending data into fust_spending table.

        Uses ON CONFLICT to upsert, updating financial values on duplicates.
        """
        if data.empty:
            logger.warning("No telecom spending data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Ensure the wider unique constraint exists
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'fust_spending_unique_row'
                ) THEN
                    -- Drop old narrow constraint if it exists
                    ALTER TABLE fust_spending
                        DROP CONSTRAINT IF EXISTS
                        fust_spending_year_month_org_code_creditor_cnpj_key;
                    -- Add wider constraint
                    ALTER TABLE fust_spending
                        ADD CONSTRAINT fust_spending_unique_row
                        UNIQUE (year, month, org_code, program_code,
                                action_code, creditor_cnpj, state_code);
                END IF;
            END $$;
        """)
        conn.commit()

        loaded = 0
        skipped = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO fust_spending
                        (year, month, org_code, org_name, program_code,
                         action_code, value_committed_brl, value_paid_brl,
                         creditor_cnpj, creditor_name, state_code, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT
                        (year, month, org_code, program_code,
                         action_code, creditor_cnpj, state_code)
                    DO UPDATE SET
                        value_committed_brl = EXCLUDED.value_committed_brl,
                        value_paid_brl = EXCLUDED.value_paid_brl,
                        org_name = EXCLUDED.org_name
                """, (
                    row["year"],
                    row["month"],
                    row["org_code"],
                    row["org_name"],
                    row["program_code"],
                    row["action_code"],
                    row["value_committed_brl"],
                    row["value_paid_brl"],
                    row["creditor_cnpj"],
                    row["creditor_name"],
                    row["state_code"],
                    row["source"],
                ))
                cur.execute("RELEASE SAVEPOINT row_sp")
                loaded += 1
            except Exception as e:
                logger.debug(f"Skipping row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                skipped += 1

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(
            f"Loaded {loaded} telecom spending records "
            f"(skipped {skipped})"
        )

    def post_load(self) -> None:
        """Log summary statistics after loading."""
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(DISTINCT (year, month)) AS months,
                COUNT(DISTINCT org_code) AS orgs,
                SUM(value_committed_brl) AS total_committed,
                SUM(value_paid_brl) AS total_paid
            FROM fust_spending
            WHERE source = 'transparencia_csv'
        """)
        row = cur.fetchone()
        logger.info(
            f"fust_spending summary: {row[0]} rows, {row[1]} months, "
            f"{row[2]} orgs, committed=R$ {row[3]:,.2f}, "
            f"paid=R$ {row[4]:,.2f}"
        )

        # Top orgs by spending
        cur.execute("""
            SELECT org_name, SUM(value_committed_brl) AS total
            FROM fust_spending
            WHERE source = 'transparencia_csv'
            GROUP BY org_name
            ORDER BY total DESC
            LIMIT 5
        """)
        logger.info("Top 5 orgs by committed value:")
        for org_name, total in cur.fetchall():
            logger.info(f"  {org_name}: R$ {total:,.2f}")

        cur.close()
        conn.close()


# Backward-compatible alias (old class name used in __init__.py and cron)
TransparenciaFUSTPipeline = TransparenciaFustPipeline
