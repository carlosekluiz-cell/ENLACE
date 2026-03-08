"""MapBiomas land use/cover classification pipeline.

Source: MapBiomas collection
URL: https://mapbiomas.org/
Format: Raster classification (GeoTIFF), accessed via GEE or direct download
Resolution: 30m pixels, annual classification since 1985

Uses H3 hexagonal indexing at resolution 8 (~0.74 km2 per hex) to store
land cover classifications. Each H3 cell stores the dominant land cover
type and biome.

Real download would:
1. Download MapBiomas raster tiles for Brazil
2. Sample land cover at H3 cell centers
3. Classify dominant cover type per hex
"""
import logging
import random

import h3
import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DataSourceURLs
from python.pipeline.loaders.postgres_loader import upsert_batch

logger = logging.getLogger(__name__)

# MapBiomas level-1 classification
COVER_TYPES = [
    "forest",
    "savanna",
    "grassland",
    "agriculture",
    "pasture",
    "urban",
    "water",
    "wetland",
    "bare_soil",
    "other_vegetation",
]

# Brazilian biomes with typical land cover distributions
BIOME_PROFILES = {
    "Amazonia": {
        "covers": ["forest", "water", "agriculture", "pasture", "other_vegetation"],
        "weights": [0.55, 0.08, 0.12, 0.15, 0.10],
    },
    "Cerrado": {
        "covers": ["savanna", "agriculture", "pasture", "grassland", "forest"],
        "weights": [0.30, 0.25, 0.20, 0.15, 0.10],
    },
    "Mata Atlantica": {
        "covers": ["forest", "urban", "agriculture", "pasture", "other_vegetation"],
        "weights": [0.25, 0.20, 0.20, 0.20, 0.15],
    },
    "Caatinga": {
        "covers": ["savanna", "agriculture", "bare_soil", "pasture", "other_vegetation"],
        "weights": [0.30, 0.20, 0.15, 0.20, 0.15],
    },
    "Pampa": {
        "covers": ["grassland", "agriculture", "pasture", "forest", "wetland"],
        "weights": [0.30, 0.30, 0.20, 0.10, 0.10],
    },
    "Pantanal": {
        "covers": ["wetland", "grassland", "forest", "water", "pasture"],
        "weights": [0.30, 0.20, 0.20, 0.15, 0.15],
    },
}

# Map municipality states to approximate biomes
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
    """Ingest MapBiomas land cover data indexed by H3 cells."""

    def __init__(self):
        super().__init__("mapbiomas_landcover")
        self.urls = DataSourceURLs()

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM land_cover")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 100

    def download(self) -> pd.DataFrame:
        try:
            logger.info("Attempting real MapBiomas download...")
            raise ConnectionError("Real download not available in dev environment")
        except Exception as e:
            logger.info(f"Real download failed ({e}), generating synthetic data")
            return self._generate_synthetic()

    def _generate_synthetic(self) -> pd.DataFrame:
        """Generate land cover data for H3 cells around seed municipalities."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT al2.id, al2.code,
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

        random.seed(47)
        rows = []
        seen_h3 = set()

        for l2_id, code, lon, lat, state_code in municipalities:
            if lon is None or lat is None:
                continue

            # Determine biome based on state
            state_abbr = state_code[:2] if len(state_code) >= 2 else "SP"
            biome = STATE_BIOME.get(state_abbr, "Cerrado")
            profile = BIOME_PROFILES.get(biome, BIOME_PROFILES["Cerrado"])

            # Get H3 cell at resolution 8 for the centroid
            center_h3 = h3.geo_to_h3(lat, lon, 8)
            # Get k-ring of radius 2 (about 19 cells)
            ring_cells = h3.k_ring(center_h3, 2)

            for h3_index in ring_cells:
                if h3_index in seen_h3:
                    continue
                seen_h3.add(h3_index)

                cover = random.choices(
                    profile["covers"], weights=profile["weights"]
                )[0]
                cover_pct = round(random.uniform(40, 95), 1)

                rows.append({
                    "h3_index": h3_index,
                    "cover_type": cover,
                    "biome": biome,
                    "cover_pct": cover_pct,
                    "year": 2023,
                    "source": "mapbiomas_synthetic",
                })

        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        required = ["h3_index", "cover_type", "year"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")
        if data.empty:
            raise ValueError("Empty dataset")
        # Validate H3 indices
        invalid = data[~data["h3_index"].apply(h3.h3_is_valid)]
        if len(invalid) > 0:
            raise ValueError(f"{len(invalid)} invalid H3 indices")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Insert land cover records."""
        # Clear existing synthetic data
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM land_cover WHERE source = 'mapbiomas_synthetic'")
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
