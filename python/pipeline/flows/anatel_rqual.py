"""ANATEL Quality Indicators Pipeline.

Source: Real broadband subscriber data (ANATEL) already in database
Derivation: Quality metrics computed from subscriber growth, technology mix,
            provider diversity, and market concentration per municipality.

ANATEL's RQUAL/IQS quality seal data is not available via public API
(dados.gov.br CKAN endpoints are broken). Instead, we compute quality
proxy metrics from real ANATEL broadband subscriber data:
- Speed proxy: fiber subscriber ratio (fiber = higher speeds)
- Competition: HHI-based market concentration
- Growth: subscriber growth rate
- Diversity: number of active providers

These are real derived metrics from 4.1M+ ANATEL broadband records.
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


class AnatelRQUALPipeline(BasePipeline):
    """Compute quality proxy metrics from real ANATEL broadband data."""

    def __init__(self):
        super().__init__("anatel_rqual")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS quality_seals (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                provider_id INTEGER REFERENCES providers(id),
                year_half CHAR(6),
                overall_score NUMERIC,
                availability_score NUMERIC,
                speed_score NUMERIC,
                latency_score NUMERIC,
                seal_level VARCHAR(20),
                source VARCHAR(50) DEFAULT 'anatel_derived',
                UNIQUE (l2_id, provider_id, year_half)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM quality_seals")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        """Try ANATEL CKAN first; derive from real broadband data if unavailable."""
        with PipelineHTTPClient(timeout=180) as http:
            # Try dados.gov.br CKAN (may work in the future)
            for dataset_id in [
                "indicadores-de-qualidade-do-scm",
                "indicadores-de-qualidade",
            ]:
                try:
                    url = http.resolve_ckan_resource_url(
                        dataset_id, resource_format="CSV"
                    )
                    logger.info(f"Downloading RQUAL CSV from: {url}")
                    df = http.get_csv(url, sep=";", encoding="latin-1")
                    if len(df) > 100:
                        logger.info(f"Downloaded {len(df)} rows from ANATEL RQUAL")
                        return df
                except Exception as e:
                    logger.warning(f"RQUAL CKAN '{dataset_id}' failed: {e}")

        # Derive quality metrics from real broadband subscriber data
        logger.info("ANATEL RQUAL not available via CKAN. "
                     "Deriving quality metrics from real broadband subscriber data.")
        return self._derive_from_broadband()

    def _derive_from_broadband(self) -> pd.DataFrame:
        """Compute quality proxy metrics from real ANATEL broadband data.

        Uses 4.1M+ real subscriber records to compute:
        - Speed score: fiber subscriber ratio (fiber = higher average speeds)
        - Availability score: subscriber growth rate (growing = stable service)
        - Overall score: weighted combination
        - Seal level: based on overall score thresholds
        """
        conn = self._get_connection()
        cur = conn.cursor()

        # Get latest year_month
        cur.execute("SELECT MAX(year_month) FROM broadband_subscribers")
        latest = cur.fetchone()[0]
        if not latest:
            cur.close()
            conn.close()
            raise RuntimeError("No broadband subscriber data in database")

        # Get previous period for growth calculation (6 months back)
        latest_year = int(latest[:4])
        latest_month = int(latest[5:7])
        prev_month = latest_month - 6
        prev_year = latest_year
        if prev_month <= 0:
            prev_month += 12
            prev_year -= 1
        prev_ym = f"{prev_year}-{prev_month:02d}"

        year_half = f"{latest_year}S{'1' if latest_month <= 6 else '2'}"

        # Compute per-provider per-municipality quality metrics
        cur.execute("""
            WITH current_data AS (
                SELECT l2_id, provider_id, technology,
                       SUM(subscribers) AS subs
                FROM broadband_subscribers
                WHERE year_month = %s
                GROUP BY l2_id, provider_id, technology
            ),
            provider_totals AS (
                SELECT l2_id, provider_id,
                       SUM(subs) AS total_subs,
                       SUM(CASE WHEN technology = 'fiber' THEN subs ELSE 0 END) AS fiber_subs,
                       COUNT(DISTINCT technology) AS tech_count
                FROM current_data
                GROUP BY l2_id, provider_id
                HAVING SUM(subs) > 0
            ),
            prev_data AS (
                SELECT l2_id, provider_id, SUM(subscribers) AS prev_subs
                FROM broadband_subscribers
                WHERE year_month = %s
                GROUP BY l2_id, provider_id
            ),
            muni_totals AS (
                SELECT l2_id, SUM(total_subs) AS muni_total
                FROM provider_totals
                GROUP BY l2_id
            )
            SELECT pt.l2_id, pt.provider_id,
                   pt.total_subs, pt.fiber_subs, pt.tech_count,
                   COALESCE(pd.prev_subs, 0) AS prev_subs,
                   mt.muni_total
            FROM provider_totals pt
            LEFT JOIN prev_data pd ON pd.l2_id = pt.l2_id AND pd.provider_id = pt.provider_id
            JOIN muni_totals mt ON mt.l2_id = pt.l2_id
        """, (latest, prev_ym))

        rows = []
        for l2_id, provider_id, total_subs, fiber_subs, tech_count, prev_subs, muni_total in cur.fetchall():
            # Cast Decimal to float for arithmetic
            total_subs = float(total_subs or 0)
            fiber_subs = float(fiber_subs or 0)
            prev_subs = float(prev_subs or 0)
            muni_total = float(muni_total or 0)
            tech_count = int(tech_count or 0)

            # Speed score: fiber ratio (0-100)
            fiber_ratio = fiber_subs / max(total_subs, 1)
            speed_score = round(min(100, fiber_ratio * 100), 1)

            # Availability score: growth stability (0-100)
            # Positive growth = good availability, negative = problems
            if prev_subs > 0:
                growth_rate = (total_subs - prev_subs) / prev_subs
                # Map growth to score: -10% = 50, 0% = 70, +10% = 90
                availability_score = round(min(100, max(0, 70 + growth_rate * 200)), 1)
            else:
                availability_score = 60.0  # New provider, neutral

            # Latency proxy: technology diversity (more tech = better coverage options)
            latency_score = round(min(100, tech_count * 30 + 20), 1)

            # Market share in municipality
            market_share = total_subs / max(muni_total, 1)

            # Overall: weighted average
            overall = round(
                speed_score * 0.4 +
                availability_score * 0.3 +
                latency_score * 0.3,
                1
            )

            # Seal level based on ANATEL-style thresholds
            if overall >= 80:
                seal = "ouro"
            elif overall >= 60:
                seal = "prata"
            elif overall >= 40:
                seal = "bronze"
            else:
                seal = "sem_selo"

            rows.append({
                "l2_id": l2_id,
                "provider_id": provider_id,
                "year_half": year_half,
                "overall_score": overall,
                "availability_score": availability_score,
                "speed_score": speed_score,
                "latency_score": latency_score,
                "seal_level": seal,
            })

        cur.close()
        conn.close()
        logger.info(f"Derived {len(rows)} quality metrics from real broadband data")
        return pd.DataFrame(rows)

    def validate_raw(self, data) -> None:
        if isinstance(data, pd.DataFrame) and data.empty:
            raise ValueError("No quality data computed")
        logger.info(f"Validating {len(data)} quality records")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        if raw_data.empty:
            return raw_data

        # If already processed (derived from broadband), return as-is
        if "l2_id" in raw_data.columns and "seal_level" in raw_data.columns:
            self.rows_processed = len(raw_data)
            return raw_data

        # Real CKAN data: map columns
        cols = {c.upper().strip(): c for c in raw_data.columns}

        code_col = None
        for candidate in ["CODIGO_IBGE", "MUNICIPIO_CODIGO", "CD_MUNICIPIO", "COD_MUNICIPIO"]:
            if candidate in cols:
                code_col = cols[candidate]
                break

        cnpj_col = None
        for candidate in ["CNPJ", "CNPJ_PRESTADORA", "NR_CNPJ"]:
            if candidate in cols:
                cnpj_col = cols[candidate]
                break

        if not code_col:
            logger.warning(f"Could not find municipality code column. Columns: {list(raw_data.columns)}")
            self.rows_processed = 0
            return pd.DataFrame()

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        l2_map = {str(row[1]).strip(): row[0] for row in cur.fetchall()}
        cur.execute("SELECT id, national_id FROM providers WHERE national_id IS NOT NULL")
        provider_map = {}
        for pid, nid in cur.fetchall():
            clean = nid.strip().replace(".", "").replace("/", "").replace("-", "")
            provider_map[clean] = pid
        cur.close()
        conn.close()

        rows = []
        for _, record in raw_data.iterrows():
            code = str(record.get(code_col, "")).strip()[:7]
            l2_id = l2_map.get(code)
            if not l2_id:
                continue

            provider_id = None
            if cnpj_col:
                cnpj = str(record.get(cnpj_col, "")).strip().replace(".", "").replace("/", "").replace("-", "")
                provider_id = provider_map.get(cnpj)

            def safe_float(val):
                try:
                    return float(str(val).replace(",", "."))
                except (ValueError, TypeError):
                    return None

            overall = None
            for c in ["IQS", "NOTA_GERAL", "SCORE_GERAL", "OVERALL"]:
                if c in cols:
                    overall = safe_float(record.get(cols[c]))
                    if overall is not None:
                        break

            seal = "sem_selo"
            if overall and overall >= 80:
                seal = "ouro"
            elif overall and overall >= 60:
                seal = "prata"
            elif overall and overall >= 40:
                seal = "bronze"

            rows.append({
                "l2_id": l2_id,
                "provider_id": provider_id,
                "year_half": "2025S1",
                "overall_score": overall,
                "availability_score": None,
                "speed_score": None,
                "latency_score": None,
                "seal_level": seal,
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} RQUAL records")
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            logger.warning("No quality data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO quality_seals
                        (l2_id, provider_id, year_half, overall_score,
                         availability_score, speed_score, latency_score, seal_level, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'anatel_derived')
                    ON CONFLICT (l2_id, provider_id, year_half) DO UPDATE SET
                        overall_score = EXCLUDED.overall_score,
                        availability_score = EXCLUDED.availability_score,
                        speed_score = EXCLUDED.speed_score,
                        latency_score = EXCLUDED.latency_score,
                        seal_level = EXCLUDED.seal_level
                """, (
                    int(row["l2_id"]) if pd.notna(row.get("l2_id")) else None,
                    int(row["provider_id"]) if pd.notna(row.get("provider_id")) else None,
                    str(row.get("year_half", "2025S1")),
                    float(row["overall_score"]) if pd.notna(row.get("overall_score")) else None,
                    float(row["availability_score"]) if pd.notna(row.get("availability_score")) else None,
                    float(row["speed_score"]) if pd.notna(row.get("speed_score")) else None,
                    float(row["latency_score"]) if pd.notna(row.get("latency_score")) else None,
                    str(row.get("seal_level", "sem_selo")),
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load quality row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} quality seal records")
