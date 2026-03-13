"""Receita Federal Ownership Graph Pipeline.

Downloads bulk CNPJ Socios and Empresas files from Receita Federal open data
to build an ownership graph linking ISP providers through shared partners.

Source: https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos/ (CDN mirror)
Official: https://dadosabertos.rfb.gov.br/CNPJ/ (often slow/unreachable)

Files used:
  - Socios0..9.zip  — Partner/shareholder records (semicolon-delimited, Latin-1)
  - Empresas0..9.zip — Company name/capital records

Algorithm (3-pass):
  1. Collect ISP CNPJ roots (first 8 digits of providers.national_id)
  2. Pass 1 — Scan all Socios files: extract partners of ISPs -> partner document set
  3. Pass 2 — Scan all Socios files: find all companies where those partners appear
  4. Read Empresas files: get company names for related CNPJ roots
  5. Build ownership_graph rows linking ISP -> partner -> related company

Qualificacao codes (partner roles):
  05=Administrador, 08=Conselheiro, 10=Diretor, 16=Presidente,
  22=Socio, 49=Socio-Administrador, 54=Fundador, etc.
"""
import logging
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

# CDN mirror (Cloudflare-backed, much faster than official rfb.gov.br)
MIRROR_BASE = "https://dados-abertos-rf-cnpj.casadosdados.com.br/arquivos"
OFFICIAL_BASE = "https://dadosabertos.rfb.gov.br/CNPJ"

# File indices: Socios0..9, Empresas0..9
FILE_INDICES = list(range(10))

# Socios CSV columns (no header, semicolon-delimited, Latin-1/CP1252)
SOCIOS_COLS = [
    "cnpj_basico",           # 0: 8-digit CNPJ root
    "identificador_socio",   # 1: 1=PJ, 2=PF, 3=Foreign
    "nome_socio",            # 2: partner name
    "cnpj_cpf_socio",        # 3: partner CPF or CNPJ (masked for PF)
    "qualificacao_socio",    # 4: role code
    "data_entrada",          # 5: YYYYMMDD
    "pais",                  # 6: country code
    "representante_legal",   # 7: CPF of legal rep
    "nome_representante",    # 8: legal rep name
    "qualificacao_representante",  # 9: legal rep role code
    "faixa_etaria",          # 10: age bracket (added 2024+)
]

# Empresas CSV columns (no header, semicolon-delimited, Latin-1/CP1252)
EMPRESAS_COLS = [
    "cnpj_basico",           # 0: 8-digit CNPJ root
    "razao_social",          # 1: company legal name
    "natureza_juridica",     # 2: legal nature code
    "qualificacao_responsavel",  # 3: responsible person role code
    "capital_social",        # 4: e.g., "1000000,00"
    "porte_empresa",         # 5: 1=N/A, 2=ME, 3=EPP, 5=Other
    "ente_federativo",       # 6: federative entity
]

# Qualificacao code -> description mapping (most common)
QUALIFICACAO_MAP = {
    "05": "Administrador",
    "08": "Conselheiro de Administracao",
    "10": "Diretor",
    "16": "Presidente",
    "22": "Socio",
    "37": "Socio PJ Domiciliado no Exterior",
    "49": "Socio-Administrador",
    "54": "Fundador",
    "55": "Socio Comanditario",
    "56": "Socio Comanditado",
    "65": "Titular PF Residente no Brasil",
    "66": "Titular PF Residente no Exterior",
}

# Chunk size for pandas CSV reading (each Socios file ~200-400MB uncompressed)
CHUNK_SIZE = 50_000

# Default date folder
DEFAULT_DATE_FOLDER = "2026-02-20"


def _detect_latest_folder(http: PipelineHTTPClient) -> str:
    """Try to detect the latest date folder from the mirror index page."""
    try:
        resp = http._retry_request("GET", f"{MIRROR_BASE}/")
        html = resp.text
        dates = re.findall(r'href="(\d{4}-\d{2}-\d{2})/"', html)
        if dates:
            dates.sort()
            latest = dates[-1]
            logger.info(f"Detected latest RF data folder: {latest}")
            return latest
    except Exception as e:
        logger.warning(f"Could not detect latest folder: {e}")
    return DEFAULT_DATE_FOLDER


class RFOwnershipPipeline(BasePipeline):
    """Build ISP ownership graph from Receita Federal bulk CNPJ data."""

    def __init__(self):
        super().__init__("rf_ownership")
        self._isp_roots: set = set()                # ISP CNPJ roots (8 digits)
        self._isp_root_to_provider: dict = {}        # root -> provider_id
        self._isp_partners: dict = {}                # partner_doc -> {name, role, roots:[]}
        self._partner_companies: dict = {}           # partner_doc -> set of cnpj_roots
        self._company_names: dict = {}               # cnpj_root -> razao_social
        self._base_url: str = ""
        self._date_folder: str = DEFAULT_DATE_FOLDER

    def check_for_updates(self) -> bool:
        """Always run -- ownership data changes monthly with RF releases."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM ownership_graph")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count == 0:
            logger.info("ownership_graph is empty -- initial load needed")
            return True
        # Check if data is older than 30 days
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(updated_at) FROM ownership_graph")
        last_update = cur.fetchone()[0]
        cur.close()
        conn.close()
        if last_update and (datetime.utcnow() - last_update).days < 30:
            logger.info(f"ownership_graph last updated {last_update}, skipping")
            return False
        return True

    def download(self) -> dict:
        """Download and process RF bulk files in streaming fashion.

        Returns a dict with the assembled ownership graph data ready for loading.
        """
        # Step 1: Load ISP CNPJ roots from database
        self._load_isp_roots()
        if not self._isp_roots:
            logger.warning("No ISP providers with valid CNPJs found")
            return {"rows": []}

        logger.info(f"Loaded {len(self._isp_roots)} ISP CNPJ roots to match against")

        with PipelineHTTPClient(timeout=600, max_retries=3, base_delay=5.0) as http:
            # Detect latest date folder
            self._date_folder = _detect_latest_folder(http)
            self._base_url = f"{MIRROR_BASE}/{self._date_folder}"

            # Step 2: Pass 1 -- extract ISP partners from Socios files
            logger.info("=== PASS 1: Extracting ISP partner data ===")
            for idx in FILE_INDICES:
                self._process_socios_file(http, idx, pass_num=1)

            logger.info(
                f"Pass 1 complete: {len(self._isp_partners)} unique partners "
                f"found across {len(self._isp_roots)} ISPs"
            )

            if not self._isp_partners:
                logger.warning("No partners found for any ISP -- check CNPJ format")
                return {"rows": []}

            # Step 3: Pass 2 -- find all companies where ISP partners appear
            logger.info("=== PASS 2: Finding related companies ===")
            for idx in FILE_INDICES:
                self._process_socios_file(http, idx, pass_num=2)

            # Collect all related CNPJ roots (excluding ISP roots themselves)
            all_related_roots = set()
            for partner_doc, roots in self._partner_companies.items():
                for root in roots:
                    if root not in self._isp_roots:
                        all_related_roots.add(root)

            logger.info(
                f"Pass 2 complete: {len(all_related_roots)} related companies found"
            )

            # Step 4: Read Empresas files for company names
            if all_related_roots:
                # Also get names of ISP roots for completeness
                lookup_roots = all_related_roots | self._isp_roots
                logger.info(
                    f"=== Reading Empresas files for {len(lookup_roots)} company names ==="
                )
                for idx in FILE_INDICES:
                    self._process_empresas_file(http, idx, lookup_roots)

                logger.info(f"Resolved {len(self._company_names)} company names")

        # Step 5: Assemble ownership_graph rows
        return self._assemble_graph()

    def _load_isp_roots(self):
        """Load all ISP provider CNPJ roots from the database."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, national_id FROM providers
            WHERE national_id IS NOT NULL
              AND LENGTH(TRIM(national_id)) >= 8
        """)
        for provider_id, national_id in cur.fetchall():
            cnpj_clean = (
                national_id.strip()
                .replace(".", "")
                .replace("/", "")
                .replace("-", "")
            )
            # Skip masked national_ids (e.g., ***25828**)
            if "*" in cnpj_clean:
                continue
            if len(cnpj_clean) >= 8 and cnpj_clean.isdigit():
                root = cnpj_clean[:8]
                self._isp_roots.add(root)
                self._isp_root_to_provider[root] = provider_id
        cur.close()
        conn.close()

    def _download_and_extract_zip(
        self, http: PipelineHTTPClient, file_type: str, idx: int
    ) -> Path:
        """Download a ZIP file and extract the CSV inside. Returns path to CSV."""
        filename = f"{file_type}{idx}.zip"
        url = f"{self._base_url}/{filename}"
        zip_path = get_cache_path(f"rf_{self._date_folder}_{filename}")
        csv_dir = Path("/tmp/enlace_cache/rf_extracted")
        csv_dir.mkdir(parents=True, exist_ok=True)
        csv_path = csv_dir / f"{file_type}{idx}.csv"

        # Skip extraction if CSV already exists and is non-empty
        if csv_path.exists() and csv_path.stat().st_size > 0:
            logger.info(
                f"Using cached CSV: {csv_path} ({csv_path.stat().st_size:,} bytes)"
            )
            return csv_path

        # Download ZIP
        logger.info(f"Downloading {url}...")
        http.download_file(url, zip_path, resume=True)
        zip_size = zip_path.stat().st_size
        logger.info(f"Downloaded {filename}: {zip_size:,} bytes")

        # Extract CSV from ZIP
        with zipfile.ZipFile(zip_path) as zf:
            members = zf.namelist()
            if not members:
                raise ValueError(f"Empty ZIP: {filename}")
            # Pick the first (usually only) member
            csv_member = members[0]
            logger.info(f"Extracting {csv_member} from {filename}...")
            zf.extract(csv_member, csv_dir)
            extracted = csv_dir / csv_member
            # Rename to consistent name if different
            if extracted != csv_path:
                if csv_path.exists():
                    csv_path.unlink()
                extracted.rename(csv_path)

        logger.info(f"Extracted {csv_path}: {csv_path.stat().st_size:,} bytes")
        return csv_path

    def _process_socios_file(
        self, http: PipelineHTTPClient, idx: int, pass_num: int
    ):
        """Process a single Socios file in chunked mode.

        Pass 1: Extract partners of ISPs.
        Pass 2: Find all companies where ISP partners appear.
        """
        try:
            csv_path = self._download_and_extract_zip(http, "Socios", idx)
        except Exception as e:
            logger.error(f"Failed to download/extract Socios{idx}.zip: {e}")
            return

        chunks_processed = 0
        rows_scanned = 0

        try:
            reader = pd.read_csv(
                csv_path,
                sep=";",
                header=None,
                names=SOCIOS_COLS,
                dtype=str,
                encoding="latin-1",
                on_bad_lines="skip",
                chunksize=CHUNK_SIZE,
                keep_default_na=False,
            )
        except Exception as e:
            logger.error(f"Failed to open Socios{idx} CSV: {e}")
            return

        for chunk in reader:
            chunks_processed += 1
            rows_scanned += len(chunk)

            # Ensure cnpj_basico is zero-padded to 8 digits
            chunk["cnpj_basico"] = chunk["cnpj_basico"].str.strip().str.zfill(8)
            chunk["cnpj_cpf_socio"] = chunk["cnpj_cpf_socio"].str.strip()
            chunk["nome_socio"] = chunk["nome_socio"].str.strip()
            chunk["qualificacao_socio"] = chunk["qualificacao_socio"].str.strip()

            if pass_num == 1:
                self._socios_pass1(chunk)
            elif pass_num == 2:
                self._socios_pass2(chunk)

            if chunks_processed % 20 == 0:
                if pass_num == 1:
                    logger.info(
                        f"  Socios{idx} pass 1: {rows_scanned:,} rows scanned, "
                        f"{len(self._isp_partners)} partners found"
                    )
                else:
                    total_related = sum(
                        len(v) for v in self._partner_companies.values()
                    )
                    logger.info(
                        f"  Socios{idx} pass 2: {rows_scanned:,} rows scanned, "
                        f"{total_related} related company links found"
                    )

        logger.info(
            f"  Socios{idx} pass {pass_num} done: {rows_scanned:,} rows in "
            f"{chunks_processed} chunks"
        )

    def _socios_pass1(self, chunk: pd.DataFrame):
        """Pass 1: Find rows where cnpj_basico is an ISP root."""
        mask = chunk["cnpj_basico"].isin(self._isp_roots)
        isp_rows = chunk[mask]

        for _, row in isp_rows.iterrows():
            partner_doc = row["cnpj_cpf_socio"]
            # Masked CPFs (***324968**) or empty docs -> use name as key
            if (not partner_doc or partner_doc == "0"
                    or len(partner_doc) < 3 or "*" in partner_doc):
                partner_doc = f"NAME:{row['nome_socio']}"

            role_code = row["qualificacao_socio"]
            role_desc = QUALIFICACAO_MAP.get(role_code, f"Codigo {role_code}")

            if partner_doc not in self._isp_partners:
                self._isp_partners[partner_doc] = {
                    "name": row["nome_socio"],
                    "role": role_desc,
                    "role_code": role_code,
                    "tipo": row["identificador_socio"],  # 1=PJ, 2=PF
                    "isp_roots": set(),
                }
            self._isp_partners[partner_doc]["isp_roots"].add(
                row["cnpj_basico"]
            )

    def _socios_pass2(self, chunk: pd.DataFrame):
        """Pass 2: Find all companies where known ISP partners appear."""
        partner_docs = set(
            k for k in self._isp_partners.keys() if not k.startswith("NAME:")
        )

        # Match by document
        mask_doc = chunk["cnpj_cpf_socio"].isin(partner_docs)

        # Match by name for partners without documents
        name_partners = {
            k[5:]: k
            for k in self._isp_partners.keys()
            if k.startswith("NAME:")
        }
        if name_partners:
            mask_name = chunk["nome_socio"].isin(name_partners.keys())
            related_rows = chunk[mask_doc | mask_name]
        else:
            related_rows = chunk[mask_doc]

        for _, row in related_rows.iterrows():
            partner_doc = row["cnpj_cpf_socio"]
            cnpj_root = row["cnpj_basico"]

            # Determine the partner key
            if partner_doc in partner_docs:
                key = partner_doc
            elif row["nome_socio"] in name_partners:
                key = name_partners[row["nome_socio"]]
            else:
                continue

            if key not in self._partner_companies:
                self._partner_companies[key] = set()
            self._partner_companies[key].add(cnpj_root)

    def _process_empresas_file(
        self,
        http: PipelineHTTPClient,
        idx: int,
        lookup_roots: set,
    ):
        """Read an Empresas file to get company names for relevant CNPJ roots."""
        try:
            csv_path = self._download_and_extract_zip(http, "Empresas", idx)
        except Exception as e:
            logger.error(f"Failed to download/extract Empresas{idx}.zip: {e}")
            return

        chunks_processed = 0
        names_found = 0

        try:
            reader = pd.read_csv(
                csv_path,
                sep=";",
                header=None,
                names=EMPRESAS_COLS,
                dtype=str,
                encoding="latin-1",
                on_bad_lines="skip",
                chunksize=CHUNK_SIZE,
                keep_default_na=False,
            )
        except Exception as e:
            logger.error(f"Failed to open Empresas{idx} CSV: {e}")
            return

        for chunk in reader:
            chunks_processed += 1
            chunk["cnpj_basico"] = chunk["cnpj_basico"].str.strip().str.zfill(8)

            mask = chunk["cnpj_basico"].isin(lookup_roots)
            matches = chunk[mask]

            for _, row in matches.iterrows():
                root = row["cnpj_basico"]
                if root not in self._company_names:
                    name = row["razao_social"].strip()
                    if name:
                        self._company_names[root] = name
                        names_found += 1

            if chunks_processed % 20 == 0:
                logger.info(
                    f"  Empresas{idx}: {chunks_processed} chunks, "
                    f"{names_found} names resolved so far"
                )

        logger.info(f"  Empresas{idx} done: {names_found} names resolved")

    def _assemble_graph(self) -> dict:
        """Assemble the final ownership_graph rows from collected data."""
        rows = []

        for partner_doc, partner_info in self._isp_partners.items():
            partner_name = partner_info["name"]
            partner_role = partner_info["role"]
            partner_tipo = partner_info["tipo"]
            isp_roots = partner_info["isp_roots"]

            # Get related companies for this partner
            related_roots = self._partner_companies.get(partner_doc, set())

            # Determine relationship type
            if partner_tipo == "1":
                rel_type = "partner_pj"  # Corporate partner
            elif partner_tipo == "2":
                rel_type = "partner_pf"  # Individual partner
            elif partner_tipo == "3":
                rel_type = "partner_foreign"
            else:
                rel_type = "partner_unknown"

            # Clean document for storage
            clean_doc = (
                partner_doc if not partner_doc.startswith("NAME:") else None
            )

            for isp_root in isp_roots:
                provider_id = self._isp_root_to_provider.get(isp_root)
                if not provider_id:
                    continue

                if related_roots:
                    # One row per ISP-partner-related_company triple
                    for related_root in related_roots:
                        if related_root == isp_root:
                            continue  # Skip self-references
                        rows.append({
                            "provider_id": provider_id,
                            "provider_cnpj_root": isp_root,
                            "partner_name": (
                                partner_name[:255] if partner_name else None
                            ),
                            "partner_document": (
                                clean_doc[:20] if clean_doc else None
                            ),
                            "partner_role": (
                                partner_role[:255] if partner_role else None
                            ),
                            "related_cnpj_root": related_root,
                            "related_company_name": (
                                self._company_names.get(related_root, "")[:255]
                                or None
                            ),
                            "related_cnae": None,
                            "relationship_type": rel_type,
                        })
                else:
                    # Partner has no other companies -- store the direct link
                    rows.append({
                        "provider_id": provider_id,
                        "provider_cnpj_root": isp_root,
                        "partner_name": (
                            partner_name[:255] if partner_name else None
                        ),
                        "partner_document": (
                            clean_doc[:20] if clean_doc else None
                        ),
                        "partner_role": (
                            partner_role[:255] if partner_role else None
                        ),
                        "related_cnpj_root": None,
                        "related_company_name": None,
                        "related_cnae": None,
                        "relationship_type": rel_type,
                    })

        logger.info(f"Assembled {len(rows)} ownership graph rows")
        self.rows_processed = len(rows)
        return {"rows": rows}

    def transform(self, raw_data: Any) -> Any:
        """Data is already transformed during download phase."""
        return raw_data

    def load(self, data: dict) -> None:
        """Load ownership graph rows into the database."""
        rows = data.get("rows", [])
        if not rows:
            logger.warning("No ownership graph data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Clear existing data for a clean load
        cur.execute("DELETE FROM ownership_graph")
        logger.info("Cleared existing ownership_graph data")

        batch_size = 1000
        loaded = 0

        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            values_list = []
            params = []

            for row in batch:
                values_list.append(
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())"
                )
                params.extend([
                    row["provider_id"],
                    row["provider_cnpj_root"],
                    row["partner_name"],
                    row["partner_document"],
                    row["partner_role"],
                    row["related_cnpj_root"],
                    row["related_company_name"],
                    row["related_cnae"],
                    row["relationship_type"],
                ])

            try:
                cur.execute("SAVEPOINT batch_sp")
                sql = (
                    "INSERT INTO ownership_graph"
                    " (provider_id, provider_cnpj_root, partner_name,"
                    "  partner_document, partner_role, related_cnpj_root,"
                    "  related_company_name, related_cnae, relationship_type,"
                    "  updated_at)"
                    " VALUES " + ", ".join(values_list)
                )
                cur.execute(sql, params)
                cur.execute("RELEASE SAVEPOINT batch_sp")
                loaded += len(batch)
            except Exception as e:
                logger.error(f"Failed to load batch at offset {i}: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT batch_sp")
                # Fall back to row-by-row
                for row in batch:
                    try:
                        cur.execute("SAVEPOINT row_sp")
                        cur.execute(
                            "INSERT INTO ownership_graph"
                            " (provider_id, provider_cnpj_root, partner_name,"
                            "  partner_document, partner_role,"
                            "  related_cnpj_root, related_company_name,"
                            "  related_cnae, relationship_type, updated_at)"
                            " VALUES"
                            " (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                            (
                                row["provider_id"],
                                row["provider_cnpj_root"],
                                row["partner_name"],
                                row["partner_document"],
                                row["partner_role"],
                                row["related_cnpj_root"],
                                row["related_company_name"],
                                row["related_cnae"],
                                row["relationship_type"],
                            ),
                        )
                        cur.execute("RELEASE SAVEPOINT row_sp")
                        loaded += 1
                    except Exception as row_err:
                        logger.warning(f"Failed to load row: {row_err}")
                        cur.execute("ROLLBACK TO SAVEPOINT row_sp")

            if loaded % 5000 == 0 and loaded > 0:
                conn.commit()
                logger.info(
                    f"Loaded {loaded:,}/{len(rows):,} ownership graph rows"
                )

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded:,} ownership graph rows total")

    def post_load(self) -> None:
        """Log summary statistics."""
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM ownership_graph")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(DISTINCT provider_id) FROM ownership_graph")
        providers = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(DISTINCT partner_document) FROM ownership_graph "
            "WHERE partner_document IS NOT NULL"
        )
        partners = cur.fetchone()[0]

        cur.execute(
            "SELECT COUNT(DISTINCT related_cnpj_root) FROM ownership_graph "
            "WHERE related_cnpj_root IS NOT NULL"
        )
        related = cur.fetchone()[0]

        # Cross-ownership: partners appearing in multiple ISPs
        cur.execute("""
            SELECT partner_document, partner_name,
                   COUNT(DISTINCT provider_id) as isp_count
            FROM ownership_graph
            WHERE partner_document IS NOT NULL
            GROUP BY partner_document, partner_name
            HAVING COUNT(DISTINCT provider_id) > 1
            ORDER BY isp_count DESC
            LIMIT 10
        """)
        cross_owners = cur.fetchall()

        cur.close()
        conn.close()

        logger.info("=== Ownership Graph Summary ===")
        logger.info(f"Total rows: {total:,}")
        logger.info(f"ISP providers covered: {providers:,}")
        logger.info(f"Unique partners: {partners:,}")
        logger.info(f"Related companies: {related:,}")

        if cross_owners:
            logger.info(
                "Top cross-ISP partners (appear in multiple ISPs):"
            )
            for doc, name, count in cross_owners:
                logger.info(f"  {name} ({doc}): {count} ISPs")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pipeline = RFOwnershipPipeline()
    result = pipeline.run(force=True)
    print(f"\nResult: {result}")
