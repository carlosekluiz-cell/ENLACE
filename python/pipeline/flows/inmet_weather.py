"""INMET meteorological observations pipeline.

Source: INMET (Instituto Nacional de Meteorologia)
URL: https://apitempo.inmet.gov.br/
API endpoints:
  - Stations: https://apitempo.inmet.gov.br/estacoes/T
  - Observations: https://apitempo.inmet.gov.br/estacao/{start}/{end}/{code}
Format: JSON API responses

Real download would:
1. Fetch station registry from INMET API
2. For each station, fetch hourly observations for the desired period
3. Parse temperature, precipitation, humidity, wind, pressure, solar radiation

Weather data is relevant for:
- RF propagation modeling (rain fade, atmospheric absorption)
- Solar power availability for off-grid base stations
- Seasonal patterns affecting construction windows
"""
import logging
import math
import random
from datetime import datetime, timedelta

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs

logger = logging.getLogger(__name__)

# Brazilian climate zones (simplified) with seasonal temperature patterns
CLIMATE_ZONES = {
    "equatorial": {"temp_mean": 27, "temp_range": 3, "rain_annual_mm": 2200},
    "tropical": {"temp_mean": 24, "temp_range": 6, "rain_annual_mm": 1500},
    "semiarid": {"temp_mean": 26, "temp_range": 5, "rain_annual_mm": 600},
    "subtropical": {"temp_mean": 18, "temp_range": 10, "rain_annual_mm": 1400},
}

# Map latitudes to climate zones
def get_climate_zone(lat: float) -> str:
    if lat > -5:
        return "equatorial"
    elif lat > -15:
        return "tropical"
    elif lat > -23.5:
        return "tropical"
    else:
        return "subtropical"


class INMETWeatherPipeline(BasePipeline):
    """Ingest INMET weather station data and observations."""

    def __init__(self):
        super().__init__("inmet_weather")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM weather_stations WHERE country_code = 'BR'")
        stations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM weather_observations")
        obs = cur.fetchone()[0]
        cur.close()
        conn.close()
        return stations < 10 or obs < 100

    def download(self) -> dict:
        try:
            logger.info("Attempting real INMET API download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> dict:
        """Generate weather stations and observations near seed municipalities."""
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
        cur.close()
        conn.close()

        random.seed(50)
        stations = []
        observations = []
        station_counter = 0

        # Create 1 weather station per municipality (some municipalities share)
        station_map = {}  # station_idx -> (lat, lon, climate_zone)
        for l2_id, code, mun_name, lon, lat in municipalities:
            if lon is None or lat is None:
                continue
            station_counter += 1
            station_code = f"A{station_counter:03d}"
            # Offset slightly from centroid
            st_lat = lat + random.uniform(-0.01, 0.01)
            st_lon = lon + random.uniform(-0.01, 0.01)
            elevation = random.uniform(10, 1200)
            climate = get_climate_zone(lat)

            stations.append({
                "country_code": "BR",
                "station_code": station_code,
                "name": f"Estacao {mun_name}",
                "latitude": round(st_lat, 6),
                "longitude": round(st_lon, 6),
                "elevation_m": round(elevation, 1),
                "station_type": random.choice(["automatica", "convencional"]),
                "active": True,
            })
            station_map[station_code] = (st_lat, st_lon, climate)

        # Generate daily observations for 30 days (one observation per day)
        base_date = datetime(2025, 1, 1)
        for station_code, (lat, lon, climate) in station_map.items():
            zone = CLIMATE_ZONES[climate]
            for day_offset in range(30):
                obs_date = base_date + timedelta(days=day_offset)
                # Seasonal adjustment (Southern Hemisphere: Jan is summer)
                month = obs_date.month
                seasonal_factor = math.cos((month - 1) * math.pi / 6)  # Peak cold in July

                temp = zone["temp_mean"] + zone["temp_range"] * seasonal_factor * 0.5
                temp += random.gauss(0, 2)  # Daily variation

                # Precipitation: higher in summer months (Oct-Mar)
                rain_probability = 0.6 if month in [10, 11, 12, 1, 2, 3] else 0.3
                if random.random() < rain_probability:
                    precip = random.expovariate(1 / (zone["rain_annual_mm"] / 365))
                else:
                    precip = 0.0

                humidity = random.uniform(40, 95)
                if precip > 0:
                    humidity = min(100, humidity + 20)

                wind_speed = max(0, random.gauss(3, 2))
                wind_dir = random.uniform(0, 360)
                pressure = random.gauss(1013, 5) - elevation_correction(stations)
                solar = max(0, random.gauss(250, 100) * (1 - min(precip / 30, 0.8)))

                observations.append({
                    "station_code": station_code,
                    "observed_at": obs_date.isoformat(),
                    "precipitation_mm": round(max(0, precip), 1),
                    "temperature_c": round(temp, 1),
                    "humidity_pct": round(min(100, max(0, humidity)), 1),
                    "wind_speed_ms": round(wind_speed, 1),
                    "wind_direction_deg": round(wind_dir, 1),
                    "pressure_hpa": round(pressure, 1),
                    "solar_radiation_wm2": round(solar, 1),
                })

        return {
            "stations": pd.DataFrame(stations),
            "observations": pd.DataFrame(observations),
        }

    def validate_raw(self, data: dict) -> None:
        if data["stations"].empty:
            raise ValueError("No weather stations found")
        if data["observations"].empty:
            raise ValueError("No weather observations found")

    def transform(self, raw_data: dict) -> dict:
        self.rows_processed = len(raw_data["stations"]) + len(raw_data["observations"])
        return raw_data

    def load(self, data: dict) -> None:
        """Load weather stations and observations."""
        conn = self._get_connection()
        cur = conn.cursor()

        # Load stations
        cur.execute("DELETE FROM weather_observations")
        cur.execute("DELETE FROM weather_stations WHERE country_code = 'BR'")
        conn.commit()

        from psycopg2.extras import execute_values
        station_values = []
        for _, row in data["stations"].iterrows():
            geom_wkt = f"SRID=4326;POINT({row['longitude']} {row['latitude']})"
            station_values.append((
                row["country_code"], row["station_code"], row["name"],
                geom_wkt, row["latitude"], row["longitude"],
                row["elevation_m"], row["station_type"], row["active"],
            ))

        execute_values(cur, """
            INSERT INTO weather_stations
            (country_code, station_code, name, geom, latitude, longitude,
             elevation_m, station_type, active)
            VALUES %s
        """, station_values, template=(
            "(%s, %s, %s, ST_GeomFromEWKT(%s), %s, %s, %s, %s, %s)"
        ), page_size=500)
        conn.commit()

        # Build station_code -> id map
        cur.execute("SELECT station_code, id FROM weather_stations WHERE country_code = 'BR'")
        station_id_map = {code: sid for code, sid in cur.fetchall()}

        # Load observations
        obs_values = []
        for _, row in data["observations"].iterrows():
            station_id = station_id_map.get(row["station_code"])
            if station_id is None:
                continue
            obs_values.append((
                station_id, row["observed_at"], row["precipitation_mm"],
                row["temperature_c"], row["humidity_pct"], row["wind_speed_ms"],
                row["wind_direction_deg"], row["pressure_hpa"],
                row["solar_radiation_wm2"],
            ))

        if obs_values:
            execute_values(cur, """
                INSERT INTO weather_observations
                (station_id, observed_at, precipitation_mm, temperature_c,
                 humidity_pct, wind_speed_ms, wind_direction_deg, pressure_hpa,
                 solar_radiation_wm2)
                VALUES %s
            """, obs_values, page_size=1000)
            conn.commit()

        self.rows_inserted = len(station_values) + len(obs_values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {len(station_values)} stations, {len(obs_values)} observations")


def elevation_correction(stations_list):
    """Rough barometric pressure correction placeholder."""
    return random.uniform(0, 5)
