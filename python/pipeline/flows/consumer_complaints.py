"""Consumer complaints pipeline — consumidor.gov.br (Ministério da Justiça).

Source: dados.mj.gov.br CKAN API
Dataset: reclamacoes-do-consumidor-gov-br
Format: CSV (semicolon-delimited, UTF-8 with BOM)
Segment filter: "Operadoras de Telecomunicações (Telefonia, Internet, TV por assinatura)"

Downloads monthly CSV files for 2024-2026, filters to telecom segment,
matches company names/CNPJs to our providers table, and loads into
consumer_complaints.
"""
import io
import logging
import re
import unicodedata
from datetime import datetime
from typing import Any, Optional

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DatabaseConfig
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

CKAN_API_URL = "https://dados.mj.gov.br/api/3/action/package_show"
DATASET_ID = "reclamacoes-do-consumidor-gov-br"
TELECOM_SEGMENT = "Operadoras de Telecomunicações (Telefonia, Internet, TV por assinatura)"

# Years to download (monthly files from 2020 onward)
TARGET_YEARS = [2024, 2025, 2026]

# Known trade-name -> CNPJ mappings for major telecoms
# These help match consumidor.gov.br trade names to our providers table
KNOWN_TELECOM_CNPJS = {
    "claro": "40432544000147",
    "claro celular": "40432544000147",
    "claro residencial": "40432544000147",
    "claro fixo": "40432544000147",
    "net": "40432544000147",
    "embratel": "40432544000147",
    "vivo": "02558157000162",
    "telefonica": "02558157000162",
    "gvt": "02558157000162",
    "tim": "02421421000111",
    "oi": "76535764000143",
    "oi fixo": "76535764000143",
    "oi fibra": "76535764000143",
    "oi movel": "76535764000143",
    "sky": "00497373000110",
    "algar": "71208516000174",
    "brisanet": "04601397000128",
    "desktop": "08170849000115",
    "unifique": "02255187000108",
    "ligga": "04368865000166",
    "sumicity": "18028846000130",
    "giga+": "18028846000130",
    "copel telecom": "04368865000166",
    "hughesnet": "05206385000161",
    "hughes": "05206385000161",
    "starlink": "46783975000120",
    "nio": "40432544000147",
    "age telecom": "36230547000120",
    "mob telecom": "22761565000124",
    "proxxima": "40120343000104",
    "viasat": "27001440000110",
    "intelig": "40432544000147",
}


def _normalize(text: str) -> str:
    """Normalize a string for fuzzy matching: lowercase, strip accents, remove punctuation."""
    if not text:
        return ""
    text = text.strip().lower()
    # Remove accents
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Remove common suffixes and punctuation
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(date_str: str) -> Optional[str]:
    """Parse dd/mm/yyyy or yyyy-mm-dd to ISO date string."""
    if not date_str or pd.isna(date_str):
        return None
    date_str = str(date_str).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_int(val: Any) -> Optional[int]:
    """Safely parse an integer from a CSV value."""
    if val is None or pd.isna(val):
        return None
    try:
        return int(float(str(val).strip().replace(",", ".")))
    except (ValueError, TypeError):
        return None


class ConsumerComplaintsPipeline(BasePipeline):
    """Ingest consumer complaints from consumidor.gov.br, filtered to telecom ISPs."""

    def __init__(self):
        super().__init__("consumer_complaints")
        self._resource_urls: list[dict] = []

    def check_for_updates(self) -> bool:
        """Always run — check if we have recent data."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(complaint_date) FROM consumer_complaints")
        result = cur.fetchone()
        cur.close()
        conn.close()
        max_date = result[0] if result else None
        if max_date is None:
            logger.info("No existing complaints — will download all")
            return True
        logger.info(f"Latest complaint date: {max_date}")
        return True

    def download(self) -> list[pd.DataFrame]:
        """Download CSV files from CKAN API for target years.

        Returns list of DataFrames (one per file, already filtered to telecom segment).
        """
        with PipelineHTTPClient(timeout=600) as http:
            # Resolve all resource URLs from CKAN
            logger.info("Fetching CKAN dataset metadata...")
            resp = http.get_json(CKAN_API_URL, params={"id": DATASET_ID})
            resources = resp.get("result", {}).get("resources", [])

            # Filter for target year CSV resources
            target_resources = []
            for r in resources:
                name = r.get("name", "")
                url = r.get("url", "")
                fmt = (r.get("format") or "").upper()
                if fmt != "CSV" and not url.endswith(".csv"):
                    continue
                # Check if this resource matches any target year
                for year in TARGET_YEARS:
                    if str(year) in name or str(year) in url:
                        target_resources.append({
                            "name": name,
                            "url": url,
                            "year": year,
                        })
                        break

            logger.info(f"Found {len(target_resources)} CSV resources for years {TARGET_YEARS}")

            # Download and filter each file
            all_dfs = []
            for res in target_resources:
                url = res["url"]
                name = res["name"]
                logger.info(f"Downloading: {name} ({url})")

                try:
                    df = self._download_and_filter_csv(http, url)
                    if df is not None and not df.empty:
                        logger.info(f"  -> {len(df)} telecom complaints from {name}")
                        all_dfs.append(df)
                    else:
                        logger.info(f"  -> 0 telecom complaints from {name}")
                except Exception as e:
                    logger.warning(f"  -> Failed to process {name}: {e}")
                    continue

        return all_dfs

    def _download_and_filter_csv(
        self, http: PipelineHTTPClient, url: str
    ) -> Optional[pd.DataFrame]:
        """Download a single CSV and return rows matching telecom segment.

        Reads in chunks to handle large files (50-100MB) without blowing memory.
        """
        resp = http._retry_request("GET", url)
        raw_bytes = resp.content

        # Detect encoding: try UTF-8 BOM, then UTF-8, then latin-1
        text = None
        for enc in ("utf-8-sig", "utf-8", "latin-1"):
            try:
                text = raw_bytes.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            text = raw_bytes.decode("latin-1", errors="replace")

        # Read in chunks to filter early and save memory
        chunks = []
        chunk_iter = pd.read_csv(
            io.StringIO(text),
            sep=";",
            dtype=str,
            on_bad_lines="skip",
            chunksize=50_000,
        )

        for chunk in chunk_iter:
            # Normalize column names (strip whitespace, BOM)
            chunk.columns = [c.strip().strip("\ufeff") for c in chunk.columns]

            # Find the segment column
            seg_col = None
            for c in chunk.columns:
                if "segmento" in c.lower():
                    seg_col = c
                    break

            if seg_col is None:
                logger.warning(f"No 'Segmento' column found. Columns: {list(chunk.columns)}")
                return None

            # Filter to telecom segment
            mask = chunk[seg_col].str.strip() == TELECOM_SEGMENT
            filtered = chunk[mask]
            if not filtered.empty:
                chunks.append(filtered)

        if not chunks:
            return None

        return pd.concat(chunks, ignore_index=True)

    def validate_raw(self, data: list[pd.DataFrame]) -> None:
        total = sum(len(df) for df in data)
        if total == 0:
            raise ValueError("No telecom complaints found across all downloaded files")
        logger.info(f"Total raw telecom complaints: {total:,}")

    def transform(self, raw_data: list[pd.DataFrame]) -> list[tuple]:
        """Transform raw DataFrames into rows for consumer_complaints table.

        Matches company names to our providers table using CNPJ and fuzzy name matching.
        Optimized: matches each unique company name once, then applies via dict lookup.
        """
        # Concatenate all chunks
        df = pd.concat(raw_data, ignore_index=True)
        df.columns = [c.strip().strip("﻿") for c in df.columns]

        logger.info(f"Columns available: {list(df.columns)}")

        # Build column mapping (handle slight variations across years)
        col_map = {}
        for c in df.columns:
            cl = c.lower().strip()
            if cl == "nome fantasia":
                col_map["company_name"] = c
            elif cl == "cnpj":
                col_map["cnpj"] = c
            elif cl == "uf":
                col_map["state"] = c
            elif cl == "cidade":
                col_map["city"] = c
            elif cl == "data abertura":
                col_map["complaint_date"] = c
            elif "segmento" in cl:
                col_map["segment"] = c
            elif cl == "área" or cl == "area":
                col_map["area"] = c
            elif cl == "assunto":
                col_map["subject"] = c
            elif cl == "grupo problema":
                col_map["problem_group"] = c
            elif cl == "problema":
                col_map["problem"] = c
            elif cl == "respondida":
                col_map["responded"] = c
            elif cl == "situação" or cl == "situacao":
                col_map["status"] = c
            elif cl == "avaliação reclamação" or cl == "avaliacao reclamacao":
                col_map["evaluation"] = c
            elif cl == "nota do consumidor":
                col_map["rating"] = c
            elif cl == "tempo resposta":
                col_map["response_time"] = c

        logger.info(f"Column mapping: {col_map}")

        # Build provider matching lookups from DB
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, name, name_normalized, national_id FROM providers WHERE country_code = 'BR'")
        providers = cur.fetchall()
        cur.close()
        conn.close()

        # CNPJ -> provider_id (strip formatting)
        cnpj_to_pid: dict[str, int] = {}
        for pid, pname, pnorm, cnpj in providers:
            if cnpj:
                clean_cnpj = re.sub(r"[^0-9]", "", cnpj)
                cnpj_to_pid[clean_cnpj] = pid

        # Normalized name -> provider_id
        name_to_pid: dict[str, int] = {}
        for pid, pname, pnorm, cnpj in providers:
            if pnorm:
                name_to_pid[_normalize(pnorm)] = pid
            if pname:
                name_to_pid[_normalize(pname)] = pid

        # Add known telecom aliases
        for alias, cnpj in KNOWN_TELECOM_CNPJS.items():
            clean = re.sub(r"[^0-9]", "", cnpj)
            pid = cnpj_to_pid.get(clean)
            if pid:
                name_to_pid[_normalize(alias)] = pid

        def match_provider_by_name(company_name: str) -> Optional[int]:
            """Match a company name to a provider. No CNPJ in these CSVs."""
            # 1. Exact normalized name match (fast O(1) dict lookup)
            norm = _normalize(company_name)
            if norm in name_to_pid:
                return name_to_pid[norm]

            # 2. Check if company name contains any known alias (~20 aliases, fast)
            for alias in KNOWN_TELECOM_CNPJS:
                if alias in norm:
                    cnpj = KNOWN_TELECOM_CNPJS[alias]
                    clean = re.sub(r"[^0-9]", "", cnpj)
                    pid = cnpj_to_pid.get(clean)
                    if pid:
                        return pid

            return None

        # OPTIMIZATION: Match each unique company name only once, then reuse via cache.
        # Telecom CSVs typically have ~100-200 unique company names across 400K+ rows.
        # This avoids the O(n*m) substring scan that was taking 30+ minutes.
        name_col = col_map.get("company_name", "")
        unique_names = df[name_col].fillna("").str.strip().unique() if name_col else []
        logger.info(f"Matching {len(unique_names)} unique company names to providers...")

        name_match_cache: dict[str, Optional[int]] = {}
        for cname in unique_names:
            name_match_cache[str(cname)] = match_provider_by_name(str(cname))

        matched_names = {k: v for k, v in name_match_cache.items() if v is not None}
        unmatched_names = sorted(k for k, v in name_match_cache.items() if v is None and k)
        logger.info(
            f"Matched {len(matched_names)}/{len(unique_names)} unique company names. "
            f"Unmatched ({len(unmatched_names)}): {unmatched_names[:20]}"
        )

        # Pre-extract columns as arrays for fast indexed access (avoid iterrows overhead)
        now = datetime.utcnow()

        def _col_values(key: str):
            """Get column values as list, or empty strings if column missing."""
            col = col_map.get(key, "")
            if col and col in df.columns:
                return df[col].fillna("").values
            return [""] * len(df)

        company_names = _col_values("company_name")
        dates = _col_values("complaint_date")
        states = _col_values("state")
        cities = _col_values("city")
        areas = _col_values("area")
        subjects = _col_values("subject")
        prob_groups = _col_values("problem_group")
        problems = _col_values("problem")
        statuses = _col_values("status")
        evaluations = _col_values("evaluation")
        ratings_raw = _col_values("rating")
        resp_times_raw = _col_values("response_time")
        segments = _col_values("segment")

        rows = []
        matched_count = 0
        unmatched_companies: dict[str, int] = {}
        n = len(df)

        for i in range(n):
            cname = str(company_names[i]).strip()

            complaint_date = _parse_date(dates[i])
            if not complaint_date:
                continue

            state = str(states[i]).strip()
            city = str(cities[i]).strip()
            area = str(areas[i]).strip()
            subject = str(subjects[i]).strip()
            problem_group = str(prob_groups[i]).strip()
            problem = str(problems[i]).strip()

            category = " | ".join(filter(None, [area, subject]))
            problem_desc = " | ".join(filter(None, [problem_group, problem]))

            status = str(statuses[i]).strip()
            evaluation = str(evaluations[i]).strip()
            rating = _parse_int(ratings_raw[i])
            response_time = _parse_int(resp_times_raw[i])
            segment = str(segments[i]).strip()

            # Use cached provider match (O(1) dict lookup)
            provider_id = name_match_cache.get(cname)
            if provider_id:
                matched_count += 1
            elif cname:
                unmatched_companies[cname] = unmatched_companies.get(cname, 0) + 1

            rows.append((
                provider_id,       # provider_id (nullable FK)
                cname or None,
                None,              # company_cnpj (not in these CSVs)
                complaint_date,
                state or None,
                city or None,
                category or None,
                problem_desc or None,     # problem_description
                evaluation or None,       # company_response (reuse for evaluation)
                status or None,
                None,                     # resolution (not in CSV directly)
                rating,
                response_time,
                segment or None,
                now,                      # updated_at
            ))

            if i % 100_000 == 0 and i > 0:
                logger.info(f"  Transformed {i:,} / {n:,} rows...")

        self.rows_processed = len(rows)
        logger.info(
            f"Transformed {len(rows):,} complaints. "
            f"Provider-matched: {matched_count:,} ({100*matched_count/max(len(rows),1):.1f}%)"
        )

        # Log top unmatched companies
        if unmatched_companies:
            top_unmatched = sorted(unmatched_companies.items(), key=lambda x: -x[1])[:15]
            logger.info(f"Top unmatched companies: {top_unmatched}")

        return rows


    def load(self, data: list[tuple]) -> None:
        """Bulk insert complaints into consumer_complaints table.

        Uses SAVEPOINT pattern for resilience, inserting in batches.
        Clears existing data first to avoid duplicates on re-run.
        """
        if not data:
            logger.warning("No complaints to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Clear existing data from this pipeline source
        cur.execute("DELETE FROM consumer_complaints")
        deleted = cur.rowcount
        if deleted:
            logger.info(f"Cleared {deleted:,} existing complaints")
        conn.commit()

        # Batch insert
        BATCH_SIZE = 5000
        total_inserted = 0

        columns = (
            "provider_id, company_name, company_cnpj, complaint_date, "
            "state, city, category, problem_description, company_response, "
            "status, resolution, satisfaction_rating, response_days, "
            "segment, updated_at"
        )
        placeholders = ", ".join(["%s"] * 15)

        for i in range(0, len(data), BATCH_SIZE):
            batch = data[i:i + BATCH_SIZE]
            try:
                cur.execute("SAVEPOINT batch_insert")
                from psycopg2.extras import execute_batch
                sql = f"INSERT INTO consumer_complaints ({columns}) VALUES ({placeholders})"
                execute_batch(cur, sql, batch, page_size=1000)
                cur.execute("RELEASE SAVEPOINT batch_insert")
                total_inserted += len(batch)
            except Exception as e:
                cur.execute("ROLLBACK TO SAVEPOINT batch_insert")
                logger.error(f"Failed to insert batch {i//BATCH_SIZE}: {e}")
                # Try row-by-row for this batch to skip bad rows
                for row in batch:
                    try:
                        cur.execute("SAVEPOINT single_insert")
                        cur.execute(
                            f"INSERT INTO consumer_complaints ({columns}) VALUES ({placeholders})",
                            row,
                        )
                        cur.execute("RELEASE SAVEPOINT single_insert")
                        total_inserted += 1
                    except Exception as row_e:
                        cur.execute("ROLLBACK TO SAVEPOINT single_insert")
                        logger.debug(f"Skipped bad row: {row_e}")

            if (i // BATCH_SIZE) % 10 == 0 and i > 0:
                logger.info(f"  Inserted {total_inserted:,} / {len(data):,} rows...")

        conn.commit()
        cur.close()
        conn.close()

        self.rows_inserted = total_inserted
        logger.info(f"Loaded {total_inserted:,} complaints into consumer_complaints")

    def post_load(self) -> None:
        """Log summary statistics."""
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM consumer_complaints")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM consumer_complaints WHERE provider_id IS NOT NULL")
        matched = cur.fetchone()[0]

        cur.execute(
            "SELECT company_name, COUNT(*) as cnt FROM consumer_complaints "
            "GROUP BY company_name ORDER BY cnt DESC LIMIT 10"
        )
        top_companies = cur.fetchall()

        cur.execute(
            "SELECT state, COUNT(*) as cnt FROM consumer_complaints "
            "GROUP BY state ORDER BY cnt DESC LIMIT 10"
        )
        top_states = cur.fetchall()

        cur.execute(
            "SELECT MIN(complaint_date), MAX(complaint_date) FROM consumer_complaints"
        )
        date_range = cur.fetchone()

        cur.close()
        conn.close()

        logger.info(f"=== Consumer Complaints Summary ===")
        logger.info(f"Total complaints: {total:,}")
        logger.info(f"Provider-matched: {matched:,} ({100*matched/max(total,1):.1f}%)")
        logger.info(f"Date range: {date_range[0]} to {date_range[1]}")
        logger.info(f"Top companies: {top_companies}")
        logger.info(f"Top states: {top_states}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    pipeline = ConsumerComplaintsPipeline()
    result = pipeline.run(force=True)
    print(f"\nResult: {result}")
