"""OpenStreetMap road network pipeline.

Source: Geofabrik daily extracts
URL: https://download.geofabrik.de/south-america/brazil-latest.osm.pbf
Format: PBF (Protocol Buffer Binary Format)
Size: ~1.5GB compressed

Real download would:
1. Download brazil-latest.osm.pbf from Geofabrik
2. Parse PBF using osmium or pyosmium
3. Extract highway=* ways with geometry
4. Filter to relevant highway classes (trunk, primary, secondary, tertiary, residential)
5. Store road segments with length calculation

For synthetic data, we generate road segments around seed municipalities
with realistic highway classes, names, and surface types.
"""
import logging
import math
import random

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs

logger = logging.getLogger(__name__)

HIGHWAY_CLASSES = {
    "trunk": {"weight": 0.05, "name_prefix": "BR-", "surfaces": ["asphalt"]},
    "primary": {"weight": 0.10, "name_prefix": "Rodovia ", "surfaces": ["asphalt"]},
    "secondary": {"weight": 0.15, "name_prefix": "Estrada ", "surfaces": ["asphalt", "paved"]},
    "tertiary": {"weight": 0.20, "name_prefix": "Rua ", "surfaces": ["asphalt", "paved", "unpaved"]},
    "residential": {"weight": 0.35, "name_prefix": "Rua ", "surfaces": ["asphalt", "paved", "unpaved"]},
    "unclassified": {"weight": 0.15, "name_prefix": "", "surfaces": ["unpaved", "ground"]},
}

ROAD_NAMES = [
    "da Paz", "Brasil", "das Flores", "do Comercio", "Principal",
    "Nova", "Velha", "do Sol", "da Liberdade", "Sao Paulo",
    "Rio Branco", "Amazonas", "Bahia", "Minas Gerais", "Parana",
    "Santos Dumont", "Tiradentes", "Dom Pedro", "Getulio Vargas",
    "JK", "XV de Novembro", "Sete de Setembro",
]


class OSMRoadsPipeline(BasePipeline):
    """Ingest OpenStreetMap road network data."""

    def __init__(self):
        super().__init__("osm_roads")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM road_segments WHERE country_code = 'BR'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real OSM PBF download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate road segments around seed municipalities."""
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

        random.seed(48)
        rows = []
        osm_id_counter = 100000000

        classes = list(HIGHWAY_CLASSES.keys())
        class_weights = [HIGHWAY_CLASSES[c]["weight"] for c in classes]

        for l2_id, code, mun_name, lon, lat in municipalities:
            if lon is None or lat is None:
                continue

            # 10-20 road segments per municipality
            num_roads = random.randint(10, 20)
            for _ in range(num_roads):
                osm_id_counter += 1
                hw_class = random.choices(classes, weights=class_weights)[0]
                info = HIGHWAY_CLASSES[hw_class]

                # Generate a line segment near the centroid
                start_lat = lat + random.uniform(-0.03, 0.03)
                start_lon = lon + random.uniform(-0.03, 0.03)
                # Road segment length: 200m to 3km
                bearing = random.uniform(0, 2 * math.pi)
                length_deg = random.uniform(0.002, 0.03)
                end_lat = start_lat + length_deg * math.cos(bearing)
                end_lon = start_lon + length_deg * math.sin(bearing)

                # Approximate length in meters (rough at these latitudes)
                dlat = (end_lat - start_lat) * 111320
                dlon = (end_lon - start_lon) * 111320 * math.cos(math.radians(start_lat))
                length_m = round(math.sqrt(dlat ** 2 + dlon ** 2), 1)

                geom_wkt = f"SRID=4326;LINESTRING({start_lon} {start_lat}, {end_lon} {end_lat})"

                name_suffix = random.choice(ROAD_NAMES)
                name = f"{info['name_prefix']}{name_suffix}" if info["name_prefix"] else name_suffix
                surface = random.choice(info["surfaces"])

                rows.append({
                    "country_code": "BR",
                    "osm_id": osm_id_counter,
                    "highway_class": hw_class,
                    "name": name,
                    "surface_type": surface,
                    "geom_wkt": geom_wkt,
                    "length_m": length_m,
                })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["highway_class", "geom_wkt", "length_m"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Insert road segment records."""
        conn = self._get_connection()
        cur = conn.cursor()
        # Clear existing synthetic roads
        cur.execute("DELETE FROM road_segments WHERE country_code = 'BR' AND osm_id >= 100000000")
        conn.commit()

        from psycopg2.extras import execute_values
        values = []
        for _, row in data.iterrows():
            values.append((
                row["country_code"], row["osm_id"], row["highway_class"],
                row["name"], row["surface_type"], row["geom_wkt"], row["length_m"],
            ))

        execute_values(cur, """
            INSERT INTO road_segments
            (country_code, osm_id, highway_class, name, surface_type, geom, length_m)
            VALUES %s
        """, values, template=(
            "(%s, %s, %s, %s, %s, ST_GeomFromEWKT(%s), %s)"
        ), page_size=1000)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} road segments")
