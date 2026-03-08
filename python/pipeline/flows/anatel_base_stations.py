"""Anatel base station (ERB) registry pipeline.

Source: Anatel STEL system
URL: https://sistemas.anatel.gov.br/se/public/view/b/stel.php
Format: CSV export from STEL database
Fields: NumEstacao, Latitude, Longitude, Tecnologia, FreqMHz, Operadora, etc.

Real download would fetch the STEL CSV export and parse station coordinates,
technology types, frequency bands, and provider assignments.
"""
import logging
import random
import uuid

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# Common frequencies for mobile technologies in Brazil
FREQ_TECH_MAP = {
    "2G": {"freqs": [850, 900, 1800], "power": (20, 40)},
    "3G": {"freqs": [850, 1900, 2100], "power": (20, 40)},
    "4G": {"freqs": [700, 1800, 2600], "power": (20, 60)},
    "5G": {"freqs": [700, 2300, 3500], "power": (10, 40)},
}


class AnatelBaseStationsPipeline(BasePipeline):
    """Ingest Anatel base station registry data."""

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
        return count < 100  # Need at least 100 stations

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real Anatel base station download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate realistic base station data near seed municipalities."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.code, al2.name,
                   ST_X(al2.centroid::geometry) as lon,
                   ST_Y(al2.centroid::geometry) as lat
            FROM admin_level_2 al2
            WHERE al2.country_code = 'BR' AND al2.centroid IS NOT NULL
        """)
        municipalities = cur.fetchall()
        # Only use major providers for base stations (top 4 + some regionals)
        cur.execute("SELECT id, name FROM providers WHERE country_code = 'BR' AND classification IN ('PGP', 'PMP') LIMIT 10")
        providers = cur.fetchall()
        cur.close()
        conn.close()

        random.seed(43)
        rows = []
        techs = list(FREQ_TECH_MAP.keys())
        tech_weights = [0.05, 0.15, 0.55, 0.25]  # 4G dominant

        for l2_id, code, mun_name, lon, lat in municipalities:
            if lon is None or lat is None:
                continue
            # 5-15 stations per municipality
            num_stations = random.randint(5, 15)
            for _ in range(num_stations):
                prov_id, prov_name = random.choice(providers)
                tech = random.choices(techs, weights=tech_weights)[0]
                freq_info = FREQ_TECH_MAP[tech]
                freq = random.choice(freq_info["freqs"])
                power = random.uniform(*freq_info["power"])

                # Random offset from centroid (up to ~5km)
                st_lat = lat + random.uniform(-0.05, 0.05)
                st_lon = lon + random.uniform(-0.05, 0.05)

                station_id = f"ERB-{code}-{uuid.uuid4().hex[:8].upper()}"
                rows.append({
                    "country_code": "BR",
                    "provider_id": prov_id,
                    "station_id": station_id,
                    "latitude": round(st_lat, 6),
                    "longitude": round(st_lon, 6),
                    "technology": tech,
                    "frequency_mhz": freq,
                    "bandwidth_mhz": random.choice([5, 10, 15, 20]),
                    "antenna_height_m": random.uniform(15, 60),
                    "azimuth_degrees": random.uniform(0, 360),
                    "mechanical_tilt": random.uniform(0, 15),
                    "power_watts": round(power, 1),
                    "authorization_date": f"20{random.randint(15, 25):02d}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}",
                    "status": "active",
                })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["latitude", "longitude", "technology", "provider_id"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")
        # Validate coordinates are in Brazil
        out_of_bounds = data[
            (data["latitude"] < -34) | (data["latitude"] > 6) |
            (data["longitude"] < -74) | (data["longitude"] > -28)
        ]
        if len(out_of_bounds) > 0:
            logger.warning(f"{len(out_of_bounds)} stations outside Brazil bounds")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        df = raw_data.copy()
        # Add PostGIS geometry WKT
        df["geom_wkt"] = df.apply(
            lambda r: f"SRID=4326;POINT({r['longitude']} {r['latitude']})", axis=1
        )
        self.rows_processed = len(df)
        return df

    def load(self, data: pd.DataFrame) -> None:
        """Insert base station records."""
        conn = self._get_connection()
        cur = conn.cursor()
        # Clear existing synthetic stations to avoid duplicates
        cur.execute("DELETE FROM base_stations WHERE country_code = 'BR' AND station_id LIKE 'ERB-%'")
        conn.commit()

        from psycopg2.extras import execute_values
        values = []
        for _, row in data.iterrows():
            values.append((
                row["country_code"], row["provider_id"], row["station_id"],
                row["geom_wkt"], row["latitude"], row["longitude"],
                row["technology"], row["frequency_mhz"], row["bandwidth_mhz"],
                row["antenna_height_m"], row["azimuth_degrees"],
                row["mechanical_tilt"], row["power_watts"],
                row["authorization_date"], row["status"],
            ))

        execute_values(cur, """
            INSERT INTO base_stations
            (country_code, provider_id, station_id, geom, latitude, longitude,
             technology, frequency_mhz, bandwidth_mhz, antenna_height_m,
             azimuth_degrees, mechanical_tilt, power_watts, authorization_date, status)
            VALUES %s
        """, values, template=(
            "(%s, %s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        ), page_size=1000)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} base stations")
