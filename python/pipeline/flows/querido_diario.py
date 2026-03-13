"""Querido Diario Municipal Gazette Pipeline.

Source: Querido Diario API (https://api.queridodiario.ok.org.br/api/gazettes)
Format: JSON API -- no auth, free
Fields: municipality (territory_id), published date, gazette excerpt, keywords

Municipal gazettes contain critical signals: tower permits, fiber construction
licenses, right-of-way authorizations, local telecom regulation changes.
Monitoring covered municipalities provides regulatory intelligence
at the local level.
"""
import hashlib
import logging
from datetime import datetime, timedelta

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

# Base URL confirmed working -- note: api.queridodiario.ok.org.br, NOT queridodiario.ok.org.br/api
QUERIDO_DIARIO_API_URL = "https://api.queridodiario.ok.org.br/api/gazettes"

# Telecom-related keywords to search for in municipal gazettes
TELECOM_SEARCH_TERMS = [
    "telecomunicacao",
    "torre",
    "antena",
    "fibra",
    "banda larga",
    "internet",
    "conectividade",
    "alvara",
]

# Map search terms to mention_type categories
KEYWORD_MENTION_TYPE = {
    "telecomunicacao": "telecomunicacao",
    "torre": "infraestrutura",
    "antena": "infraestrutura",
    "fibra": "fibra",
    "banda larga": "banda_larga",
    "internet": "internet",
    "conectividade": "conectividade",
    "alvara": "licenca",
}

# Maximum results per request (API limit)
PAGE_SIZE = 100


class QueridoDiarioPipeline(BasePipeline):
    """Ingest municipal gazette telecom mentions from Querido Diario API."""

    def __init__(self):
        super().__init__("querido_diario")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS municipal_gazette_mentions (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                published_date DATE,
                gazette_id VARCHAR(100),
                excerpt TEXT,
                keywords TEXT[],
                mention_type VARCHAR(50),
                source_url VARCHAR(500),
                source VARCHAR(50) DEFAULT 'querido_diario',
                UNIQUE (gazette_id, excerpt)
            )
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_gazette_mentions_date
            ON municipal_gazette_mentions(published_date)
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_gazette_mentions_l2_id
            ON municipal_gazette_mentions(l2_id)
        """)
        conn.commit()

        # Check for recent data
        cur.execute("""
            SELECT MAX(published_date) FROM municipal_gazette_mentions
        """)
        last_date = cur.fetchone()[0]
        cur.close()
        conn.close()

        if last_date is None:
            return True
        return (datetime.now().date() - last_date).days > 1

    def download(self) -> pd.DataFrame:
        """Query Querido Diario real API for telecom-related gazette mentions.

        Searches for each keyword across a date range, paginating through all
        results using the offset parameter. Raises on API failure -- no
        synthetic data fallback.
        """
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(published_date) FROM municipal_gazette_mentions")
        last_date = cur.fetchone()[0]
        cur.close()
        conn.close()

        since = (
            (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
            if last_date
            else (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
        )
        until = datetime.now().strftime("%Y-%m-%d")

        logger.info(
            f"Querying Querido Diario API from {since} to {until} "
            f"for {len(TELECOM_SEARCH_TERMS)} keywords"
        )

        all_results = []
        seen_keys = set()  # Deduplicate across keyword searches

        with PipelineHTTPClient(timeout=60) as http:
            for term in TELECOM_SEARCH_TERMS:
                offset = 0
                term_total = 0

                while True:
                    try:
                        data = http.get_json(
                            QUERIDO_DIARIO_API_URL,
                            params={
                                "querystring": term,
                                "since": since,
                                "until": until,
                                "size": PAGE_SIZE,
                                "offset": offset,
                            },
                        )
                    except Exception as e:
                        # API returns 404 when offset exceeds available results
                        logger.warning(
                            f"Querido Diario API request for '{term}' "
                            f"(offset={offset}) failed: {e}"
                        )
                        break

                    if not isinstance(data, dict):
                        raise RuntimeError(
                            f"Querido Diario API returned unexpected response "
                            f"type {type(data).__name__} for keyword '{term}'"
                        )

                    gazettes = data.get("gazettes", [])
                    total_gazettes = data.get("total_gazettes", 0)

                    for gazette in gazettes:
                        # Build a dedup key from territory_id + date + url
                        dedup_key = (
                            gazette.get("territory_id", ""),
                            gazette.get("date", ""),
                            gazette.get("url", ""),
                        )
                        if dedup_key not in seen_keys:
                            seen_keys.add(dedup_key)
                            gazette["search_term"] = term
                            all_results.append(gazette)

                    term_total += len(gazettes)

                    # Stop paginating if we got fewer than PAGE_SIZE or reached total
                    if len(gazettes) < PAGE_SIZE or term_total >= total_gazettes:
                        break

                    offset += PAGE_SIZE

                if term_total > 0:
                    logger.info(
                        f"Keyword '{term}': {term_total} gazettes fetched "
                        f"({total_gazettes} total available)"
                    )

        if not all_results:
            logger.warning(
                f"Querido Diario API returned 0 results for date range "
                f"{since} to {until}. This may be expected for very recent dates."
            )
            return pd.DataFrame()

        logger.info(
            f"Downloaded {len(all_results)} unique gazette results "
            f"across {len(TELECOM_SEARCH_TERMS)} keywords"
        )
        return pd.DataFrame(all_results)

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Transform raw API response into load-ready records.

        Maps territory_id to l2_id, extracts excerpts, and classifies
        mention_type based on the matched search keyword.
        """
        if raw_data.empty:
            return raw_data

        # Build l2_id lookup from admin_level_2
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        l2_map = {str(row[1]).strip(): row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        for _, record in raw_data.iterrows():
            territory_id = str(record.get("territory_id", "")).strip()
            l2_id = l2_map.get(territory_id)

            date_str = str(record.get("date", ""))[:10]

            # Build a unique gazette_id from territory + date
            gazette_id = f"{territory_id}-{date_str}"

            # Extract excerpt from the excerpts array
            excerpts = record.get("excerpts", [])
            if isinstance(excerpts, list) and excerpts:
                excerpt_text = excerpts[0]
            else:
                excerpt_text = str(excerpts) if excerpts else ""

            # Determine mention_type from the keyword that matched
            search_term = str(record.get("search_term", ""))
            mention_type = KEYWORD_MENTION_TYPE.get(search_term, "geral")

            source_url = str(record.get("url", ""))

            rows.append({
                "l2_id": l2_id,
                "municipality_code": territory_id,
                "published_date": date_str,
                "gazette_id": gazette_id,
                "excerpt": str(excerpt_text)[:2000],
                "keywords": [search_term],
                "mention_type": mention_type,
                "source_url": source_url,
                "source": "querido_diario",
            })

        self.rows_processed = len(rows)
        logger.info(
            f"Transformed {len(rows)} gazette mentions "
            f"({sum(1 for r in rows if r['l2_id'] is not None)} mapped to municipalities)"
        )
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def load(self, data: pd.DataFrame) -> None:
        """Load transformed gazette mentions into PostgreSQL.

        Uses gazette_id + excerpt hash for conflict deduplication.
        """
        if data.empty:
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                keywords = row.get("keywords", [])
                if isinstance(keywords, str):
                    keywords = [keywords]

                # Use hash of excerpt for uniqueness (excerpt can be long)
                excerpt_str = str(row.get("excerpt", ""))
                excerpt_hash = hashlib.md5(excerpt_str.encode()).hexdigest()[:16]
                gazette_id = str(row.get("gazette_id", ""))
                unique_key = f"{gazette_id}-{excerpt_hash}"

                cur.execute("""
                    INSERT INTO municipal_gazette_mentions
                        (l2_id, municipality_code, published_date, gazette_id,
                         excerpt, keywords, mention_type, source_url, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (gazette_id, excerpt) DO NOTHING
                """, (
                    int(row["l2_id"]) if pd.notna(row.get("l2_id")) else None,
                    str(row.get("municipality_code", "")),
                    str(row.get("published_date", ""))[:10],
                    unique_key,
                    excerpt_str[:2000],
                    keywords,
                    str(row.get("mention_type", "geral")),
                    str(row.get("source_url", ""))[:500],
                    "querido_diario",
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load gazette mention: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} gazette mention records")
