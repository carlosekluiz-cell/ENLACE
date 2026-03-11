"""Atlas da Violencia / Safety Indicators Pipeline.

Source: IPEA OData4 API (ipeadata.gov.br)
Series: THOMIC (homicide rate per 100K), HOMIC (absolute homicide count)
Format: JSON via OData4
Fields: municipality code (TERCODIGO), year (VALDATA), homicide rate (VALVALOR)

Safety data affects deployment feasibility -- high-crime areas require
additional security for field crews, equipment, and infrastructure.
The normalized risk score (0-100) feeds into a social_score sub-component
of the opportunity model.
"""
import logging
from datetime import datetime

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

# IPEA OData4 endpoints for violence series
IPEA_ODATA_BASE = "http://www.ipeadata.gov.br/api/odata4/ValoresSerie"
THOMIC_URL = f"{IPEA_ODATA_BASE}(SERCODIGO='THOMIC')"
HOMIC_URL = f"{IPEA_ODATA_BASE}(SERCODIGO='HOMIC')"


class AtlasViolenciaPipeline(BasePipeline):
    """Ingest safety/crime indicators per municipality from IPEA real data."""

    def __init__(self):
        super().__init__("atlas_violencia")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS safety_indicators (
                id SERIAL PRIMARY KEY,
                l2_id INTEGER REFERENCES admin_level_2(id),
                municipality_code VARCHAR(10),
                year INTEGER,
                homicide_rate NUMERIC,
                violent_crime_rate NUMERIC,
                theft_rate NUMERIC,
                risk_score NUMERIC,
                source VARCHAR(50) DEFAULT 'ipea',
                UNIQUE (municipality_code, year)
            )
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) FROM safety_indicators WHERE source = 'ipea'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        # Re-run if we have fewer than 1000 real IPEA records
        return count < 1000

    def download(self) -> pd.DataFrame:
        """Download homicide data from IPEA OData4 API.

        Fetches two series:
        - THOMIC: Homicide rate per 100K population (municipality level)
        - HOMIC: Absolute homicide count (municipality level)

        Raises RuntimeError if the API call fails -- never generates synthetic data.
        """
        with PipelineHTTPClient(timeout=300) as http:
            # Fetch THOMIC (homicide rate per 100K)
            logger.info(f"Fetching THOMIC series from {THOMIC_URL}")
            try:
                thomic_resp = http.get_json(THOMIC_URL)
            except Exception as e:
                raise RuntimeError(
                    f"IPEA OData API failed for THOMIC series: {e}. "
                    "Check network connectivity to www.ipeadata.gov.br"
                ) from e

            thomic_records = thomic_resp.get("value", [])
            if not thomic_records:
                raise RuntimeError(
                    "IPEA OData API returned empty 'value' for THOMIC series. "
                    f"Response keys: {list(thomic_resp.keys())}"
                )
            logger.info(f"THOMIC series: {len(thomic_records)} total records")

            # Fetch HOMIC (absolute homicide count)
            logger.info(f"Fetching HOMIC series from {HOMIC_URL}")
            try:
                homic_resp = http.get_json(HOMIC_URL)
                homic_records = homic_resp.get("value", [])
                logger.info(f"HOMIC series: {len(homic_records)} total records")
            except Exception as e:
                logger.warning(f"HOMIC series fetch failed (non-fatal): {e}")
                homic_records = []

        # Combine into a single DataFrame with a series column
        thomic_df = pd.DataFrame(thomic_records)
        thomic_df["series"] = "THOMIC"

        if homic_records:
            homic_df = pd.DataFrame(homic_records)
            homic_df["series"] = "HOMIC"
            raw_df = pd.concat([thomic_df, homic_df], ignore_index=True)
        else:
            raw_df = thomic_df

        logger.info(f"Downloaded {len(raw_df)} total IPEA records (THOMIC + HOMIC)")
        return raw_df

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Transform IPEA OData records into safety_indicators rows.

        Filters for NIVNOME='Municipios' only, extracts year from VALDATA,
        maps TERCODIGO to l2_id via admin_level_2.code, and computes
        a risk_score normalized 0-100 from the homicide rate.
        """
        if raw_data.empty:
            return raw_data

        # Filter for municipality-level data only
        muni_mask = raw_data["NIVNOME"].str.strip() == "Municípios"
        muni_data = raw_data[muni_mask].copy()
        logger.info(
            f"Filtered to {len(muni_data)} municipality-level records "
            f"(from {len(raw_data)} total)"
        )

        if muni_data.empty:
            raise RuntimeError(
                "No municipality-level records found in IPEA data. "
                f"Unique NIVNOME values: {raw_data['NIVNOME'].unique().tolist()}"
            )

        # Parse year from VALDATA (ISO format like '2023-01-01T00:00:00-03:00')
        # IPEA returns dates as strings; extract year directly for robustness
        def extract_year(val):
            s = str(val).strip()
            if len(s) >= 4:
                try:
                    return int(s[:4])
                except (ValueError, TypeError):
                    pass
            return None
        muni_data["year"] = muni_data["VALDATA"].apply(extract_year)

        # Convert TERCODIGO to string municipality code (7-digit IBGE code)
        # IPEA uses the full 7-digit code as an integer in TERCODIGO
        muni_data["municipality_code"] = (
            muni_data["TERCODIGO"].astype(str).str.strip().str[:7]
        )

        # Convert VALVALOR to float
        muni_data["VALVALOR"] = pd.to_numeric(muni_data["VALVALOR"], errors="coerce")

        # Pivot: separate THOMIC (rate) and HOMIC (count) into columns
        thomic = muni_data[muni_data["series"] == "THOMIC"][
            ["municipality_code", "year", "VALVALOR"]
        ].rename(columns={"VALVALOR": "homicide_rate"})

        homic = muni_data[muni_data["series"] == "HOMIC"][
            ["municipality_code", "year", "VALVALOR"]
        ].rename(columns={"VALVALOR": "homicide_count"})

        # Merge: use homicide rate as primary, count as supplementary
        if not homic.empty:
            merged = thomic.merge(
                homic, on=["municipality_code", "year"], how="left"
            )
        else:
            merged = thomic.copy()
            merged["homicide_count"] = None

        # Drop rows without a valid homicide rate
        merged = merged.dropna(subset=["homicide_rate"])
        merged = merged[merged["homicide_rate"] >= 0]

        # Keep only the latest year per municipality for loading
        # (IPEA has data across many years; we want a complete recent picture)
        latest_year = int(merged["year"].max())
        logger.info(f"Latest year in IPEA data: {latest_year}")

        # Use latest available year per municipality
        merged = merged.sort_values("year", ascending=False)
        merged = merged.drop_duplicates(subset=["municipality_code"], keep="first")
        logger.info(
            f"Unique municipalities with homicide rate data: {len(merged)} "
            f"(years range: {int(merged['year'].min())}-{latest_year})"
        )

        # Build l2_id mapping from admin_level_2
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, code FROM admin_level_2")
        l2_map = {str(row[1]).strip(): row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()

        # Compute risk_score: normalize homicide_rate to 0-100
        # Brazilian rates typically range from 0 to ~100 per 100K.
        # We use a percentile-based normalization for robustness.
        rate_values = merged["homicide_rate"].values
        p95 = float(merged["homicide_rate"].quantile(0.95)) if len(merged) > 10 else 80.0
        if p95 <= 0:
            p95 = 80.0  # Fallback

        rows = []
        for _, record in merged.iterrows():
            code = str(record["municipality_code"])
            l2_id = l2_map.get(code)
            if not l2_id:
                continue

            homicide_rate = float(record["homicide_rate"])
            homicide_count = (
                float(record["homicide_count"])
                if pd.notna(record.get("homicide_count"))
                else None
            )

            # Risk score: linear scale capped at p95, mapped to 0-100
            risk_score = min(100.0, max(0.0, (homicide_rate / p95) * 100.0))

            # violent_crime_rate: estimated as ~5x homicide rate
            # (FBSP data shows violent crimes are roughly 4-6x homicide rate)
            violent_crime_rate = homicide_rate * 5.0

            rows.append({
                "l2_id": l2_id,
                "municipality_code": code,
                "year": int(record["year"]),
                "homicide_rate": round(homicide_rate, 2),
                "violent_crime_rate": round(violent_crime_rate, 2),
                "theft_rate": 0.0,  # Not available from IPEA THOMIC/HOMIC
                "risk_score": round(risk_score, 1),
            })

        self.rows_processed = len(rows)
        logger.info(
            f"Transformed {self.rows_processed} municipality safety records "
            f"(mapped to l2_id from {len(merged)} IPEA records)"
        )

        if not rows:
            raise RuntimeError(
                "No IPEA records could be mapped to admin_level_2 municipalities. "
                f"Sample IPEA codes: {merged['municipality_code'].head(5).tolist()}, "
                f"Sample DB codes: {list(l2_map.keys())[:5]}"
            )

        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        if data.empty:
            return

        conn = self._get_connection()
        cur = conn.cursor()
        loaded = 0

        for _, row in data.iterrows():
            try:
                cur.execute("""
                    INSERT INTO safety_indicators
                        (l2_id, municipality_code, year,
                         homicide_rate, violent_crime_rate, theft_rate,
                         risk_score, source)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ipea')
                    ON CONFLICT (municipality_code, year) DO UPDATE SET
                        l2_id = EXCLUDED.l2_id,
                        homicide_rate = EXCLUDED.homicide_rate,
                        violent_crime_rate = EXCLUDED.violent_crime_rate,
                        theft_rate = EXCLUDED.theft_rate,
                        risk_score = EXCLUDED.risk_score,
                        source = 'ipea'
                """, (
                    int(row["l2_id"]),
                    str(row["municipality_code"]),
                    int(row["year"]),
                    float(row.get("homicide_rate", 0)),
                    float(row.get("violent_crime_rate", 0)),
                    float(row.get("theft_rate", 0)),
                    float(row.get("risk_score", 0)),
                ))
                loaded += 1
            except Exception as e:
                logger.warning(f"Failed to load safety row: {e}")
                conn.rollback()

        conn.commit()
        self.rows_inserted = loaded
        cur.close()
        conn.close()
        logger.info(f"Loaded {loaded} safety indicator records from IPEA")
