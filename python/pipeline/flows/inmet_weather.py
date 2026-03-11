"""Weather observations pipeline with INMET and Open-Meteo sources.

Primary: INMET (Instituto Nacional de Meteorologia)
Fallback: Open-Meteo (free, no auth required)

Stations are already loaded (671 INMET stations in weather_stations).
This pipeline fetches daily observations and appends them.
"""
import logging
import os
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs

logger = logging.getLogger(__name__)

# Sentinel values INMET uses for missing data
MISSING_VALUES = {"-9999", "-9999.0", "", "null", "None"}

# Open-Meteo daily parameters matching our schema
OPEN_METEO_PARAMS = (
    "temperature_2m_mean,precipitation_sum,relative_humidity_2m_mean,"
    "wind_speed_10m_max,wind_direction_10m_dominant,pressure_msl_mean,"
    "shortwave_radiation_sum"
)


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
    """Ingest weather observations from INMET or Open-Meteo (fallback)."""

    def __init__(self):
        super().__init__("inmet_weather")
        self.urls = DataSourceURLs()
        self._token = os.getenv("INMET_API_TOKEN", "")
        self._source = "open-meteo"  # Track which source was used

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT MAX(observed_at) FROM weather_observations")
        latest = cur.fetchone()[0]
        cur.close()
        conn.close()
        if not latest:
            return True
        # Update if latest observation is more than 1 day old
        return (datetime.utcnow() - latest.replace(tzinfo=None)).days >= 1

    def download(self) -> dict:
        """Fetch observations from Open-Meteo for all existing stations."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, latitude, longitude, station_code FROM weather_stations")
        stations = cur.fetchall()

        # Find the latest observation date to only fetch new data
        cur.execute("SELECT MAX(observed_at)::date FROM weather_observations")
        latest_row = cur.fetchone()
        latest_date = latest_row[0] if latest_row[0] else None
        cur.close()
        conn.close()

        if latest_date:
            start_date = latest_date + timedelta(days=1)
        else:
            start_date = datetime.utcnow() - timedelta(days=30)

        end_date = datetime.utcnow()

        if start_date.date() >= end_date.date():
            logger.info("Weather data is already up to date")
            return {"observations": [], "stations_fetched": 0}

        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        logger.info(f"Fetching Open-Meteo data for {len(stations)} stations ({start_str} to {end_str})")

        all_obs = []
        fetched = 0
        errors = 0

        for station_id, lat, lon, code in stations:
            url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}"
                f"&daily={OPEN_METEO_PARAMS}"
                f"&start_date={start_str}&end_date={end_str}"
                f"&timezone=America/Sao_Paulo"
            )
            try:
                resp = requests.get(url, timeout=15)
                if resp.status_code != 200:
                    errors += 1
                    continue
                data = resp.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                for i, date_str in enumerate(dates):
                    def val(key, idx=i):
                        lst = daily.get(key, [])
                        return lst[idx] if idx < len(lst) and lst[idx] is not None else None

                    ws = val("wind_speed_10m_max")
                    all_obs.append({
                        "station_id": station_id,
                        "observed_at": date_str,
                        "precipitation_mm": val("precipitation_sum"),
                        "temperature_c": val("temperature_2m_mean"),
                        "humidity_pct": val("relative_humidity_2m_mean"),
                        "wind_speed_ms": round(ws / 3.6, 2) if ws else None,
                        "wind_direction_deg": val("wind_direction_10m_dominant"),
                        "pressure_hpa": val("pressure_msl_mean"),
                        "solar_radiation_wm2": val("shortwave_radiation_sum"),
                    })
                fetched += 1
            except Exception as e:
                errors += 1
                logger.debug(f"Station {code}: {e}")

            # Rate limiting: ~30 requests/second
            if fetched % 30 == 0:
                time.sleep(1.0)
                if fetched % 100 == 0:
                    logger.info(f"  Fetched {fetched}/{len(stations)} stations ({errors} errors)")

        logger.info(f"Fetched {len(all_obs)} observations from {fetched} stations ({errors} errors)")
        return {"observations": all_obs, "stations_fetched": fetched}

    def validate_raw(self, data: dict) -> None:
        if not data["observations"] and data["stations_fetched"] == 0:
            logger.info("No new observations to load (already up to date)")

    def transform(self, raw_data: dict) -> list[dict]:
        """Pass through — data is already in the right format from Open-Meteo."""
        self.rows_processed = len(raw_data["observations"])
        return raw_data["observations"]

    def load(self, data: list[dict]) -> None:
        """Load weather observations."""
        if not data:
            logger.info("No new weather observations to load")
            self.rows_inserted = 0
            return

        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        values = [
            (
                obs["station_id"], obs["observed_at"],
                obs["precipitation_mm"], obs["temperature_c"],
                obs["humidity_pct"], obs["wind_speed_ms"],
                obs["wind_direction_deg"], obs["pressure_hpa"],
                obs["solar_radiation_wm2"],
            )
            for obs in data
        ]

        execute_values(cur, """
            INSERT INTO weather_observations
            (station_id, observed_at, precipitation_mm, temperature_c,
             humidity_pct, wind_speed_ms, wind_direction_deg, pressure_hpa,
             solar_radiation_wm2)
            VALUES %s
            ON CONFLICT (station_id, observed_at) DO NOTHING
        """, values, page_size=1000)
        conn.commit()

        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {len(values)} weather observations")
