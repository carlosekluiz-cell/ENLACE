"""Anatel base station (ERB) registry pipeline.

Source: Anatel open data on dados.gov.br (CKAN)
Dataset: "licenciamento"
Format: CSV (semicolon-delimited, ISO-8859-1)
Fields: NumEstacao, Latitude, Longitude, Tecnologia, FreqMHz, Operadora, etc.

Downloads the full licensing CSV, parses DMS coordinates to decimal,
maps technology codes, and loads station locations.
"""
import logging
import re

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# Map Anatel technology codes to standard labels
ANATEL_TECH_MAP = {
    "LTE": "4G",
    "4G": "4G",
    "NR": "5G",
    "5G": "5G",
    "WCDMA": "3G",
    "UMTS": "3G",
    "3G": "3G",
    "GSM": "2G",
    "CDMA": "2G",
    "2G": "2G",
}


def dms_to_decimal(dms_str: str) -> float | None:
    """Convert Anatel DMS coordinate string to decimal degrees.

    Handles formats like:
      - 23°32'15"S or 23°32'15.5"S
      - -23.5375 (already decimal)
      - 23 32 15 S
    """
    if not dms_str or str(dms_str).strip() in ("", "nan", "None"):
        return None

    dms_str = str(dms_str).strip()

    # Already decimal
    try:
        val = float(dms_str)
        return val
    except ValueError:
        pass

    # DMS pattern: degrees°minutes'seconds"direction
    pattern = r"(\d+)[°º]\s*(\d+)['\u2019]\s*([\d.]+)[\"″]?\s*([NSEW]?)"
    match = re.match(pattern, dms_str, re.IGNORECASE)
    if match:
        degrees = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        direction = match.group(4).upper()

        decimal = degrees + minutes / 60 + seconds / 3600
        if direction in ("S", "W"):
            decimal = -decimal
        return decimal

    # Space-separated: "23 32 15 S"
    parts = dms_str.split()
    if len(parts) >= 3:
        try:
            degrees = int(parts[0])
            minutes = int(parts[1])
            seconds = float(parts[2])
            direction = parts[3].upper() if len(parts) > 3 else ""
            decimal = degrees + minutes / 60 + seconds / 3600
            if direction in ("S", "W"):
                decimal = -decimal
            return decimal
        except (ValueError, IndexError):
            pass

    return None


class AnatelBaseStationsPipeline(BasePipeline):
    """Ingest real Anatel base station registry from CKAN."""

    def __init__(self):
        super().__init__("anatel_base_stations")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM base_stations WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 1000

    def download(self) -> pd.DataFrame:
        """Download base station CSV from dados.gov.br CKAN."""
        with PipelineHTTPClient(timeout=600) as http:
            logger.info("Resolving Anatel base stations CKAN resource URL...")
            csv_url = http.resolve_ckan_resource_url(
                self.urls.anatel_base_stations_dataset,
                resource_format="CSV",
                ckan_base=self.urls.anatel_ckan_base,
            )
            logger.info(f"Downloading base stations CSV from {csv_url}")
            df = http.get_csv(csv_url, sep=";", encoding="iso-8859-1")
            logger.info(f"Downloaded {len(df)} base station records")

        return df

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("Empty base stations CSV")
        logger.info(f"Base stations CSV columns: {list(data.columns)}")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """Parse coordinates, map technology, filter to Brazil bounds."""
        df = raw_data.copy()
        df.columns = [c.strip() for c in df.columns]

        # Find column names
        col_map = {}
        for c in df.columns:
            cl = c.lower()
            if "latitude" in cl or cl == "lat":
                col_map["lat"] = c
            elif "longitude" in cl or cl == "lon":
                col_map["lon"] = c
            elif "estacao" in cl or "estação" in cl or "numesta" in cl:
                col_map["station_id"] = c
            elif "tecnologia" in cl or "tech" in cl:
                col_map["tech"] = c
            elif "freq" in cl:
                col_map.setdefault("freq", c)
            elif "cnpj" in cl or "operadora" in cl:
                col_map.setdefault("operator", c)

        # Build provider lookup
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT national_id, id FROM providers WHERE country_code = 'BR'")
        cnpj_to_provider = {nid: pid for nid, pid in cur.fetchall()}
        # Fallback: get a default provider
        cur.execute("SELECT id FROM providers WHERE country_code = 'BR' LIMIT 1")
        default_provider = cur.fetchone()
        default_provider_id = default_provider[0] if default_provider else None
        cur.close()
        conn.close()

        rows = []
        for _, row in df.iterrows():
            # Parse coordinates
            lat = dms_to_decimal(str(row.get(col_map.get("lat", ""), "")))
            lon = dms_to_decimal(str(row.get(col_map.get("lon", ""), "")))

            if lat is None or lon is None:
                continue

            # Validate Brazil bounds
            if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -28.0):
                continue

            station_id = str(row.get(col_map.get("station_id", ""), "")).strip()
            if not station_id or station_id == "nan":
                continue

            # Map technology
            tech_raw = str(row.get(col_map.get("tech", ""), "")).strip().upper()
            technology = ANATEL_TECH_MAP.get(tech_raw, "4G")

            # Map frequency
            freq_raw = str(row.get(col_map.get("freq", ""), "")).strip()
            try:
                frequency_mhz = int(float(freq_raw))
            except (ValueError, TypeError):
                frequency_mhz = 0

            # Map operator to provider
            operator = str(row.get(col_map.get("operator", ""), "")).strip()
            provider_id = cnpj_to_provider.get(operator, default_provider_id)
            if provider_id is None:
                continue

            rows.append({
                "country_code": "BR",
                "provider_id": provider_id,
                "station_id": station_id,
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "technology": technology,
                "frequency_mhz": frequency_mhz,
                "status": "active",
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} base stations within Brazil bounds")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Upsert base station records."""
        if data.empty:
            logger.warning("No base stations to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        values = []
        for _, row in data.iterrows():
            geom_wkt = f"SRID=4326;POINT({row['longitude']} {row['latitude']})"
            values.append((
                row["country_code"], row["provider_id"], row["station_id"],
                geom_wkt, row["latitude"], row["longitude"],
                row["technology"], row["frequency_mhz"], row["status"],
            ))

        # Upsert by station_id
        execute_values(cur, """
            INSERT INTO base_stations
            (country_code, provider_id, station_id, geom, latitude, longitude,
             technology, frequency_mhz, status)
            VALUES %s
            ON CONFLICT (station_id) DO UPDATE
            SET provider_id = EXCLUDED.provider_id,
                geom = EXCLUDED.geom,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                technology = EXCLUDED.technology,
                frequency_mhz = EXCLUDED.frequency_mhz,
                status = EXCLUDED.status
        """, values, template=(
            "(%s, %s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s)"
        ), page_size=1000)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} base stations")
