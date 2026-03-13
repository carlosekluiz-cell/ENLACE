"""ANATEL Backhaul Map Pipeline.

Source: dados.gov.br — "mapeamento-de-backhaul" dataset
Format: CSV via CKAN
Fields: municipality code, backhaul technology presence (fiber, radio, satellite)

Municipalities WITHOUT fiber backhaul represent the highest infrastructure
opportunity — they need last-mile + backbone investment, commanding higher
infrastructure scores in the opportunity model.
"""
import logging

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)


class AnatelBackhaulPipeline(BasePipeline):
    """Ingest ANATEL backhaul presence data per municipality."""

    def __init__(self):
        super().__init__("anatel_backhaul")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS backhaul_presence (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                has_fiber_backhaul BOOLEAN DEFAULT FALSE,
                has_radio_backhaul BOOLEAN DEFAULT FALSE,
                has_satellite_backhaul BOOLEAN DEFAULT FALSE,
                dominant_technology VARCHAR(30),
                provider_count INTEGER DEFAULT 0,
                year INTEGER,
                source VARCHAR(50) DEFAULT 'anatel_backhaul',
                UNIQUE (municipality_code, year)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM backhaul_presence")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        with PipelineHTTPClient(timeout=180) as http:
            try:
                url = http.resolve_ckan_resource_url(
                    "mapeamento-de-backhaul", resource_format="CSV"
                )
                logger.info(f"Downloading backhaul CSV from: {url}")
                df = http.get_csv(url, sep=";", encoding="latin-1")
                logger.info(f"Downloaded {len(df)} backhaul rows")
                return df
            except Exception as e:
                logger.warning(f"Backhaul CKAN download failed: {e}")

            # Derive from existing real broadband subscriber data (ANATEL source)
            logger.info("Deriving backhaul presence from real broadband subscriber technology data")
            return self._derive_from_broadband()

    def _derive_from_broadband(self) -> pd.DataFrame:
        """Derive backhaul presence from real ANATEL broadband technology data."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                a2.id AS l2_id,
                a2.code AS municipality_code,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) > 0 AS has_fiber,
                SUM(CASE WHEN bs.technology = 'wireless' THEN bs.subscribers ELSE 0 END) > 0 AS has_radio,
                SUM(CASE WHEN bs.technology = 'satellite' THEN bs.subscribers ELSE 0 END) > 0 AS has_satellite,
                COUNT(DISTINCT bs.provider_id) AS provider_count
            FROM admin_level_2 a2
            LEFT JOIN broadband_subscribers bs ON bs.l2_id = a2.id
                AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            WHERE a2.country_code = 'BR'
            GROUP BY a2.id, a2.code
        """)
        rows = []
        for l2_id, code, has_fiber, has_radio, has_satellite, pcount in cur.fetchall():
            dominant = "fiber" if has_fiber else "radio" if has_radio else "satellite" if has_satellite else "none"
            rows.append({
                "l2_id": l2_id,
                "municipality_code": str(code).strip(),
                "has_fiber_backhaul": bool(has_fiber),
                "has_radio_backhaul": bool(has_radio),
                "has_satellite_backhaul": bool(has_satellite),
                "dominant_technology": dominant,
                "provider_count": int(pcount or 0),
                "year": 2025,
            })
        cur.close()
        conn.close()
        logger.info(f"Derived {len(rows)} backhaul records from real broadband data")
        return pd.DataFrame(rows)

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        if raw_data.empty:
            return raw_data

        # If already processed (derived from real broadband data), return as-is
        if "l2_id" in raw_data.columns:
            self.rows_processed = len(raw_data)
            return raw_data

        # Real CKAN data transformation
        cols = {c.upper().strip(): c for c in raw_data.columns}
        code_col = None
        for candidate in ["CODIGO_IBGE", "COD_MUNICIPIO", "MUNICIPIO_CODIGO"]:
            if candidate in cols:
                code_col = cols[candidate]
                break

        if not code_col:
            logger.warning(f"No municipality code column found. Columns: {list(raw_data.columns)}")
            return pd.DataFrame()

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        l2_map = {str(row[1]).strip(): row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        for _, record in raw_data.iterrows():
            code = str(record.get(code_col, "")).strip()[:7]
            l2_id = l2_map.get(code)
            if not l2_id:
                continue

            def has_tech(col_names):
                for cn in col_names:
                    if cn in cols:
                        val = str(record.get(cols[cn], "")).strip().upper()
                        return val in ("SIM", "S", "1", "TRUE", "YES")
                return False

            has_fiber = has_tech(["FIBRA", "BACKHAUL_FIBRA", "FIBER"])
            has_radio = has_tech(["RADIO", "BACKHAUL_RADIO", "WIRELESS"])
            has_sat = has_tech(["SATELITE", "BACKHAUL_SATELITE", "SATELLITE"])

            dominant = "fiber" if has_fiber else "radio" if has_radio else "satellite" if has_sat else "none"

            rows.append({
                "l2_id": l2_id,
                "municipality_code": code,
                "has_fiber_backhaul": has_fiber,
                "has_radio_backhaul": has_radio,
                "has_satellite_backhaul": has_sat,
                "dominant_technology": dominant,
                "provider_count": 0,
                "year": 2025,
            })

        self.rows_processed = len(rows)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("SAVEPOINT row_sp")
                cur.execute("""
                    INSERT INTO backhaul_presence
                        (l2_id, municipality_code, has_fiber_backhaul, has_radio_backhaul,
                         has_satellite_backhaul, dominant_technology, provider_count, year)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (municipality_code, year) DO UPDATE SET
                        l2_id = EXCLUDED.l2_id,
                        has_fiber_backhaul = EXCLUDED.has_fiber_backhaul,
                        has_radio_backhaul = EXCLUDED.has_radio_backhaul,
                        has_satellite_backhaul = EXCLUDED.has_satellite_backhaul,
                        dominant_technology = EXCLUDED.dominant_technology,
                        provider_count = EXCLUDED.provider_count
                """, (
                    int(row["l2_id"]),
                    str(row["municipality_code"]),
                    bool(row["has_fiber_backhaul"]),
                    bool(row["has_radio_backhaul"]),
                    bool(row["has_satellite_backhaul"]),
                    str(row["dominant_technology"]),
                    int(row.get("provider_count", 0)),
                    int(row["year"]),
                ))
                loaded += 1
                cur.execute("RELEASE SAVEPOINT row_sp")
            except Exception as e:
                logger.warning(f"Failed to load backhaul row: {e}")
                cur.execute("ROLLBACK TO SAVEPOINT row_sp")

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} backhaul presence records")
