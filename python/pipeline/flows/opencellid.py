"""OpenCelliD cell tower pipeline.

Source: OpenCelliD community database (unwiredlabs.com)
URL: https://opencellid.org/ocid/downloads?token={token}&type=mcc&file={mcc}.csv.gz
Format: Gzipped CSV with columns: radio, mcc, net, area, cell, unit, lon, lat,
        range, samples, changeable, created, updated, averageSignal
MCC 724 = Brazil, MCC 732 = Colombia

Downloads country-filtered CSVs, inserts into opencellid_towers,
matches to existing base_stations within 500m, and spatial-joins to
admin_level_2 for municipality assignment.
"""

import gzip
import io
import logging
import os

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import (
    BRAZIL_BBOX, COLOMBIA_BBOX,
    MEXICO_BBOX, ARGENTINA_BBOX, CHILE_BBOX, PERU_BBOX, ECUADOR_BBOX,
    VENEZUELA_BBOX, BOLIVIA_BBOX, PARAGUAY_BBOX, URUGUAY_BBOX,
    PANAMA_BBOX, COSTA_RICA_BBOX, GUATEMALA_BBOX, HONDURAS_BBOX,
    EL_SALVADOR_BBOX, NICARAGUA_BBOX, DOMINICAN_REPUBLIC_BBOX, CUBA_BBOX,
)
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

OPENCELLID_DOWNLOAD_URL = (
    "https://opencellid.org/ocid/downloads?token={token}&type=mcc&file={mcc}.csv.gz"
)

# Country MCC codes and bounding boxes
COUNTRY_MCC_CONFIG = {
    724: {"name": "Brazil", "bbox": BRAZIL_BBOX},
    732: {"name": "Colombia", "bbox": COLOMBIA_BBOX},
    334: {"name": "Mexico", "bbox": MEXICO_BBOX},
    722: {"name": "Argentina", "bbox": ARGENTINA_BBOX},
    730: {"name": "Chile", "bbox": CHILE_BBOX},
    716: {"name": "Peru", "bbox": PERU_BBOX},
    740: {"name": "Ecuador", "bbox": ECUADOR_BBOX},
    734: {"name": "Venezuela", "bbox": VENEZUELA_BBOX},
    736: {"name": "Bolivia", "bbox": BOLIVIA_BBOX},
    744: {"name": "Paraguay", "bbox": PARAGUAY_BBOX},
    748: {"name": "Uruguay", "bbox": URUGUAY_BBOX},
    714: {"name": "Panama", "bbox": PANAMA_BBOX},
    712: {"name": "Costa Rica", "bbox": COSTA_RICA_BBOX},
    704: {"name": "Guatemala", "bbox": GUATEMALA_BBOX},
    708: {"name": "Honduras", "bbox": HONDURAS_BBOX},
    706: {"name": "El Salvador", "bbox": EL_SALVADOR_BBOX},
    710: {"name": "Nicaragua", "bbox": NICARAGUA_BBOX},
    370: {"name": "Dominican Republic", "bbox": DOMINICAN_REPUBLIC_BBOX},
    368: {"name": "Cuba", "bbox": CUBA_BBOX},
}

# MNC -> operator name mapping for MCC 724 (Brazil)
MNC_OPERATOR_MAP = {
    2: "TIM",
    3: "TIM",
    4: "TIM",
    5: "Claro",
    6: "Vivo",
    10: "Vivo",
    11: "Vivo",
    23: "Vivo",
    31: "Oi",
    32: "Oi",
}

# MNC -> operator name mapping for MCC 732 (Colombia)
MNC_OPERATOR_MAP_CO = {
    101: "Claro",
    102: "Movistar",
    103: "Tigo",
    111: "Tigo",
    123: "Movistar",
    130: "Avantel",
    142: "UNE",
    154: "Virgin",
    165: "WOM",
    187: "ETB",
    199: "DIRECTV",
}


class OpenCelliDPipeline(BasePipeline):
    """Ingest OpenCelliD cell tower data for all 19 LATAM countries."""

    def __init__(self):
        super().__init__("opencellid")

    def check_for_updates(self) -> bool:
        """Run if the table is empty, has fewer than 1000 rows, or
        a previous run left rows without municipality assignment
        (indicating the matching/spatial-join step failed)."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM opencellid_towers")
        total = cur.fetchone()[0]
        if total < 1000:
            cur.close()
            conn.close()
            return True
        # Detect partial failure: rows exist but municipality assignment incomplete
        cur.execute("SELECT COUNT(*) FROM opencellid_towers WHERE l2_id IS NOT NULL")
        assigned = cur.fetchone()[0]
        cur.close()
        conn.close()
        if assigned < total * 0.5:
            logger.warning(
                "Detected partial load: %d rows but only %d with l2_id assigned. "
                "Will re-run pipeline.", total, assigned
            )
            return True
        return False

    def download(self) -> pd.DataFrame:
        """Download OpenCelliD CSVs for Brazil and Colombia (gzipped)."""
        token = os.getenv("OPENCELLID_TOKEN")
        if not token:
            raise ValueError(
                "OPENCELLID_TOKEN environment variable is required. "
                "Register at https://opencellid.org to obtain an API token."
            )

        OPENCELLID_COLUMNS = [
            "radio", "mcc", "net", "area", "cell", "unit",
            "lon", "lat", "range", "samples", "changeable",
            "created", "updated", "averageSignal",
        ]

        all_dfs = []
        with PipelineHTTPClient(timeout=600) as http:
            for mcc in COUNTRY_MCC_CONFIG:
                country_name = COUNTRY_MCC_CONFIG[mcc]["name"]
                url = OPENCELLID_DOWNLOAD_URL.format(token=token, mcc=mcc)
                cache_path = get_cache_path(f"opencellid_{mcc}.csv.gz")

                try:
                    logger.info(f"Downloading OpenCelliD {country_name} (MCC={mcc}) data...")
                    http.download_file(url, cache_path, resume=False)

                    logger.info(f"Decompressing {cache_path}...")
                    with gzip.open(cache_path, "rt", encoding="utf-8", errors="replace") as f:
                        df = pd.read_csv(f, dtype=str, on_bad_lines="skip", header=None, names=OPENCELLID_COLUMNS)

                    logger.info(f"Downloaded {len(df)} OpenCelliD records for {country_name}")
                    all_dfs.append(df)
                except Exception as e:
                    logger.warning(f"Could not download OpenCelliD MCC={mcc} ({country_name}): {e}")

        if not all_dfs:
            raise ValueError("No OpenCelliD data could be downloaded for any country")

        combined = pd.concat(all_dfs, ignore_index=True)
        logger.info(f"Total OpenCelliD records: {len(combined)}")
        return combined

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Empty OpenCelliD CSV")
        required = {"radio", "mcc", "net", "lon", "lat"}
        missing = required - set(data.columns)
        if missing:
            raise ValueError(f"Missing required columns: {missing}")
        logger.info(f"OpenCelliD CSV columns: {list(data.columns)}")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Parse and filter OpenCelliD records to Brazil and Colombia bounds."""
        df = raw_data.copy()

        rows = []
        for _, row in df.iterrows():
            try:
                mcc = int(row.get("mcc", 0))
                if mcc not in COUNTRY_MCC_CONFIG:
                    continue

                lat = float(row.get("lat", 0))
                lon = float(row.get("lon", 0))

                # Validate bounds for the corresponding country
                bbox = COUNTRY_MCC_CONFIG[mcc]["bbox"]
                if not (bbox["min_lat"] <= lat <= bbox["max_lat"]
                        and bbox["min_lon"] <= lon <= bbox["max_lon"]):
                    continue

                mnc = int(row.get("net", 0))
                cell_id = int(row.get("cell", 0))
                lac = int(row.get("area", 0))
                radio = str(row.get("radio", "")).strip().upper()

                range_m_raw = row.get("range", "0")
                try:
                    range_m = int(float(range_m_raw))
                except (ValueError, TypeError):
                    range_m = 0

                samples_raw = row.get("samples", "0")
                try:
                    samples = int(float(samples_raw))
                except (ValueError, TypeError):
                    samples = 0

                rows.append({
                    "cell_id": cell_id,
                    "mcc": mcc,
                    "mnc": mnc,
                    "lac": lac,
                    "radio": radio[:10] if radio else None,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "range_m": range_m,
                    "samples": samples,
                })
            except (ValueError, TypeError):
                continue

        result = pd.DataFrame(rows)
        if not result.empty:
            # Deduplicate by cell_id (keep the one with most samples)
            result = result.sort_values("samples", ascending=False)
            result = result.drop_duplicates(subset=["cell_id"], keep="first")

        self.rows_processed = len(result)
        logger.info(f"Transformed {len(result)} valid OpenCelliD towers within Brazil bounds")
        return result

    def load(self, data: pd.DataFrame) -> None:
        """Insert OpenCelliD records, then match to base_stations and assign l2_id."""
        if data.empty:
            logger.warning("No OpenCelliD towers to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Clear existing data for a clean reload
        cur.execute("DELETE FROM opencellid_towers")
        conn.commit()

        from psycopg2.extras import execute_values

        # Insert tower records
        values = []
        for _, row in data.iterrows():
            values.append((
                row["cell_id"],
                row["mcc"],
                row["mnc"],
                row["lac"],
                row["radio"],
                row["latitude"],
                row["longitude"],
                row["range_m"],
                row["samples"],
            ))

        execute_values(cur, """
            INSERT INTO opencellid_towers
            (cell_id, mcc, mnc, lac, radio, latitude, longitude, range_m, samples)
            VALUES %s
        """, values, template=(
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ), page_size=5000)
        conn.commit()
        self.rows_inserted = len(values)
        logger.info(f"Inserted {self.rows_inserted} OpenCelliD towers")

        # Match to existing base_stations within ~500m
        # ST_DWithin on geography type uses meters; on geometry(4326) uses degrees
        # 0.005 degrees ~ 500m at equatorial latitudes
        logger.info("Matching OpenCelliD towers to base_stations (within ~500m)...")
        cur.execute("""
            UPDATE opencellid_towers
            SET matched_base_station_id = matches.bs_id
            FROM (
                SELECT DISTINCT ON (oc_inner.id)
                    oc_inner.id AS oc_id,
                    bs_inner.id AS bs_id
                FROM opencellid_towers oc_inner
                JOIN base_stations bs_inner
                    ON ST_DWithin(bs_inner.geom, oc_inner.geom_point, 0.005)
                ORDER BY oc_inner.id, ST_Distance(bs_inner.geom, oc_inner.geom_point)
            ) AS matches
            WHERE opencellid_towers.id = matches.oc_id
        """)
        matched_count = cur.rowcount
        conn.commit()
        logger.info(f"Matched {matched_count} OpenCelliD towers to base_stations")

        # Spatial join to admin_level_2 for municipality assignment
        logger.info("Assigning municipalities (l2_id) via spatial join...")
        cur.execute("""
            UPDATE opencellid_towers oc
            SET l2_id = al2.id
            FROM admin_level_2 al2
            WHERE al2.geom IS NOT NULL
              AND ST_Within(oc.geom_point, al2.geom)
              AND oc.l2_id IS NULL
        """)
        assigned_count = cur.rowcount
        conn.commit()
        logger.info(f"Assigned {assigned_count} OpenCelliD towers to municipalities")

        self.rows_updated = matched_count + assigned_count
        cur.close()
        conn.close()

    def post_load(self) -> None:
        """Log summary statistics."""
        conn = self._get_connection()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM opencellid_towers")
        total = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM opencellid_towers WHERE matched_base_station_id IS NOT NULL")
        matched = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM opencellid_towers WHERE l2_id IS NOT NULL")
        with_l2 = cur.fetchone()[0]

        cur.execute("""
            SELECT radio, COUNT(*) AS cnt
            FROM opencellid_towers
            GROUP BY radio
            ORDER BY cnt DESC
        """)
        radio_breakdown = cur.fetchall()

        cur.close()
        conn.close()

        logger.info(
            f"OpenCelliD summary: {total} towers, "
            f"{matched} matched to base_stations ({matched/total*100:.1f}% match rate), "
            f"{with_l2} assigned to municipalities"
        )
        for radio, cnt in radio_breakdown:
            logger.info(f"  Radio type {radio}: {cnt} towers")
