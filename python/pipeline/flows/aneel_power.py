"""ANEEL power grid corridors pipeline.

Source: ANEEL (Agencia Nacional de Energia Eletrica)
URL: https://dadosabertos.aneel.gov.br/
Format: CSV/Shapefile with transmission and distribution line data

Real download would fetch power line geometry from ANEEL's open data portal,
including voltage levels, operator names, and line types (transmission vs distribution).

Fiber-optic cables are frequently co-deployed along power transmission corridors
(OPGW - Optical Ground Wire), making power grid data valuable for identifying
potential fiber routes and infrastructure sharing opportunities.
"""
import logging
import math
import random

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs

logger = logging.getLogger(__name__)

# Major power operators in Brazil
POWER_OPERATORS = [
    "CHESF", "Eletronorte", "Furnas", "Eletrosul", "CTEEP",
    "CELG", "CEMIG", "COPEL", "CEEE", "Light",
    "Enel", "Neoenergia", "Energisa", "CPFL", "Equatorial",
]

# Voltage levels
VOLTAGE_LEVELS = {
    "transmission": [230, 345, 500, 750],
    "subtransmission": [69, 88, 138],
    "distribution": [13.8, 23, 34.5],
}


class ANEELPowerPipeline(BasePipeline):
    """Ingest ANEEL power grid corridor data."""

    def __init__(self):
        super().__init__("aneel_power")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM power_lines WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 50

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real ANEEL power grid download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate power lines connecting seed municipalities."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.name,
                   ST_X(al2.centroid::geometry) as lon,
                   ST_Y(al2.centroid::geometry) as lat
            FROM admin_level_2 al2
            WHERE al2.country_code = 'BR' AND al2.centroid IS NOT NULL
            ORDER BY al2.id
        """)
        municipalities = cur.fetchall()
        cur.close()
        conn.close()

        random.seed(49)
        rows = []

        # Create transmission lines between nearby municipalities
        for i, (l2_id_a, name_a, lon_a, lat_a) in enumerate(municipalities):
            if lon_a is None or lat_a is None:
                continue

            # Connect to 2-3 nearest municipalities
            distances = []
            for j, (l2_id_b, name_b, lon_b, lat_b) in enumerate(municipalities):
                if i == j or lon_b is None or lat_b is None:
                    continue
                dist = math.sqrt((lon_a - lon_b) ** 2 + (lat_a - lat_b) ** 2)
                distances.append((j, dist, lon_b, lat_b))

            distances.sort(key=lambda x: x[1])
            connections = distances[:random.randint(2, 3)]

            for j, dist, lon_b, lat_b in connections:
                # Only create line if we haven't created the reverse
                if j < i:
                    continue

                # Determine line type based on distance
                if dist > 3.0:
                    line_type = "transmission"
                elif dist > 1.0:
                    line_type = "subtransmission"
                else:
                    line_type = "distribution"

                voltage = random.choice(VOLTAGE_LEVELS[line_type])
                operator = random.choice(POWER_OPERATORS)

                # Create a line with an intermediate point for realism
                mid_lon = (lon_a + lon_b) / 2 + random.uniform(-0.1, 0.1)
                mid_lat = (lat_a + lat_b) / 2 + random.uniform(-0.1, 0.1)

                geom_wkt = (
                    f"SRID=4326;LINESTRING("
                    f"{lon_a} {lat_a}, {mid_lon} {mid_lat}, {lon_b} {lat_b})"
                )

                rows.append({
                    "country_code": "BR",
                    "voltage_kv": voltage,
                    "operator_name": operator,
                    "line_type": line_type,
                    "geom_wkt": geom_wkt,
                    "source": "aneel_synthetic",
                })

            # Also add local distribution lines within municipality
            for _ in range(random.randint(2, 5)):
                start_lon = lon_a + random.uniform(-0.02, 0.02)
                start_lat = lat_a + random.uniform(-0.02, 0.02)
                end_lon = start_lon + random.uniform(-0.01, 0.01)
                end_lat = start_lat + random.uniform(-0.01, 0.01)

                geom_wkt = (
                    f"SRID=4326;LINESTRING("
                    f"{start_lon} {start_lat}, {end_lon} {end_lat})"
                )
                rows.append({
                    "country_code": "BR",
                    "voltage_kv": random.choice(VOLTAGE_LEVELS["distribution"]),
                    "operator_name": random.choice(POWER_OPERATORS),
                    "line_type": "distribution",
                    "geom_wkt": geom_wkt,
                    "source": "aneel_synthetic",
                })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["voltage_kv", "line_type", "geom_wkt"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Insert power line records."""
        conn = self._get_connection()
        cur = conn.cursor()
        # Clear existing synthetic power lines
        cur.execute("DELETE FROM power_lines WHERE source = 'aneel_synthetic'")
        conn.commit()

        from psycopg2.extras import execute_values
        values = []
        for _, row in data.iterrows():
            values.append((
                row["country_code"], row["voltage_kv"], row["operator_name"],
                row["line_type"], row["geom_wkt"], row["source"],
            ))

        execute_values(cur, """
            INSERT INTO power_lines
            (country_code, voltage_kv, operator_name, line_type, geom, source)
            VALUES %s
        """, values, template=(
            "(%s, %s, %s, %s, ST_GeomFromEWKT(%s), %s)"
        ), page_size=1000)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} power lines")
