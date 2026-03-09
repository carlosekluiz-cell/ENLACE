"""MapBiomas land use/cover classification pipeline.

Source: MapBiomas Collection 9, Google Cloud Storage (no auth)
URL: https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/
     collection_9/lclu/coverage/brasil_coverage_2023.tif
Format: GeoTIFF (~2GB)
Resolution: 30m pixels

Uses rasterio windowed reading to sample land cover at H3 cell centers
for each municipality's bounding box. Maps MapBiomas integer class codes
to cover type strings.
"""
import logging
from pathlib import Path

import h3
import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DOWNLOAD_CACHE_DIR, DataSourceURLs, STATE_ABBREVIATIONS
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# MapBiomas Collection 9 class codes -> cover type strings
MAPBIOMAS_CLASSES = {
    1: "forest",
    3: "forest",
    4: "savanna",
    5: "savanna",
    6: "forest",        # flooded forest
    9: "forest",        # forest plantation
    10: "other_vegetation",
    11: "wetland",
    12: "grassland",
    13: "other_vegetation",
    14: "agriculture",
    15: "pasture",
    18: "agriculture",
    19: "agriculture",   # temp crop
    20: "agriculture",   # sugar cane
    21: "agriculture",   # mosaic
    22: "bare_soil",
    23: "bare_soil",
    24: "urban",
    25: "bare_soil",
    26: "water",
    27: "bare_soil",
    29: "agriculture",   # soybean
    30: "agriculture",
    31: "water",
    32: "bare_soil",     # salt flat
    33: "water",
    36: "agriculture",   # perennial crop
    39: "agriculture",   # soybean
    40: "agriculture",   # rice
    41: "agriculture",   # other temp
    46: "agriculture",   # coffee
    47: "agriculture",   # citrus
    48: "agriculture",   # other perennial
    49: "forest",        # wooded sandbank
    50: "other_vegetation",
    62: "agriculture",   # cotton
}

# State -> biome mapping (simplified)
STATE_BIOME = {
    "AM": "Amazonia", "PA": "Amazonia", "RO": "Amazonia", "RR": "Amazonia",
    "AC": "Amazonia", "AP": "Amazonia", "TO": "Cerrado",
    "MA": "Amazonia", "PI": "Caatinga", "CE": "Caatinga", "RN": "Caatinga",
    "PB": "Caatinga", "PE": "Caatinga", "AL": "Caatinga", "SE": "Caatinga",
    "BA": "Caatinga", "MG": "Cerrado", "ES": "Mata Atlantica",
    "RJ": "Mata Atlantica", "SP": "Mata Atlantica",
    "PR": "Mata Atlantica", "SC": "Mata Atlantica", "RS": "Pampa",
    "MS": "Cerrado", "MT": "Cerrado", "GO": "Cerrado", "DF": "Cerrado",
}


class MapBiomasLandCoverPipeline(BasePipeline):
    """Ingest real MapBiomas land cover data from GCS."""

    def __init__(self):
        super().__init__("mapbiomas_landcover")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM land_cover WHERE source = 'mapbiomas'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 1000

    def download(self) -> pd.DataFrame:
        """Download MapBiomas GeoTIFF and sample at H3 cell centers."""
        # Download the GeoTIFF
        cache_path = get_cache_path("brasil_coverage_2023.tif")

        with PipelineHTTPClient(timeout=1800) as http:
            logger.info("Downloading MapBiomas GeoTIFF (~2GB)...")
            http.download_file(self.urls.mapbiomas_gcs, cache_path)

        # Get municipality centroids and state codes for biome mapping
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id,
                   ST_X(al2.centroid::geometry) as lon,
                   ST_Y(al2.centroid::geometry) as lat,
                   al1.code as state_code
            FROM admin_level_2 al2
            JOIN admin_level_1 al1 ON al2.l1_id = al1.id
            WHERE al2.country_code = 'BR' AND al2.centroid IS NOT NULL
        """)
        municipalities = cur.fetchall()
        cur.close()
        conn.close()

        # Sample raster at H3 cell centers
        try:
            import rasterio
            from rasterio.transform import rowcol
        except ImportError:
            logger.error("rasterio is required for MapBiomas pipeline. Install with: pip install rasterio")
            raise

        rows = []
        seen_h3 = set()

        with rasterio.open(str(cache_path)) as dataset:
            logger.info(f"Raster: {dataset.width}x{dataset.height}, CRS={dataset.crs}")

            for l2_id, lon, lat, state_code in municipalities:
                if lon is None or lat is None:
                    continue

                state_abbr = STATE_ABBREVIATIONS.get(str(state_code), "SP")
                biome = STATE_BIOME.get(state_abbr, "Cerrado")

                # Get H3 cells around the centroid
                center_h3 = h3.geo_to_h3(lat, lon, 8)
                ring_cells = h3.k_ring(center_h3, 2)

                for h3_index in ring_cells:
                    if h3_index in seen_h3:
                        continue
                    seen_h3.add(h3_index)

                    # Get H3 cell center
                    cell_lat, cell_lon = h3.h3_to_geo(h3_index)

                    try:
                        row_idx, col_idx = rowcol(dataset.transform, cell_lon, cell_lat)
                        if (0 <= row_idx < dataset.height and 0 <= col_idx < dataset.width):
                            # Read single pixel using windowed read
                            window = rasterio.windows.Window(col_idx, row_idx, 1, 1)
                            pixel = dataset.read(1, window=window)
                            class_code = int(pixel[0, 0])

                            cover_type = MAPBIOMAS_CLASSES.get(class_code, "other_vegetation")
                            rows.append({
                                "h3_index": h3_index,
                                "cover_type": cover_type,
                                "biome": biome,
                                "cover_pct": 100.0,  # Dominant class at cell center
                                "year": 2023,
                                "source": "mapbiomas",
                            })
                    except Exception:
                        continue

        logger.info(f"Sampled {len(rows)} H3 cells from MapBiomas raster")
        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["h3_index", "cover_type", "year"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty land cover dataset")
        # Validate H3 indices
        invalid = data[~data["h3_index"].apply(h3.h3_is_valid)]
        if len(invalid) > 0:
            raise ValueError(f"{len(invalid)} invalid H3 indices")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Insert land cover records."""
        if data.empty:
            logger.warning("No land cover data to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM land_cover WHERE source = 'mapbiomas'")
        conn.commit()
        cur.close()
        conn.close()

        columns = ["h3_index", "cover_type", "biome", "cover_pct", "year", "source"]
        values = [tuple(row) for row in data[columns].values]

        inserted, updated = upsert_batch(
            table="land_cover",
            columns=columns,
            values=values,
            conflict_columns=["id"],
            db_config=self.db_config,
        )
        self.rows_inserted = inserted
        self.rows_updated = updated
        logger.info(f"Loaded {inserted} land cover records")
