"""Microsoft Building Footprints pipeline.

Source: Microsoft Global ML Building Footprints (2024-06-27 release)
URL: https://minedbuildings.blob.core.windows.net/global-buildings/2024-06-27/by_country/country=BRA/country=BRA.parquet
Format: GeoParquet with geometry column (Polygon/MultiPolygon, WGS84)

Downloads the Brazil GeoParquet, performs spatial join against admin_level_2
to assign l2_id (municipality), computes area_m2, and batch inserts into
the building_footprints table.
"""
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from psycopg2.extras import execute_values

from python.pipeline.base import BasePipeline
from python.pipeline.config import PIPELINE_DEFAULTS
from python.pipeline.http_client import PipelineHTTPClient, get_cache_path

logger = logging.getLogger(__name__)

BUILDINGS_PARQUET_URL = (
    "https://minedbuildings.blob.core.windows.net/global-buildings"
    "/2024-06-27/by_country/country=BRA/country=BRA.parquet"
)


class MSBuildingsPipeline(BasePipeline):
    """Ingest Microsoft Building Footprints for Brazil."""

    def __init__(self):
        super().__init__("ms_buildings")

    def check_for_updates(self) -> bool:
        """Run if the building_footprints table has fewer than 1000 rows."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM building_footprints WHERE source = 'microsoft'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 1000

    def download(self) -> gpd.GeoDataFrame:
        """Download the Brazil GeoParquet from Microsoft's blob storage."""
        cache_path = get_cache_path("ms_buildings_BRA.parquet")

        with PipelineHTTPClient(timeout=600) as http:
            logger.info("Downloading Microsoft Building Footprints GeoParquet for Brazil...")
            http.download_file(BUILDINGS_PARQUET_URL, cache_path)

        logger.info(f"Reading GeoParquet from {cache_path}...")
        gdf = gpd.read_parquet(cache_path)
        logger.info(f"Loaded {len(gdf):,} building footprints from parquet")
        return gdf

    def validate_raw(self, data) -> None:
        if data.empty:
            raise ValueError("Empty building footprints dataset")
        if "geometry" not in data.columns and data.geometry is None:
            raise ValueError("No geometry column found in parquet")

    def transform(self, raw_data: gpd.GeoDataFrame) -> pd.DataFrame:
        """Spatial join buildings to municipalities and compute area."""
        gdf = raw_data

        # Ensure CRS is WGS84
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=4326)
        elif gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)

        # Load municipality geometries for spatial join
        conn = self._get_connection()
        logger.info("Loading municipality geometries for spatial join...")
        municipalities = gpd.read_postgis(
            "SELECT id AS l2_id, geom FROM admin_level_2 WHERE country_code = 'BR' AND geom IS NOT NULL",
            conn,
            geom_col="geom",
        )
        conn.close()

        if municipalities.empty:
            raise ValueError("No municipality geometries found in admin_level_2")

        # Use building centroids for faster spatial join
        logger.info("Computing building centroids for spatial join...")
        buildings_centroids = gdf.copy()
        buildings_centroids["original_geom"] = buildings_centroids.geometry
        buildings_centroids.geometry = buildings_centroids.geometry.centroid

        logger.info(f"Spatial joining {len(buildings_centroids):,} buildings to {len(municipalities)} municipalities...")
        joined = gpd.sjoin(
            buildings_centroids,
            municipalities,
            how="inner",
            predicate="within",
        )
        logger.info(f"Matched {len(joined):,} buildings to municipalities")

        # Restore original polygon geometry
        joined.geometry = joined["original_geom"]
        joined = joined.drop(columns=["original_geom", "index_right"], errors="ignore")

        # Compute area in square meters using UTM projection
        # Use a rough estimate: project to equal-area for area computation
        logger.info("Computing building areas...")
        joined_ea = joined.to_crs(epsg=6933)  # Equal Earth projection
        joined["area_m2"] = joined_ea.geometry.area

        # Build output rows
        rows = []
        for _, row in joined.iterrows():
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue

            # Convert to Polygon WKT (take first polygon if MultiPolygon)
            if geom.geom_type == "MultiPolygon":
                geom = max(geom.geoms, key=lambda g: g.area)

            if geom.geom_type != "Polygon":
                continue

            coords = list(geom.exterior.coords)
            coord_str = ", ".join(f"{c[0]} {c[1]}" for c in coords)
            geom_ewkt = f"SRID=4326;POLYGON(({coord_str}))"

            rows.append({
                "l2_id": int(row["l2_id"]),
                "source": "microsoft",
                "area_m2": round(float(row["area_m2"]), 2),
                "height_m": None,
                "geom_ewkt": geom_ewkt,
            })

        self.rows_processed = len(rows)
        logger.info(f"Transformed {len(rows):,} building footprints")
        return pd.DataFrame(rows)

    def load(self, data: pd.DataFrame) -> None:
        """Batch insert building footprints into PostgreSQL."""
        if data.empty:
            logger.warning("No building footprints to load")
            return

        conn = self._get_connection()
        cur = conn.cursor()

        # Clear existing Microsoft buildings before reload
        cur.execute("DELETE FROM building_footprints WHERE source = 'microsoft'")
        conn.commit()
        logger.info("Cleared existing Microsoft building footprints")

        batch_size = PIPELINE_DEFAULTS["batch_size"]
        total_inserted = 0

        values = []
        for _, row in data.iterrows():
            values.append((
                row["l2_id"],
                row["source"],
                row["area_m2"],
                row["height_m"],
                row["geom_ewkt"],
            ))

            if len(values) >= batch_size:
                execute_values(cur, """
                    INSERT INTO building_footprints (l2_id, source, area_m2, height_m, geom)
                    VALUES %s
                """, values, template=(
                    "(%s, %s, %s, %s, ST_GeomFromEWKT(%s))"
                ), page_size=1000)
                conn.commit()
                total_inserted += len(values)
                logger.info(f"Inserted {total_inserted:,} buildings so far...")
                values = []

        # Insert remaining
        if values:
            execute_values(cur, """
                INSERT INTO building_footprints (l2_id, source, area_m2, height_m, geom)
                VALUES %s
            """, values, template=(
                "(%s, %s, %s, %s, ST_GeomFromEWKT(%s))"
            ), page_size=1000)
            conn.commit()
            total_inserted += len(values)

        self.rows_inserted = total_inserted
        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted:,} building footprints")
