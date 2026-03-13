"""PGFN Divida Ativa (Tax Debt) pipeline — ISP tax compliance intelligence.

Source: Procuradoria-Geral da Fazenda Nacional (PGFN) Open Data
URL: https://dadosabertos.pgfn.gov.br/{year}_trimestre_{quarter}/
Format: ZIP containing multiple CSV files (semicolon-separated, Latin-1 or UTF-8)
Key fields: CPF_CNPJ, NOME_DEVEDOR, VALOR_CONSOLIDADO, SITUACAO_INSCRICAO,
            UF_DEVEDOR, NUMERO_INSCRICAO, INDICADOR_AJUIZADO, DATA_INSCRICAO

PGFN publishes quarterly snapshots of all active federal tax debts
(Divida Ativa da Uniao). Three debt types are available:
  - Nao_Previdenciario: non-social-security tax debts (~1.2 GB ZIP)
  - Previdenciario: social security tax debts (~90 MB ZIP)
  - FGTS: employment guarantee fund debts (~17 MB ZIP)

This pipeline downloads all three ZIP files for the latest available quarter,
streams through each CSV line by line to filter only records whose CNPJ
matches a known ISP provider, and upserts matched records into the
provider_tax_debts table.

The streaming approach is critical because the Nao_Previdenciario file
uncompresses to several GB. We never load the full CSV into memory.

Schedule: Monthly (1st at 05:45 UTC)
"""
import csv
import io
import logging
import re
import shutil
import subprocess
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

PGFN_BASE_URL = "https://dadosabertos.pgfn.gov.br"

# Debt type -> ZIP filename mapping
DEBT_TYPES = {
    "FGTS": "Dados_abertos_FGTS.zip",
    "PREVIDENCIARIO": "Dados_abertos_Previdenciario.zip",
    "NAO_PREVIDENCIARIO": "Dados_abertos_Nao_Previdenciario.zip",
}

# Expected CSV columns (semicolon-separated)
EXPECTED_COLUMNS = [
    "CPF_CNPJ", "TIPO_PESSOA", "TIPO_DEVEDOR", "NOME_DEVEDOR",
    "UF_DEVEDOR", "UNIDADE_RESPONSAVEL", "ENTIDADE_RESPONSAVEL",
    "UNIDADE_INSCRICAO", "NUMERO_INSCRICAO", "TIPO_SITUACAO_INSCRICAO",
    "SITUACAO_INSCRICAO", "RECEITA_PRINCIPAL", "DATA_INSCRICAO",
    "INDICADOR_AJUIZADO", "VALOR_CONSOLIDADO",
]

# Regex to strip CNPJ formatting: 10.496.760/0001-95 -> 10496760000195
CNPJ_STRIP_RE = re.compile(r"[.\-/]")


def strip_cnpj(raw: str) -> str:
    """Remove formatting from a CNPJ string, keeping only digits."""
    return CNPJ_STRIP_RE.sub("", raw.strip())


def find_latest_quarter() -> str:
    """Determine the latest available quarter directory on PGFN.

    Probes from the current date backwards until a valid directory is found.
    Returns a string like '2025_trimestre_04'.
    """
    now = datetime.utcnow()
    # Generate candidates from current year backwards
    candidates = []
    for year in range(now.year, now.year - 3, -1):
        for quarter in range(4, 0, -1):
            candidates.append(f"{year}_trimestre_{quarter:02d}")

    with PipelineHTTPClient(timeout=30) as http:
        for candidate in candidates:
            url = f"{PGFN_BASE_URL}/{candidate}/"
            try:
                resp = http._retry_request("GET", url)
                if resp.status_code == 200 and "Dados_abertos" in resp.text:
                    logger.info(f"Latest PGFN quarter: {candidate}")
                    return candidate
            except Exception:
                continue

    raise RuntimeError("Could not find any available PGFN quarter directory")


class PGFNDividaAtivaPipeline(BasePipeline):
    """Ingest PGFN tax debt data and match to ISP providers.

    Downloads three ZIP archives (FGTS, Previdenciario, Nao_Previdenciario)
    from the latest available quarter. Each ZIP contains multiple CSV files
    split by region. We stream through each CSV and filter for CNPJs matching
    our providers table, then upsert into provider_tax_debts.

    The Nao_Previdenciario archive is over 1 GB, so we stream through the
    ZIPs rather than loading entire CSVs into memory.
    """

    def __init__(self):
        super().__init__("pgfn_divida_ativa")
        self._quarter: Optional[str] = None
        self._provider_cnpjs: dict[str, int] = {}  # cnpj_digits -> provider_id

    def check_for_updates(self) -> bool:
        """Check if we should run by looking at current data freshness."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Check how many records we have and their freshness
        cur.execute("SELECT COUNT(*), MAX(updated_at) FROM provider_tax_debts")
        count, last_update = cur.fetchone()
        cur.close()
        conn.close()

        if count == 0:
            logger.info("No PGFN data yet — will download")
            return True

        # Re-run if data is older than 80 days (quarterly updates)
        if last_update:
            age_days = (datetime.utcnow() - last_update).days
            if age_days > 80:
                logger.info(f"PGFN data is {age_days} days old — will refresh")
                return True
            logger.info(f"PGFN data is {age_days} days old — still fresh")
            return False

        return True

    def download(self) -> dict[str, Path]:
        """Download all three PGFN ZIP files for the latest quarter.

        Returns a dict mapping debt_type -> local ZIP file path.
        """
        self._quarter = find_latest_quarter()
        downloaded = {}

        with PipelineHTTPClient(timeout=600) as http:
            for debt_type, filename in DEBT_TYPES.items():
                url = f"{PGFN_BASE_URL}/{self._quarter}/{filename}"
                cache_path = get_cache_path(f"pgfn_{self._quarter}_{filename}")

                logger.info(f"Downloading {debt_type}: {url}")
                try:
                    local_path = http.download_file(url, cache_path, resume=True)
                    downloaded[debt_type] = local_path
                    logger.info(
                        f"Downloaded {debt_type}: "
                        f"{local_path.stat().st_size / 1024 / 1024:.1f} MB"
                    )
                except Exception as e:
                    logger.error(f"Failed to download {debt_type}: {e}")
                    # Continue with other types — partial results are still valuable

        if not downloaded:
            raise RuntimeError(
                f"Failed to download any PGFN ZIP files from {self._quarter}"
            )

        return downloaded

    def validate_raw(self, data: dict[str, Path]) -> None:
        """Validate that downloaded ZIPs are valid and contain CSVs."""
        for debt_type, path in data.items():
            if not path.exists():
                raise ValueError(f"ZIP file missing for {debt_type}: {path}")
            try:
                with zipfile.ZipFile(path) as zf:
                    csv_files = [
                        n for n in zf.namelist()
                        if n.lower().endswith(".csv")
                    ]
                    if not csv_files:
                        raise ValueError(
                            f"No CSV files in {debt_type} ZIP. "
                            f"Contents: {zf.namelist()}"
                        )
                    logger.info(
                        f"{debt_type}: {len(csv_files)} CSV files in ZIP"
                    )
            except zipfile.BadZipFile:
                raise ValueError(f"Corrupt ZIP file for {debt_type}: {path}")

    def _load_provider_cnpjs(self) -> dict[str, int]:
        """Load all provider CNPJs from the database into a lookup dict.

        Returns a mapping of stripped CNPJ (digits only) -> provider_id.
        """
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT national_id, id FROM providers "
            "WHERE national_id IS NOT NULL AND LENGTH(national_id) >= 11"
        )
        result = {}
        for national_id, provider_id in cur.fetchall():
            # Providers may already have stripped CNPJs, but strip again to be safe
            clean = strip_cnpj(national_id)
            if len(clean) >= 11:  # Valid CNPJ (14) or CPF (11)
                result[clean] = provider_id
        cur.close()
        conn.close()
        logger.info(f"Loaded {len(result)} provider CNPJs for matching")
        return result

    def transform(self, raw_data: dict[str, Path]) -> list[dict]:
        """Stream through all ZIPs and extract rows matching provider CNPJs.

        This is the critical performance section. For the 1.2 GB
        Nao_Previdenciario file, we:
        1. Open the ZIP without extracting to disk
        2. For each CSV inside, read line by line
        3. Parse only the CPF_CNPJ column first
        4. If it matches a provider, parse the full row

        This keeps memory usage to O(matched_rows) rather than O(total_rows).

        Some PGFN ZIPs have corrupted headers (extra bytes at the start) that
        Python's zipfile module cannot handle. In that case, we fall back to
        the system `unzip` command which is more lenient.
        """
        self._provider_cnpjs = self._load_provider_cnpjs()
        matched_rows = []
        total_scanned = 0

        for debt_type, zip_path in raw_data.items():
            logger.info(f"Processing {debt_type} from {zip_path}")
            type_scanned = 0
            type_matched = 0

            try:
                with zipfile.ZipFile(zip_path) as zf:
                    csv_files = [
                        n for n in zf.namelist()
                        if n.lower().endswith(".csv")
                    ]
                    # Test that we can actually open the first CSV
                    # (catches "Bad magic number" on corrupt ZIPs early)
                    if csv_files:
                        with zf.open(csv_files[0]) as test_f:
                            test_f.read(1)

                    for csv_name in csv_files:
                        logger.info(
                            f"  Scanning {csv_name} "
                            f"({zf.getinfo(csv_name).file_size:,} bytes)"
                        )
                        scanned, matched = self._process_csv_in_zip(
                            zf, csv_name, debt_type, matched_rows
                        )
                        type_scanned += scanned
                        type_matched += matched

            except Exception as e:
                logger.warning(
                    f"Python zipfile failed for {debt_type}: {e}. "
                    f"Falling back to system unzip..."
                )
                try:
                    fallback_scanned, fallback_matched = (
                        self._extract_and_process_corrupt_zip(
                            zip_path, debt_type, matched_rows
                        )
                    )
                    type_scanned += fallback_scanned
                    type_matched += fallback_matched
                except Exception as e2:
                    logger.error(
                        f"Fallback also failed for {debt_type}: {e2}"
                    )
                    continue

            total_scanned += type_scanned
            logger.info(
                f"{debt_type}: scanned {type_scanned:,} rows, "
                f"matched {type_matched:,} ISP records"
            )

        self.rows_processed = total_scanned
        logger.info(
            f"Total: scanned {total_scanned:,} rows, "
            f"matched {len(matched_rows):,} ISP tax debt records"
        )
        return matched_rows

    def _process_csv_in_zip(
        self,
        zf: zipfile.ZipFile,
        csv_name: str,
        debt_type: str,
        matched_rows: list[dict],
    ) -> tuple[int, int]:
        """Process a single CSV file inside a ZIP archive.

        Streams line by line to minimize memory usage.
        Returns (scanned_count, matched_count).
        """
        scanned = 0
        matched = 0

        with zf.open(csv_name) as f:
            # Wrap in TextIOWrapper for line-by-line reading
            # Try UTF-8 first, fall back to latin-1
            raw_bytes = f.read()

        # Decode the full file content
        for encoding in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = raw_bytes.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            text = raw_bytes.decode("latin-1")

        reader = csv.DictReader(io.StringIO(text), delimiter=";")

        for row in reader:
            scanned += 1
            if scanned % 500_000 == 0:
                logger.info(
                    f"    ...{csv_name}: {scanned:,} rows scanned, "
                    f"{matched:,} matched"
                )

            raw_cnpj = row.get("CPF_CNPJ", "").strip()
            if not raw_cnpj:
                continue

            clean_cnpj = strip_cnpj(raw_cnpj)
            provider_id = self._provider_cnpjs.get(clean_cnpj)
            if provider_id is None:
                continue

            # This CNPJ belongs to a known ISP — extract full record
            matched += 1

            # Parse consolidated value
            valor_raw = row.get("VALOR_CONSOLIDADO", "0").strip()
            try:
                total_consolidated = float(
                    valor_raw.replace(",", ".").replace(" ", "")
                )
            except (ValueError, TypeError):
                total_consolidated = None

            # Parse inscription date
            date_raw = row.get("DATA_INSCRICAO", "").strip()
            inscription_date = None
            for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                try:
                    inscription_date = datetime.strptime(date_raw, fmt).date()
                    break
                except (ValueError, TypeError):
                    continue

            # Parse court action indicator
            ajuizado_raw = row.get("INDICADOR_AJUIZADO", "").strip().upper()
            has_legal_action = ajuizado_raw == "SIM"

            matched_rows.append({
                "provider_id": provider_id,
                "cnpj": clean_cnpj[:20],
                "debtor_name": (
                    row.get("NOME_DEVEDOR", "").strip()[:500] or None
                ),
                "debt_type": debt_type,
                "inscription_number": (
                    row.get("NUMERO_INSCRICAO", "").strip()[:50] or None
                ),
                "total_consolidated": total_consolidated,
                "situation": (
                    row.get("SITUACAO_INSCRICAO", "").strip()[:200] or None
                ),
                "state_code": (
                    row.get("UF_DEVEDOR", "").strip()[:2] or None
                ),
                "has_legal_action": has_legal_action,
                "inscription_date": inscription_date,
            })

        return scanned, matched

    def _extract_and_process_corrupt_zip(
        self,
        zip_path: Path,
        debt_type: str,
        matched_rows: list[dict],
    ) -> tuple[int, int]:
        """Fall back to system unzip for ZIPs with corrupted headers.

        Some PGFN ZIPs (especially Nao_Previdenciario) have extra bytes at
        the start that break Python's zipfile module. The system `unzip`
        command is more lenient and can handle these.

        Extracts one CSV at a time to limit disk usage, processes it,
        then deletes it before extracting the next.
        """
        total_scanned = 0
        total_matched = 0
        tmp_dir = Path(tempfile.mkdtemp(prefix="pgfn_extract_"))

        try:
            # First, list CSV files in the ZIP
            result = subprocess.run(
                ["unzip", "-l", str(zip_path)],
                capture_output=True, text=True, timeout=60,
            )
            csv_files = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.lower().endswith(".csv"):
                    # The filename is the last column
                    parts = line.split()
                    if parts:
                        csv_files.append(parts[-1])

            logger.info(
                f"Corrupt ZIP fallback: found {len(csv_files)} CSV files "
                f"in {zip_path.name}"
            )

            for csv_name in csv_files:
                # Extract just this one CSV
                logger.info(f"  Extracting {csv_name} via system unzip...")
                extract_result = subprocess.run(
                    ["unzip", "-o", "-d", str(tmp_dir), str(zip_path), csv_name],
                    capture_output=True, text=True, timeout=600,
                )
                csv_path = tmp_dir / csv_name
                if not csv_path.exists():
                    # unzip may return code 2 for format warnings but still
                    # extract successfully. Only skip if file is truly missing.
                    logger.error(
                        f"  Extracted file not found: {csv_path} "
                        f"(unzip rc={extract_result.returncode}, "
                        f"stderr={extract_result.stderr[:200]})"
                    )
                    continue
                if extract_result.returncode not in (0, 1, 2):
                    logger.warning(
                        f"  unzip returned code {extract_result.returncode} "
                        f"for {csv_name} but file was extracted"
                    )

                logger.info(
                    f"  Scanning {csv_name} "
                    f"({csv_path.stat().st_size:,} bytes on disk)"
                )
                scanned, matched = self._process_csv_file(
                    csv_path, csv_name, debt_type, matched_rows
                )
                total_scanned += scanned
                total_matched += matched

                # Remove the extracted CSV to free disk space
                csv_path.unlink()

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        return total_scanned, total_matched

    def _process_csv_file(
        self,
        csv_path: Path,
        csv_name: str,
        debt_type: str,
        matched_rows: list[dict],
    ) -> tuple[int, int]:
        """Process a CSV file on disk, streaming line by line.

        Similar to _process_csv_in_zip but reads from an extracted file
        on disk. Uses a streaming approach to handle multi-GB files without
        loading them entirely into memory.
        """
        scanned = 0
        matched = 0

        # Detect encoding from first few KB
        with open(csv_path, "rb") as f:
            sample = f.read(8192)

        encoding = "latin-1"  # safe default
        for enc in ("utf-8-sig", "utf-8"):
            try:
                sample.decode(enc)
                encoding = enc
                break
            except UnicodeDecodeError:
                continue

        with open(csv_path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.DictReader(f, delimiter=";")

            for row in reader:
                scanned += 1
                if scanned % 500_000 == 0:
                    logger.info(
                        f"    ...{csv_name}: {scanned:,} rows scanned, "
                        f"{matched:,} matched"
                    )

                raw_cnpj = row.get("CPF_CNPJ", "").strip()
                if not raw_cnpj:
                    continue

                clean_cnpj = strip_cnpj(raw_cnpj)
                provider_id = self._provider_cnpjs.get(clean_cnpj)
                if provider_id is None:
                    continue

                matched += 1

                valor_raw = row.get("VALOR_CONSOLIDADO", "0").strip()
                try:
                    total_consolidated = float(
                        valor_raw.replace(",", ".").replace(" ", "")
                    )
                except (ValueError, TypeError):
                    total_consolidated = None

                date_raw = row.get("DATA_INSCRICAO", "").strip()
                inscription_date = None
                for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
                    try:
                        inscription_date = datetime.strptime(
                            date_raw, fmt
                        ).date()
                        break
                    except (ValueError, TypeError):
                        continue

                ajuizado_raw = (
                    row.get("INDICADOR_AJUIZADO", "").strip().upper()
                )
                has_legal_action = ajuizado_raw == "SIM"

                matched_rows.append({
                    "provider_id": provider_id,
                    "cnpj": clean_cnpj[:20],
                    "debtor_name": (
                        row.get("NOME_DEVEDOR", "").strip()[:500] or None
                    ),
                    "debt_type": debt_type,
                    "inscription_number": (
                        row.get("NUMERO_INSCRICAO", "").strip()[:50] or None
                    ),
                    "total_consolidated": total_consolidated,
                    "situation": (
                        row.get("SITUACAO_INSCRICAO", "").strip()[:200]
                        or None
                    ),
                    "state_code": (
                        row.get("UF_DEVEDOR", "").strip()[:2] or None
                    ),
                    "has_legal_action": has_legal_action,
                    "inscription_date": inscription_date,
                })

        return scanned, matched

    def load(self, data: list[dict]) -> None:
        """Upsert matched tax debt records into provider_tax_debts.

        Uses inscription_number as the natural key for upserts.
        Clears old data first since PGFN publishes full quarterly snapshots.
        """
        if not data:
            logger.warning("No matching PGFN tax debt records to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Clear existing data — PGFN is a full snapshot, not incremental
        cur.execute("DELETE FROM provider_tax_debts")
        deleted = cur.rowcount
        if deleted:
            logger.info(f"Cleared {deleted} existing tax debt records")
        conn.commit()

        loaded = 0
        skipped = 0
        batch_size = 1000

        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            for row in batch:
                try:
                    cur.execute("SAVEPOINT row_sp")
                    cur.execute("""
                        INSERT INTO provider_tax_debts
                        (provider_id, cnpj, debtor_name, debt_type,
                         inscription_number, total_consolidated, situation,
                         state_code, has_legal_action, inscription_date,
                         updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        row["provider_id"],
                        row["cnpj"],
                        row["debtor_name"],
                        row["debt_type"],
                        row["inscription_number"],
                        row["total_consolidated"],
                        row["situation"],
                        row["state_code"],
                        row["has_legal_action"],
                        row["inscription_date"],
                    ))
                    loaded += 1
                    cur.execute("RELEASE SAVEPOINT row_sp")
                except Exception as e:
                    logger.debug(f"Skipping tax debt row: {e}")
                    cur.execute("ROLLBACK TO SAVEPOINT row_sp")
                    skipped += 1

            conn.commit()
            if (i + batch_size) % 5000 == 0:
                logger.info(f"  Loaded {loaded:,} records so far...")

        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(
            f"Loaded {loaded:,} PGFN tax debt records "
            f"({skipped:,} skipped)"
        )

    def post_load(self) -> None:
        """Log summary statistics after loading."""
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT debt_type, COUNT(*), 
                   SUM(total_consolidated),
                   COUNT(DISTINCT provider_id)
            FROM provider_tax_debts
            GROUP BY debt_type
            ORDER BY debt_type
        """)
        for row in cur.fetchall():
            debt_type, count, total, providers = row
            total_fmt = f"R$ {total:,.2f}" if total else "R$ 0"
            logger.info(
                f"  {debt_type}: {count:,} debts, "
                f"{total_fmt} total, "
                f"{providers:,} providers"
            )

        cur.execute("""
            SELECT COUNT(DISTINCT provider_id), COUNT(*),
                   SUM(total_consolidated)
            FROM provider_tax_debts
        """)
        providers, total_debts, grand_total = cur.fetchone()
        total_fmt = f"R$ {grand_total:,.2f}" if grand_total else "R$ 0"
        logger.info(
            f"PGFN Summary: {providers:,} ISPs with {total_debts:,} debts "
            f"totaling {total_fmt}"
        )

        cur.close()
        conn.close()
