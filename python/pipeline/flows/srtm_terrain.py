"""SRTM terrain tile download pipeline.

Source: OpenTopography S3 (no auth required)
  - Bucket: raster, prefix: SRTM_GL1/SRTM_GL1_srtm/
  - Endpoint: https://opentopography.s3.sdsc.edu
Format: HGT files (3601x3601 int16 big-endian), 1° x 1° tiles
Resolution: ~30m (SRTM1)

Downloads HGT tiles covering all municipalities in the DB,
uploads to MinIO, and registers metadata in terrain_tiles table.
"""
import logging
import math
import os
from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

import pandas as pd

from python.pipeline.base import BasePipeline
from python.pipeline.config import DOWNLOAD_CACHE_DIR, DataSourceURLs, MinIOConfig

logger = logging.getLogger(__name__)


def srtm_tile_name(lat: float, lon: float) -> str:
    """Convert lat/lon to SRTM tile name (e.g., S24W047)."""
    lat_int = int(math.floor(lat))
    lon_int = int(math.floor(lon))
    lat_prefix = "S" if lat_int < 0 else "N"
    lon_prefix = "W" if lon_int < 0 else "E"
    return f"{lat_prefix}{abs(lat_int):02d}{lon_prefix}{abs(lon_int):03d}"


def tile_bbox_wkt(lat: float, lon: float) -> str:
    """Create WKT polygon for a 1x1 degree tile."""
    lat_int = int(math.floor(lat))
    lon_int = int(math.floor(lon))
    return (
        f"SRID=4326;POLYGON(("
        f"{lon_int} {lat_int}, {lon_int + 1} {lat_int}, "
        f"{lon_int + 1} {lat_int + 1}, {lon_int} {lat_int + 1}, "
        f"{lon_int} {lat_int}))"
    )


class SRTMTerrainPipeline(BasePipeline):
    """Download real SRTM tiles from OpenTopography S3 and store in MinIO."""

    def __init__(self):
        super().__init__("srtm_terrain")
        self.urls = DataSourceURLs()
        self.minio_config = MinIOConfig()
        self.cache_dir = Path(DOWNLOAD_CACHE_DIR) / "srtm"

    def check_for_updates(self) -> bool:
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM terrain_tiles WHERE source = 'SRTM1'")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count < 50

    def download(self) -> pd.DataFrame:
        """Determine required tiles and download from OpenTopography S3."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT ST_X(centroid::geometry) as lon, ST_Y(centroid::geometry) as lat
            FROM admin_level_2
            WHERE country_code = 'BR' AND centroid IS NOT NULL
        """)
        centroids = cur.fetchall()
        cur.close()
        conn.close()

        # Determine unique tiles needed
        seen_tiles = set()
        tiles_to_download = []
        for lon, lat in centroids:
            if lon is None or lat is None:
                continue
            tile_name = srtm_tile_name(lat, lon)
            if tile_name in seen_tiles:
                continue
            seen_tiles.add(tile_name)
            tiles_to_download.append({
                "tile_name": tile_name,
                "lat": lat,
                "lon": lon,
            })

        logger.info(f"Need {len(tiles_to_download)} SRTM tiles")

        # Set up S3 client for OpenTopography (unsigned/public)
        s3 = boto3.client(
            "s3",
            endpoint_url=self.urls.srtm_s3_endpoint,
            config=Config(signature_version=UNSIGNED),
        )

        # Set up MinIO client for upload
        minio_s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{self.minio_config.endpoint}",
            aws_access_key_id=self.minio_config.access_key,
            aws_secret_access_key=self.minio_config.secret_key,
        )

        # Ensure MinIO bucket exists
        try:
            minio_s3.head_bucket(Bucket=self.minio_config.bucket_terrain)
        except Exception:
            try:
                minio_s3.create_bucket(Bucket=self.minio_config.bucket_terrain)
            except Exception as e:
                logger.warning(f"Could not create MinIO bucket: {e}")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        downloaded = 0
        failed = 0

        for tile_info in tiles_to_download:
            tile_name = tile_info["tile_name"]
            s3_key = f"{self.urls.srtm_s3_prefix}{tile_name}.hgt"
            local_path = self.cache_dir / f"{tile_name}.hgt"
            minio_key = f"srtm/{tile_name}.hgt"

            try:
                # Download from OpenTopography S3
                if not local_path.exists():
                    s3.download_file(
                        self.urls.srtm_s3_bucket,
                        s3_key,
                        str(local_path),
                    )

                file_size = local_path.stat().st_size

                # Upload to MinIO
                try:
                    minio_s3.upload_file(
                        str(local_path),
                        self.minio_config.bucket_terrain,
                        minio_key,
                    )
                except Exception as e:
                    logger.warning(f"MinIO upload failed for {tile_name}: {e}")

                rows.append({
                    "tile_name": tile_name,
                    "filepath": f"terrain/{minio_key}",
                    "bbox_wkt": tile_bbox_wkt(tile_info["lat"], tile_info["lon"]),
                    "resolution_m": 30.0,
                    "source": "SRTM1",
                    "file_size_bytes": file_size,
                })
                downloaded += 1

                if downloaded % 10 == 0:
                    logger.info(f"Downloaded {downloaded} tiles...")

            except Exception as e:
                logger.warning(f"Could not download SRTM tile {tile_name}: {e}")
                failed += 1

        logger.info(f"Downloaded {downloaded} tiles, {failed} failed")
        return pd.DataFrame(rows)

    def validate_raw(self, data: pd.DataFrame) -> None:
        if data.empty:
            raise ValueError("No terrain tiles downloaded")
        required = ["tile_name", "filepath", "bbox_wkt"]
        missing = set(required) - set(data.columns)
        if missing:
            raise ValueError(f"Missing columns: {missing}")

    def transform(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        self.rows_processed = len(raw_data)
        return raw_data

    def load(self, data: pd.DataFrame) -> None:
        """Insert terrain tile registry entries."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM terrain_tiles WHERE source = 'SRTM1'")
        conn.commit()

        from psycopg2.extras import execute_values
        values = []
        for _, row in data.iterrows():
            values.append((
                row["tile_name"], row["filepath"],
                row["bbox_wkt"], row["resolution_m"],
                row["source"], row["file_size_bytes"],
            ))

        execute_values(cur, """
            INSERT INTO terrain_tiles
            (tile_name, filepath, bbox, resolution_m, source, file_size_bytes)
            VALUES %s
        """, values, template=(
            "(%s, %s, ST_GeomFromEWKT(%s), %s, %s, %s)"
        ), page_size=500)
        conn.commit()
        self.rows_inserted = len(values)
        cur.close()
        conn.close()
        logger.info(f"Registered {self.rows_inserted} terrain tiles")
