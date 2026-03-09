"""INMET meteorological observations pipeline.

Source: INMET (Instituto Nacional de Meteorologia)
Endpoints:
  - Stations: GET https://apitempo.inmet.gov.br/estacoes/T
  - Observations: GET https://apitempo.inmet.gov.br/estacao/{start}/{end}/{code}
    (max 6-month window per request)
Format: JSON API

Maps INMET fields: CD_ESTACAO->station_code, VL_LATITUDE->lat,
TEM_INS->temperature_c, CHUVA->precipitation_mm, etc.
INMET uses -9999 or empty strings for missing values.
"""
import logging
import os
from datetime import datetime, timedelta

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.http_client import PipelineHTTPClient

logger = logging.getLogger(__name__)

# INMET field mapping to our schema
INMET_FIELD_MAP = {
    "TEM_INS": "temperature_c",
    "CHUVA": "precipitation_mm",
    "UMD_INS": "humidity_pct",
    "VEN_VEL": "wind_speed_ms",
    "VEN_DIR": "wind_direction_deg",
    "PRE_INS": "pressure_hpa",
    "RAD_GLO": "solar_radiation_wm2",
}

# Sentinel values INMET uses for missing data
MISSING_VALUES = {"-9999", "-9999.0", "", "null", "None"}


def parse_inmet_value(val) -> float | None:
    """Parse INMET numeric value, returning None for missing/sentinel."""
    if val is None:
        return None
    s = str(val).strip()
    if s in MISSING_VALUES:
        return None
    try:
        v = float(s.replace(",", "."))
        if v <= -9999:
            return None
        return v
    except (ValueError, TypeError):
        return None


class INMETWeatherPipeline(BasePipeline):
    """Ingest real INMET weather station data and observations."""

    def __init__(self):
        super().__init__("inmet_weather")
        self.urls = DataSourceURLs()
        self._token = os.getenv("INMET_API_TOKEN", "")

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM weather_stations WHERE country_code = 'BR'")
        stations = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM weather_observations")
        obs = cur.fetchone()[0]
        cur.close()
        conn.close()
        return stations < 100 or obs < 1000

    def download(self) -> dict:
        """Download station registry and recent observations from INMET API."""
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        with PipelineHTTPClient(timeout=120) as http:
            if self._token:
                http._client.headers.update(headers)

            # Fetch all stations
            logger.info("Fetching INMET station registry...")
            stations = http.get_json(self.urls.inmet_stations)
            logger.info(f"Got {len(stations)} weather stations")

            # Fetch recent observations for each station (last 30 days)
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=30)
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            all_observations = []
            station_count = 0
            for station in stations:
                code = station.get("CD_ESTACAO", station.get("cd_estacao", ""))
                if not code:
                    continue

                try:
                    url = f"{self.urls.inmet_observations}/{start_str}/{end_str}/{code}"
                    obs = http.get_json(url)
                    if isinstance(obs, list):
                        for o in obs:
                            o["_station_code"] = code
                        all_observations.extend(obs)
                    station_count += 1

                    if station_count % 50 == 0:
                        logger.info(f"Fetched observations for {station_count} stations...")
                except Exception as e:
                    logger.debug(f"Could not fetch observations for station {code}: {e}")
                    continue

            logger.info(
                f"Fetched {len(all_observations)} observations "
                f"from {station_count} stations"
            )

        return {
            "stations": stations,
            "observations": all_observations,
        }

    def validate_raw(self, data: dict) -> None:
        if not data["stations"]:
            raise ValueError("No weather stations returned from INMET API")
        logger.info(
            f"Raw: {len(data['stations'])} stations, "
            f"{len(data['observations'])} observations"
        )

    def transform(self, raw_data: dict) -> dict:
        """Transform INMET API responses into database-ready format."""
        # Transform stations
        station_rows = []
        for s in raw_data["stations"]:
            code = s.get("CD_ESTACAO", s.get("cd_estacao", ""))
            if not code:
                continue

            lat = parse_inmet_value(s.get("VL_LATITUDE", s.get("vl_latitude")))
            lon = parse_inmet_value(s.get("VL_LONGITUDE", s.get("vl_longitude")))
            if lat is None or lon is None:
                continue

            # Validate Brazil bounds
            if not (-34.0 <= lat <= 6.0 and -74.0 <= lon <= -28.0):
                continue

            elevation = parse_inmet_value(s.get("VL_ALTITUDE", s.get("vl_altitude")))
            name = s.get("DC_NOME", s.get("dc_nome", f"Station {code}"))
            station_type = s.get("TP_ESTACAO", s.get("tp_estacao", "automatica"))

            station_rows.append({
                "country_code": "BR",
                "station_code": str(code),
                "name": str(name),
                "latitude": round(lat, 6),
                "longitude": round(lon, 6),
                "elevation_m": round(elevation, 1) if elevation else 0,
                "station_type": str(station_type).lower() if station_type else "automatica",
                "active": True,
            })

        # Transform observations
        obs_rows = []
        for o in raw_data["observations"]:
            station_code = o.get("_station_code", "")
            dt_str = o.get("DT_MEDICAO", o.get("dt_medicao", ""))
            hr_str = o.get("HR_MEDICAO", o.get("hr_medicao", "0000"))

            if not station_code or not dt_str:
                continue

            try:
                observed_at = f"{dt_str}T{hr_str[:2]}:{hr_str[2:4] if len(hr_str) >= 4 else '00'}:00"
            except (IndexError, TypeError):
                observed_at = f"{dt_str}T00:00:00"

            obs_rows.append({
                "station_code": station_code,
                "observed_at": observed_at,
                "temperature_c": parse_inmet_value(o.get("TEM_INS")),
                "precipitation_mm": parse_inmet_value(o.get("CHUVA")),
                "humidity_pct": parse_inmet_value(o.get("UMD_INS")),
                "wind_speed_ms": parse_inmet_value(o.get("VEN_VEL")),
                "wind_direction_deg": parse_inmet_value(o.get("VEN_DIR")),
                "pressure_hpa": parse_inmet_value(o.get("PRE_INS")),
                "solar_radiation_wm2": parse_inmet_value(o.get("RAD_GLO")),
            })

        self.rows_processed = len(station_rows) + len(obs_rows)
        return {
            "stations": pd.DataFrame(station_rows),
            "observations": pd.DataFrame(obs_rows),
        }

    def load(self, data: dict) -> None:
        """Load weather stations and observations."""
        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        # Load stations
        stations_df = data["stations"]
        if not stations_df.empty:
            cur.execute("DELETE FROM weather_observations")
            cur.execute("DELETE FROM weather_stations WHERE country_code = 'BR'")
            conn.commit()

            station_values = []
            for _, row in stations_df.iterrows():
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
        obs_df = data["observations"]
        obs_values = []
        if not obs_df.empty:
            for _, row in obs_df.iterrows():
                station_id = station_id_map.get(row["station_code"])
                if station_id is None:
                    continue
                obs_values.append((
                    station_id, row["observed_at"],
                    row.get("precipitation_mm"), row.get("temperature_c"),
                    row.get("humidity_pct"), row.get("wind_speed_ms"),
                    row.get("wind_direction_deg"), row.get("pressure_hpa"),
                    row.get("solar_radiation_wm2"),
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

        stations_loaded = len(stations_df) if not stations_df.empty else 0
        self.rows_inserted = stations_loaded + len(obs_values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {stations_loaded} stations, {len(obs_values)} observations")
