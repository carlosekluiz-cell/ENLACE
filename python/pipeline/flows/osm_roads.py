"""OpenStreetMap road network pipeline.

Source: Geofabrik regional shapefiles
URL template: https://download.geofabrik.de/south-america/brazil/{region}-latest-free.shp.zip
Regions: sudeste, sul, nordeste, norte, centro-oeste
Format: Shapefile ZIP containing gis_osm_roads_free_1.shp

Downloads regional shapefiles, extracts road geometries, filters by
municipality bounding boxes using geopandas spatial operations.
"""
import logging
import tempfile
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping

from python.pipeline.base import BasePipeline
from python.pipeline.config import DOWNLOAD_CACHE_DIR, DataSourceURLs, STATE_ABBREVIATIONS
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

# Map state IBGE codes to Geofabrik regions
STATE_TO_REGION = {}
for code in ["35", "33", "31", "32"]:
    STATE_TO_REGION[code] = "sudeste"
for code in ["41", "42", "43"]:
    STATE_TO_REGION[code] = "sul"
for code in ["21", "22", "23", "24", "25", "26", "27", "28", "29"]:
    STATE_TO_REGION[code] = "nordeste"
for code in ["11", "12", "13", "14", "15", "16", "17"]:
    STATE_TO_REGION[code] = "norte"
for code in ["50", "51", "52", "53"]:
    STATE_TO_REGION[code] = "centro-oeste"

HIGHWAY_CLASS_MAP = {
    "trunk": "trunk",
    "trunk_link": "trunk",
    "primary": "primary",
    "primary_link": "primary",
    "secondary": "secondary",
    "secondary_link": "secondary",
    "tertiary": "tertiary",
    "tertiary_link": "tertiary",
    "residential": "residential",
    "unclassified": "unclassified",
    "living_street": "residential",
    "service": "unclassified",
}


class OSMRoadsPipeline(BasePipeline):
    """Ingest real road network from Geofabrik regional shapefiles."""

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
        return count < 1000

    def download(self) -> pd.DataFrame:
        """Download regional shapefiles and extract roads."""
        # Determine which regions we need based on municipalities in DB
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT al1.code as state_code
            FROM admin_level_2 al2
            JOIN admin_level_1 al1 ON al2.l1_id = al1.id
            WHERE al2.country_code = 'BR'
        """)
        state_codes = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

        needed_regions = set()
        for state_code in state_codes:
            region = STATE_TO_REGION.get(state_code)
            if region:
                needed_regions.add(region)

        if not needed_regions:
            needed_regions = {"sudeste", "sul", "nordeste", "norte", "centro-oeste"}

        logger.info(f"Need regions: {needed_regions}")

        all_roads = []
        with PipelineHTTPClient(timeout=600) as http:
            for region in needed_regions:
                url = self.urls.osm_geofabrik_shp.format(region=region)
                cache_path = get_cache_path(f"osm_{region}.shp.zip")

                try:
                    logger.info(f"Downloading {region} shapefile...")
                    http.download_file(url, cache_path)

                    # Extract and read roads shapefile
                    roads_gdf = self._extract_roads(cache_path)
                    if roads_gdf is not None and not roads_gdf.empty:
                        all_roads.append(roads_gdf)
                        logger.info(f"Extracted {len(roads_gdf)} roads from {region}")
                    else:
                        logger.warning(f"No roads extracted from {region}")

                except Exception as e:
                    logger.warning(f"Could not process {region}: {e}")

        if not all_roads:
            raise ValueError("No road data extracted from any region")

        combined = pd.concat(all_roads, ignore_index=True)
        logger.info(f"Total roads extracted: {len(combined)}")
        return combined

    def _extract_roads(self, zip_path: Path) -> gpd.GeoDataFrame | None:
        """Extract road geometries from a Geofabrik shapefile ZIP."""
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    # Find the roads shapefile
                    road_files = [f for f in zf.namelist() if "roads_free_1" in f.lower()]
                    if not road_files:
                        road_files = [f for f in zf.namelist() if "roads" in f.lower() and f.endswith(".shp")]
                    if not road_files:
                        logger.warning(f"No roads shapefile found in {zip_path}")
                        return None

                    zf.extractall(tmpdir)

                    shp_file = None
                    for f in road_files:
                        if f.endswith(".shp"):
                            shp_file = Path(tmpdir) / f
                            break

                    if shp_file is None or not shp_file.exists():
                        return None

                    gdf = gpd.read_file(shp_file)

                    # Filter to relevant highway classes
                    if "fclass" in gdf.columns:
                        gdf = gdf[gdf["fclass"].isin(HIGHWAY_CLASS_MAP.keys())]
                        gdf["highway_class"] = gdf["fclass"].map(HIGHWAY_CLASS_MAP)
                    elif "highway" in gdf.columns:
                        gdf = gdf[gdf["highway"].isin(HIGHWAY_CLASS_MAP.keys())]
                        gdf["highway_class"] = gdf["highway"].map(HIGHWAY_CLASS_MAP)
                    else:
                        gdf["highway_class"] = "unclassified"

                    return gdf

        except Exception as e:
            logger.warning(f"Error extracting roads from {zip_path}: {e}")
            return None

    def validate_raw(self, data) -> None:
        if data.empty:
            raise ValueError("Empty road dataset")

    def transform(self, raw_data) -> pd.DataFrame:
        """Convert geopandas GeoDataFrame to load-ready DataFrame."""
        gdf = raw_data
        rows = []

        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            # Get OSM ID
            osm_id = row.get("osm_id", row.get("OSM_ID", 0))
            try:
                osm_id = int(osm_id)
            except (ValueError, TypeError):
                osm_id = 0

            # Compute length in meters
            try:
                length_m = geom.length * 111320  # Rough degrees to meters
            except Exception:
                length_m = 0

            # Convert geometry to EWKT
            if geom.geom_type == "LineString":
                coords = list(geom.coords)
                coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
                geom_wkt = f"SRID=4326;LINESTRING({coord_str})"
            elif geom.geom_type == "MultiLineString":
                first_line = list(geom.geoms)[0]
                coords = list(first_line.coords)
                coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
                geom_wkt = f"SRID=4326;LINESTRING({coord_str})"
            else:
                continue

            name = str(row.get("name", row.get("NAME", "")))
            if name in ("None", "nan", ""):
                name = ""

            surface = str(row.get("surface", row.get("SURFACE", "")))
            if surface in ("None", "nan", ""):
                surface = "unknown"

            rows.append({
                "country_code": "BR",
                "osm_id": osm_id,
                "highway_class": row.get("highway_class", "unclassified"),
                "name": name,
                "surface_type": surface,
                "geom_wkt": geom_wkt,
                "length_m": round(length_m, 1),
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows)} road segments")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Insert road segment records."""
        if data.empty:
            logger.warning("No road segments to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM road_segments WHERE country_code = 'BR'")
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
