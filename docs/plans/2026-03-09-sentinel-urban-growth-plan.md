# Sentinel-2 Urban Growth Intelligence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add satellite-based urban growth detection using Sentinel-2 data to validate and complement IBGE census metrics, with GEE computing indices at scale, Rust generating map tiles, and Python orchestrating the pipeline.

**Architecture:** Three-stage hybrid — Google Earth Engine computes annual NDVI/NDBI/MNDWI/BSI indices per municipality and exports RGB composites; a Python `BasePipeline` subclass orchestrates GEE tasks, downloads results from GCS, and loads into PostgreSQL; a Rust CLI generates XYZ map tiles from COG composites for MinIO serving. Frontend gets new satellite layer, year timeline slider, and growth comparison charts.

**Tech Stack:** Python (earthengine-api, google-cloud-storage), Rust (gdal, image, clap, aws-sdk-s3), PostgreSQL/PostGIS, MinIO, Next.js/React (deck.gl TileLayer, recharts), FastAPI

---

## Task 1: Database Schema — Sentinel Tables

**Files:**
- Create: `python/api/migrations/add_sentinel_tables.sql`

**Step 1: Write the migration SQL**

```sql
-- Sentinel-2 urban indices per municipality per year
CREATE TABLE IF NOT EXISTS sentinel_urban_indices (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER NOT NULL REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    -- Vegetation
    mean_ndvi FLOAT,
    ndvi_std FLOAT,
    -- Built-up
    mean_ndbi FLOAT,
    built_up_area_km2 FLOAT,
    built_up_pct FLOAT,
    -- Water
    mean_mndwi FLOAT,
    water_area_km2 FLOAT,
    -- Bare soil
    mean_bsi FLOAT,
    bare_soil_area_km2 FLOAT,
    -- Year-over-year change
    built_up_change_km2 FLOAT,
    built_up_change_pct FLOAT,
    ndvi_change_pct FLOAT,
    -- Metadata
    cloud_cover_pct FLOAT,
    scenes_used INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(l2_id, year)
);

CREATE INDEX idx_sentinel_indices_l2_year ON sentinel_urban_indices(l2_id, year);
CREATE INDEX idx_sentinel_indices_year ON sentinel_urban_indices(year);

-- Sentinel-2 composite tile metadata
CREATE TABLE IF NOT EXISTS sentinel_composites (
    id SERIAL PRIMARY KEY,
    l2_id INTEGER NOT NULL REFERENCES admin_level_2(id),
    year INTEGER NOT NULL,
    composite_type VARCHAR(20) NOT NULL,  -- 'true_color', 'false_color', 'ndvi'
    filepath VARCHAR(500) NOT NULL,       -- MinIO path
    bbox GEOMETRY(POLYGON, 4326),
    resolution_m FLOAT DEFAULT 10.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(l2_id, year, composite_type)
);

CREATE INDEX idx_sentinel_composites_l2_year ON sentinel_composites(l2_id, year);
CREATE INDEX idx_sentinel_composites_bbox ON sentinel_composites USING GIST(bbox);
```

**Step 2: Run the migration**

```bash
psql $DATABASE_URL -f python/api/migrations/add_sentinel_tables.sql
```

Expected: `CREATE TABLE` x2, `CREATE INDEX` x4

**Step 3: Verify tables exist**

```bash
psql $DATABASE_URL -c "\dt sentinel_*"
```

Expected: `sentinel_urban_indices` and `sentinel_composites` listed

**Step 4: Commit**

```bash
git add python/api/migrations/add_sentinel_tables.sql
git commit -m "feat(db): add sentinel_urban_indices and sentinel_composites tables"
```

---

## Task 2: GEE Compute Script

**Files:**
- Create: `python/pipeline/gee/sentinel_compute.py`
- Create: `python/pipeline/gee/__init__.py`

**Step 1: Write the GEE computation module**

This module authenticates with GEE, computes annual median composites per municipality, calculates NDVI/NDBI/MNDWI/BSI, classifies built-up pixels, and exports results (CSV stats + COG composites) to Google Cloud Storage.

```python
"""Google Earth Engine computation for Sentinel-2 urban indices.

Computes annual median composites per municipality and calculates
NDVI, NDBI, MNDWI, BSI indices. Exports stats as CSV and RGB
composites as COG to Google Cloud Storage.

Requires: GEE service account credentials (JSON key file).
Set GEE_SERVICE_ACCOUNT_KEY env var to the path of the key file.
"""
import ee
import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

GCS_BUCKET = os.getenv("GEE_EXPORT_BUCKET", "enlace-sentinel")
GEE_KEY_PATH = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "")


def initialize_gee():
    """Authenticate and initialize Earth Engine."""
    if GEE_KEY_PATH and os.path.exists(GEE_KEY_PATH):
        credentials = ee.ServiceAccountCredentials(
            email=None,  # read from key file
            key_file=GEE_KEY_PATH,
        )
        ee.Initialize(credentials)
    else:
        ee.Authenticate()
        ee.Initialize(project=os.getenv("GEE_PROJECT", "enlace-platform"))
    logger.info("Google Earth Engine initialized")


def compute_municipality_indices(
    municipality_code: str,
    bbox: list[float],  # [min_lon, min_lat, max_lon, max_lat]
    year: int,
    cloud_threshold: float = 20.0,
) -> ee.batch.Task:
    """Submit a GEE task to compute urban indices for one municipality/year.

    Args:
        municipality_code: IBGE municipality code (e.g. "3550308" for São Paulo)
        bbox: [min_lon, min_lat, max_lon, max_lat] in WGS84
        year: Year to analyze (2016-2026)
        cloud_threshold: Max cloud cover percentage for scene filtering

    Returns:
        GEE export task (already started)
    """
    region = ee.Geometry.Rectangle(bbox)

    # Load Sentinel-2 L2A (atmospherically corrected)
    s2 = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(region)
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
    )

    # Cloud masking using SCL band
    def mask_clouds(image):
        scl = image.select("SCL")
        # SCL values: 4=vegetation, 5=bare soil, 6=water, 7=unclassified,
        # 8=cloud medium prob, 9=cloud high prob, 10=thin cirrus, 11=snow
        mask = scl.neq(8).And(scl.neq(9)).And(scl.neq(10)).And(scl.neq(3))
        return image.updateMask(mask)

    s2_masked = s2.map(mask_clouds)

    # Annual median composite
    composite = s2_masked.median().clip(region)

    # Compute indices
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")
    ndbi = composite.normalizedDifference(["B11", "B8"]).rename("NDBI")
    mndwi = composite.normalizedDifference(["B3", "B11"]).rename("MNDWI")

    # BSI = ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))
    bsi_num = composite.select("B11").add(composite.select("B4")).subtract(
        composite.select("B8").add(composite.select("B2"))
    )
    bsi_den = composite.select("B11").add(composite.select("B4")).add(
        composite.select("B8").add(composite.select("B2"))
    )
    bsi = bsi_num.divide(bsi_den).rename("BSI")

    # Classify built-up pixels: NDBI > 0 AND NDVI < 0.2
    built_up = ndbi.gt(0).And(ndvi.lt(0.2)).rename("built_up")

    # Stack all layers
    indices = ee.Image.cat([ndvi, ndbi, mndwi, bsi, built_up])

    # Reduce to stats
    stats = indices.reduceRegion(
        reducer=ee.Reducer.mean().combine(
            ee.Reducer.stdDev(), sharedInputs=True
        ).combine(
            ee.Reducer.sum(), sharedInputs=True
        ),
        geometry=region,
        scale=10,
        maxPixels=1e9,
        bestEffort=True,
    )

    # Get pixel area for km2 calculations
    pixel_area_km2 = ee.Image.pixelArea().divide(1e6)
    built_up_area = built_up.multiply(pixel_area_km2).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=10,
        maxPixels=1e9,
        bestEffort=True,
    )

    water_area = mndwi.gt(0.3).multiply(pixel_area_km2).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=10,
        maxPixels=1e9,
        bestEffort=True,
    )

    bare_soil_area = bsi.gt(0.1).And(ndvi.lt(0.15)).multiply(pixel_area_km2).reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=region,
        scale=10,
        maxPixels=1e9,
        bestEffort=True,
    )

    # Combine all stats into a single feature for CSV export
    total_area = region.area().divide(1e6)  # km2
    scene_count = s2_masked.size()

    feature = ee.Feature(None, {
        "municipality_code": municipality_code,
        "year": year,
        "mean_ndvi": stats.get("NDVI_mean"),
        "ndvi_std": stats.get("NDVI_stdDev"),
        "mean_ndbi": stats.get("NDBI_mean"),
        "mean_mndwi": stats.get("MNDWI_mean"),
        "mean_bsi": stats.get("BSI_mean"),
        "built_up_area_km2": built_up_area.get("built_up"),
        "built_up_pct": ee.Number(built_up_area.get("built_up")).divide(total_area).multiply(100),
        "water_area_km2": water_area.get("MNDWI"),
        "bare_soil_area_km2": bare_soil_area.get("BSI"),
        "scenes_used": scene_count,
    })

    # Export stats as CSV to GCS
    stats_task = ee.batch.Export.table.toCloudStorage(
        collection=ee.FeatureCollection([feature]),
        description=f"sentinel_stats_{municipality_code}_{year}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"stats/{municipality_code}/{year}/indices",
        fileFormat="CSV",
    )
    stats_task.start()

    # Export RGB composite as GeoTIFF to GCS
    rgb = composite.select(["B4", "B3", "B2"]).multiply(0.0001).clamp(0, 0.3).divide(0.3).multiply(255).toByte()
    rgb_task = ee.batch.Export.image.toCloudStorage(
        image=rgb,
        description=f"sentinel_rgb_{municipality_code}_{year}",
        bucket=GCS_BUCKET,
        fileNamePrefix=f"composites/{municipality_code}/{year}/true_color",
        region=region,
        scale=10,
        crs="EPSG:4326",
        maxPixels=1e9,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    rgb_task.start()

    logger.info(f"Submitted GEE tasks for {municipality_code}/{year}")
    return stats_task, rgb_task


def check_task_status(task_id: str) -> dict:
    """Check the status of a GEE export task."""
    status = ee.data.getTaskStatus(task_id)
    if status:
        return status[0]
    return {"state": "UNKNOWN"}


def batch_compute(
    municipalities: list[dict],  # [{code, bbox, ...}]
    years: list[int],
    batch_size: int = 50,
) -> list[tuple]:
    """Submit GEE tasks for multiple municipalities and years.

    Args:
        municipalities: List of dicts with 'code' and 'bbox' keys
        years: List of years to process
        batch_size: Max concurrent GEE tasks

    Returns:
        List of (municipality_code, year, stats_task, rgb_task) tuples
    """
    all_tasks = []
    pending = 0

    for mun in municipalities:
        for year in years:
            if pending >= batch_size:
                logger.info(f"Batch limit reached ({batch_size}), waiting...")
                return all_tasks

            stats_task, rgb_task = compute_municipality_indices(
                municipality_code=mun["code"],
                bbox=mun["bbox"],
                year=year,
            )
            all_tasks.append((mun["code"], year, stats_task, rgb_task))
            pending += 1

    return all_tasks
```

**Step 2: Create `__init__.py`**

```python
"""Google Earth Engine integration for Sentinel-2 analysis."""
```

**Step 3: Commit**

```bash
git add python/pipeline/gee/
git commit -m "feat(gee): add Sentinel-2 index computation module"
```

---

## Task 3: Python Pipeline — SentinelGrowthPipeline

**Files:**
- Create: `python/pipeline/flows/sentinel_growth.py`
- Modify: `python/pipeline/flows/__init__.py` (add import)
- Modify: `python/pipeline/scheduler.py` (add to schedule)
- Modify: `python/pipeline/config.py` (add MinIO bucket)
- Modify: `python/requirements.txt` (add earthengine-api, google-cloud-storage)

**Step 1: Write the pipeline**

```python
"""Sentinel-2 Urban Growth pipeline.

Orchestrates GEE computation, downloads results from GCS, loads indices
into sentinel_urban_indices, and uploads composites to MinIO.

Lifecycle:
  check_for_updates() — checks if any municipality/year combos are missing
  download() — triggers GEE tasks and downloads results from GCS
  transform() — parses CSV stats into DB-ready rows
  load() — upserts into sentinel_urban_indices, registers composites
  post_load() — triggers Rust tile generation for new composites
"""
import csv
import io
import json
import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
import pandas as pd
from google.cloud import storage as gcs

from python.pipeline.base import BasePipeline
from python.pipeline.config import DatabaseConfig, MinIOConfig
from python.pipeline.gee.sentinel_compute import (
    batch_compute,
    check_task_status,
    initialize_gee,
)

logger = logging.getLogger(__name__)

GCS_BUCKET = os.getenv("GEE_EXPORT_BUCKET", "enlace-sentinel")
TILE_BINARY = os.getenv("ENLACE_TILES_BIN", "enlace-tiles")
YEARS_RANGE = list(range(2016, datetime.now().year + 1))


class SentinelGrowthPipeline(BasePipeline):
    """Compute and load Sentinel-2 urban growth indices for all municipalities."""

    def __init__(self):
        super().__init__("sentinel_growth")
        self.minio = MinIOConfig()
        self._gcs_client = None

    def _get_gcs_client(self):
        if self._gcs_client is None:
            self._gcs_client = gcs.Client()
        return self._gcs_client

    def _get_minio_client(self):
        return boto3.client(
            "s3",
            endpoint_url=f"http://{self.minio.endpoint}",
            aws_access_key_id=self.minio.access_key,
            aws_secret_access_key=self.minio.secret_key,
        )

    def check_for_updates(self) -> bool:
        """Check if there are municipality/year combos missing from sentinel_urban_indices."""
        conn = self._get_connection()
        cur = conn.cursor()
        current_year = datetime.now().year

        # Count existing records
        cur.execute("SELECT COUNT(*) FROM sentinel_urban_indices")
        existing = cur.fetchone()[0]

        # Count total municipalities
        cur.execute("SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'")
        total_mun = cur.fetchone()[0]

        cur.close()
        conn.close()

        # Expected: total_mun * len(YEARS_RANGE) records
        expected = total_mun * len(YEARS_RANGE)
        needs_update = existing < expected
        if needs_update:
            logger.info(f"Sentinel data: {existing}/{expected} records present, update needed")
        return needs_update

    def download(self) -> dict:
        """Fetch municipality bboxes, submit GEE tasks, wait and download results."""
        initialize_gee()

        conn = self._get_connection()
        cur = conn.cursor()

        # Get municipalities with their bounding boxes
        cur.execute("""
            SELECT a2.code, a2.id,
                   ST_XMin(a2.geom) AS min_lon, ST_YMin(a2.geom) AS min_lat,
                   ST_XMax(a2.geom) AS max_lon, ST_YMax(a2.geom) AS max_lat
            FROM admin_level_2 a2
            WHERE a2.country_code = 'BR'
              AND a2.geom IS NOT NULL
            ORDER BY a2.code
        """)
        municipalities = []
        for row in cur.fetchall():
            municipalities.append({
                "code": row[0],
                "l2_id": row[1],
                "bbox": [row[2], row[3], row[4], row[5]],
            })

        # Find which municipality/year combos are missing
        cur.execute("SELECT l2_id, year FROM sentinel_urban_indices")
        existing = {(r[0], r[1]) for r in cur.fetchall()}
        cur.close()
        conn.close()

        # Filter to missing only
        to_process = []
        for mun in municipalities:
            for year in YEARS_RANGE:
                if (mun["l2_id"], year) not in existing:
                    to_process.append((mun, year))

        if not to_process:
            logger.info("All municipality/year combos already processed")
            return {"stats_files": [], "composite_files": [], "municipalities": municipalities}

        logger.info(f"Processing {len(to_process)} municipality/year combos")

        # Submit GEE tasks in batches
        # Group by municipality for batch_compute
        mun_lookup = {m["code"]: m for m in municipalities}
        unique_muns = list({code: mun_lookup[code] for code, _ in
                          [(m["code"], y) for m, y in to_process]}.values())
        unique_years = sorted(set(y for _, y in to_process))

        all_tasks = batch_compute(unique_muns, unique_years, batch_size=50)

        # Wait for tasks to complete (poll every 60s)
        completed_tasks = self._wait_for_tasks(all_tasks)

        # Download results from GCS
        stats_files = []
        composite_files = []
        gcs_client = self._get_gcs_client()
        bucket = gcs_client.bucket(GCS_BUCKET)

        for code, year, _, _ in completed_tasks:
            # Download stats CSV
            stats_blob = bucket.blob(f"stats/{code}/{year}/indices.csv")
            if stats_blob.exists():
                stats_content = stats_blob.download_as_text()
                stats_files.append({"code": code, "year": year, "content": stats_content})

            # Download composite GeoTIFF
            composite_blob = bucket.blob(f"composites/{code}/{year}/true_color.tif")
            if composite_blob.exists():
                local_path = Path(f"/tmp/enlace_cache/sentinel/{code}/{year}/true_color.tif")
                local_path.parent.mkdir(parents=True, exist_ok=True)
                composite_blob.download_to_filename(str(local_path))
                composite_files.append({
                    "code": code, "year": year, "path": str(local_path),
                })

        return {
            "stats_files": stats_files,
            "composite_files": composite_files,
            "municipalities": municipalities,
        }

    def _wait_for_tasks(self, tasks, poll_interval=60, max_wait=7200):
        """Poll GEE task status until all complete or timeout."""
        completed = []
        start = time.time()

        while tasks and (time.time() - start) < max_wait:
            remaining = []
            for code, year, stats_task, rgb_task in tasks:
                s_status = check_task_status(stats_task.id)
                r_status = check_task_status(rgb_task.id)

                s_state = s_status.get("state", "UNKNOWN")
                r_state = r_status.get("state", "UNKNOWN")

                if s_state == "COMPLETED" and r_state == "COMPLETED":
                    completed.append((code, year, stats_task, rgb_task))
                elif s_state in ("FAILED", "CANCELLED") or r_state in ("FAILED", "CANCELLED"):
                    logger.warning(f"GEE task failed for {code}/{year}: stats={s_state}, rgb={r_state}")
                else:
                    remaining.append((code, year, stats_task, rgb_task))

            tasks = remaining
            if tasks:
                logger.info(f"Waiting for {len(tasks)} GEE tasks ({len(completed)} completed)...")
                time.sleep(poll_interval)

        if tasks:
            logger.warning(f"Timeout: {len(tasks)} tasks still running after {max_wait}s")

        return completed

    def validate_raw(self, data: dict) -> None:
        """Validate downloaded data."""
        stats = data.get("stats_files", [])
        composites = data.get("composite_files", [])
        logger.info(f"Downloaded {len(stats)} stats files, {len(composites)} composites")

    def transform(self, raw_data: dict) -> dict:
        """Parse CSV stats into database-ready rows."""
        conn = self._get_connection()
        cur = conn.cursor()
        cur.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_id = {code: l2_id for code, l2_id in cur.fetchall()}
        cur.close()
        conn.close()

        rows = []
        for stats in raw_data["stats_files"]:
            reader = csv.DictReader(io.StringIO(stats["content"]))
            for record in reader:
                l2_id = code_to_id.get(stats["code"])
                if l2_id is None:
                    continue
                rows.append({
                    "l2_id": l2_id,
                    "year": int(stats["year"]),
                    "mean_ndvi": _safe_float(record.get("mean_ndvi")),
                    "ndvi_std": _safe_float(record.get("ndvi_std")),
                    "mean_ndbi": _safe_float(record.get("mean_ndbi")),
                    "built_up_area_km2": _safe_float(record.get("built_up_area_km2")),
                    "built_up_pct": _safe_float(record.get("built_up_pct")),
                    "mean_mndwi": _safe_float(record.get("mean_mndwi")),
                    "water_area_km2": _safe_float(record.get("water_area_km2")),
                    "mean_bsi": _safe_float(record.get("mean_bsi")),
                    "bare_soil_area_km2": _safe_float(record.get("bare_soil_area_km2")),
                    "scenes_used": _safe_int(record.get("scenes_used")),
                })

        self.rows_processed = len(rows)

        # Compute year-over-year changes
        rows_by_mun = {}
        for r in rows:
            rows_by_mun.setdefault(r["l2_id"], []).append(r)

        for l2_id, mun_rows in rows_by_mun.items():
            mun_rows.sort(key=lambda r: r["year"])
            for i in range(1, len(mun_rows)):
                prev = mun_rows[i - 1]
                curr = mun_rows[i]
                if prev["built_up_area_km2"] and curr["built_up_area_km2"]:
                    curr["built_up_change_km2"] = curr["built_up_area_km2"] - prev["built_up_area_km2"]
                    if prev["built_up_area_km2"] > 0:
                        curr["built_up_change_pct"] = (
                            curr["built_up_change_km2"] / prev["built_up_area_km2"] * 100
                        )
                if prev["mean_ndvi"] and curr["mean_ndvi"] and prev["mean_ndvi"] != 0:
                    curr["ndvi_change_pct"] = (
                        (curr["mean_ndvi"] - prev["mean_ndvi"]) / abs(prev["mean_ndvi"]) * 100
                    )

        return {
            "index_rows": rows,
            "composite_files": raw_data["composite_files"],
        }

    def load(self, data: dict) -> None:
        """Upsert indices into sentinel_urban_indices and upload composites to MinIO."""
        conn = self._get_connection()
        cur = conn.cursor()
        from psycopg2.extras import execute_values

        # Upsert index rows
        rows = data["index_rows"]
        if rows:
            values = [
                (
                    r["l2_id"], r["year"], r.get("mean_ndvi"), r.get("ndvi_std"),
                    r.get("mean_ndbi"), r.get("built_up_area_km2"), r.get("built_up_pct"),
                    r.get("mean_mndwi"), r.get("water_area_km2"),
                    r.get("mean_bsi"), r.get("bare_soil_area_km2"),
                    r.get("built_up_change_km2"), r.get("built_up_change_pct"),
                    r.get("ndvi_change_pct"), r.get("scenes_used"),
                )
                for r in rows
            ]
            execute_values(cur, """
                INSERT INTO sentinel_urban_indices (
                    l2_id, year, mean_ndvi, ndvi_std,
                    mean_ndbi, built_up_area_km2, built_up_pct,
                    mean_mndwi, water_area_km2,
                    mean_bsi, bare_soil_area_km2,
                    built_up_change_km2, built_up_change_pct,
                    ndvi_change_pct, scenes_used
                ) VALUES %s
                ON CONFLICT (l2_id, year) DO UPDATE SET
                    mean_ndvi = EXCLUDED.mean_ndvi,
                    ndvi_std = EXCLUDED.ndvi_std,
                    mean_ndbi = EXCLUDED.mean_ndbi,
                    built_up_area_km2 = EXCLUDED.built_up_area_km2,
                    built_up_pct = EXCLUDED.built_up_pct,
                    mean_mndwi = EXCLUDED.mean_mndwi,
                    water_area_km2 = EXCLUDED.water_area_km2,
                    mean_bsi = EXCLUDED.mean_bsi,
                    bare_soil_area_km2 = EXCLUDED.bare_soil_area_km2,
                    built_up_change_km2 = EXCLUDED.built_up_change_km2,
                    built_up_change_pct = EXCLUDED.built_up_change_pct,
                    ndvi_change_pct = EXCLUDED.ndvi_change_pct,
                    scenes_used = EXCLUDED.scenes_used
            """, values, page_size=1000)
            conn.commit()
            self.rows_inserted = len(values)

        # Upload composites to MinIO and register in DB
        s3 = self._get_minio_client()
        bucket_name = "sentinel-composites"

        # Ensure bucket exists
        try:
            s3.head_bucket(Bucket=bucket_name)
        except Exception:
            s3.create_bucket(Bucket=bucket_name)

        conn2 = self._get_connection()
        cur2 = conn2.cursor()

        # Build code->l2_id map
        cur2.execute("SELECT code, id FROM admin_level_2 WHERE country_code = 'BR'")
        code_to_id = {code: l2_id for code, l2_id in cur2.fetchall()}

        for comp in data["composite_files"]:
            local_path = comp["path"]
            code = comp["code"]
            year = comp["year"]
            l2_id = code_to_id.get(code)
            if l2_id is None:
                continue

            minio_key = f"{code}/{year}/true_color.tif"
            s3.upload_file(local_path, bucket_name, minio_key)

            cur2.execute("""
                INSERT INTO sentinel_composites (l2_id, year, composite_type, filepath)
                VALUES (%s, %s, 'true_color', %s)
                ON CONFLICT (l2_id, year, composite_type) DO UPDATE
                SET filepath = EXCLUDED.filepath
            """, (l2_id, year, f"sentinel-composites/{minio_key}"))

        conn2.commit()
        cur2.close()
        conn2.close()

        cur.close()
        conn.close()
        logger.info(f"Loaded {self.rows_inserted} index rows, {len(data['composite_files'])} composites")

    def post_load(self) -> None:
        """Trigger Rust tile generation for new composites."""
        # This will be implemented when the Rust CLI is ready
        logger.info("Post-load: tile generation would be triggered here")


def _safe_float(val) -> float | None:
    if val is None or val == "" or val == "None":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    if val is None or val == "" or val == "None":
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None
```

**Step 2: Add import to `python/pipeline/flows/__init__.py`**

Add at end:
```python
from python.pipeline.flows.sentinel_growth import SentinelGrowthPipeline
```

**Step 3: Add to scheduler `python/pipeline/scheduler.py`**

Add import:
```python
from python.pipeline.flows import SentinelGrowthPipeline
```

Add new schedule function:
```python
def run_monthly_sentinel():
    """Monthly: Sentinel-2 urban growth analysis."""
    logger.info("=== Monthly Sentinel pipeline ===")
    _run_pipeline(SentinelGrowthPipeline)
```

Add scheduler job in `main()`:
```python
# Monthly on 1st at 06:00 UTC — Sentinel-2 satellite data
scheduler.add_job(run_monthly_sentinel, CronTrigger(day=1, hour=6, minute=0),
                  id="monthly_sentinel", name="Monthly Sentinel-2 urban growth")
```

**Step 4: Add MinIO bucket to config**

In `python/pipeline/config.py` `MinIOConfig`, add:
```python
bucket_sentinel: str = "sentinel-composites"
```

**Step 5: Add Python dependencies to `python/requirements.txt`**

Add:
```
earthengine-api>=1.4.0
google-cloud-storage>=2.18.0
```

**Step 6: Commit**

```bash
git add python/pipeline/flows/sentinel_growth.py python/pipeline/gee/ \
        python/pipeline/flows/__init__.py python/pipeline/scheduler.py \
        python/pipeline/config.py python/requirements.txt
git commit -m "feat(pipeline): add SentinelGrowthPipeline with GEE integration"
```

---

## Task 4: Rust CLI — enlace-tiles

**Files:**
- Create: `rust/enlace-tiles/Cargo.toml`
- Create: `rust/enlace-tiles/src/main.rs`

**Step 1: Create `Cargo.toml`**

```toml
[package]
name = "enlace-tiles"
version = "0.1.0"
edition = "2021"
description = "XYZ tile generator for Sentinel-2 COG composites"

[dependencies]
clap = { version = "4", features = ["derive"] }
gdal = "0.17"
image = "0.25"
rayon = "1.10"
anyhow = "1"
aws-config = "1"
aws-sdk-s3 = "1"
tokio = { version = "1", features = ["full"] }
tracing = "0.1"
tracing-subscriber = "0.3"
```

**Step 2: Write `src/main.rs`**

```rust
//! enlace-tiles: Generate XYZ map tiles from Cloud-Optimized GeoTIFFs.
//!
//! Reads a Sentinel-2 RGB composite (COG) and generates a tile pyramid
//! suitable for serving via XYZ tile endpoints (z/x/y.png).
//!
//! Usage:
//!   enlace-tiles --input composite.tif --output /tiles/3550308/2024/ \
//!                --zoom-min 10 --zoom-max 16

use anyhow::{Context, Result};
use clap::Parser;
use gdal::raster::RasterBand;
use gdal::Dataset;
use image::{ImageBuffer, Rgb, RgbImage};
use rayon::prelude::*;
use std::fs;
use std::path::{Path, PathBuf};
use tracing::{info, warn};

#[derive(Parser, Debug)]
#[command(name = "enlace-tiles", about = "Generate XYZ tiles from COG composites")]
struct Args {
    /// Path to the input GeoTIFF file
    #[arg(short, long)]
    input: PathBuf,

    /// Output directory for tiles (will create z/x/y.png structure)
    #[arg(short, long)]
    output: PathBuf,

    /// Minimum zoom level
    #[arg(long, default_value = "10")]
    zoom_min: u32,

    /// Maximum zoom level
    #[arg(long, default_value = "16")]
    zoom_max: u32,

    /// Tile size in pixels
    #[arg(long, default_value = "256")]
    tile_size: u32,
}

/// Convert lat/lon to tile coordinates at a given zoom level
fn lat_lon_to_tile(lat: f64, lon: f64, zoom: u32) -> (u32, u32) {
    let n = 2_f64.powi(zoom as i32);
    let x = ((lon + 180.0) / 360.0 * n).floor() as u32;
    let lat_rad = lat.to_radians();
    let y = ((1.0 - lat_rad.tan().asinh() / std::f64::consts::PI) / 2.0 * n).floor() as u32;
    (x, y)
}

/// Convert tile coordinates back to lat/lon (northwest corner)
fn tile_to_lat_lon(x: u32, y: u32, zoom: u32) -> (f64, f64) {
    let n = 2_f64.powi(zoom as i32);
    let lon = x as f64 / n * 360.0 - 180.0;
    let lat_rad = (std::f64::consts::PI * (1.0 - 2.0 * y as f64 / n)).sinh().atan();
    let lat = lat_rad.to_degrees();
    (lat, lon)
}

/// Read a pixel window from the raster and produce an RGB tile
fn render_tile(
    dataset: &Dataset,
    tile_x: u32,
    tile_y: u32,
    zoom: u32,
    tile_size: u32,
) -> Result<Option<RgbImage>> {
    let (nw_lat, nw_lon) = tile_to_lat_lon(tile_x, tile_y, zoom);
    let (se_lat, se_lon) = tile_to_lat_lon(tile_x + 1, tile_y + 1, zoom);

    // Get the raster's geotransform
    let gt = dataset.geo_transform().context("Failed to read geotransform")?;
    let (raster_w, raster_h) = dataset.raster_size();

    // Convert geographic coordinates to pixel coordinates
    let px_min_x = ((nw_lon - gt[0]) / gt[1]).round() as i64;
    let px_min_y = ((nw_lat - gt[3]) / gt[5]).round() as i64;
    let px_max_x = ((se_lon - gt[0]) / gt[1]).round() as i64;
    let px_max_y = ((se_lat - gt[3]) / gt[5]).round() as i64;

    // Clamp to raster bounds
    let x_off = px_min_x.max(0) as usize;
    let y_off = px_min_y.max(0) as usize;
    let x_end = (px_max_x as usize).min(raster_w);
    let y_end = (px_max_y as usize).min(raster_h);

    if x_off >= x_end || y_off >= y_end {
        return Ok(None); // Tile outside raster bounds
    }

    let win_w = x_end - x_off;
    let win_h = y_end - y_off;

    if win_w == 0 || win_h == 0 {
        return Ok(None);
    }

    // Read RGB bands with windowed read
    let mut img = RgbImage::new(tile_size, tile_size);

    let bands: Vec<Vec<u8>> = (1..=3)
        .map(|b| {
            let band = dataset.rasterband(b).expect("Failed to read band");
            let buf = band
                .read_as::<u8>(
                    (x_off as isize, y_off as isize),
                    (win_w, win_h),
                    (tile_size as usize, tile_size as usize),
                    None,
                )
                .expect("Failed to read raster window");
            buf.data().to_vec()
        })
        .collect();

    for py in 0..tile_size {
        for px in 0..tile_size {
            let idx = (py * tile_size + px) as usize;
            if idx < bands[0].len() {
                img.put_pixel(px, py, Rgb([bands[0][idx], bands[1][idx], bands[2][idx]]));
            }
        }
    }

    Ok(Some(img))
}

fn main() -> Result<()> {
    tracing_subscriber::fmt::init();
    let args = Args::parse();

    info!("Opening raster: {:?}", args.input);
    let dataset = Dataset::open(&args.input).context("Failed to open GeoTIFF")?;
    let (raster_w, raster_h) = dataset.raster_size();
    let gt = dataset.geo_transform()?;

    info!("Raster size: {}x{}", raster_w, raster_h);

    // Compute geographic bounds of the raster
    let min_lon = gt[0];
    let max_lat = gt[3];
    let max_lon = gt[0] + gt[1] * raster_w as f64;
    let min_lat = gt[3] + gt[5] * raster_h as f64;

    info!("Bounds: ({}, {}) to ({}, {})", min_lat, min_lon, max_lat, max_lon);

    let mut total_tiles = 0;

    for zoom in args.zoom_min..=args.zoom_max {
        let (min_tx, min_ty) = lat_lon_to_tile(max_lat, min_lon, zoom);
        let (max_tx, max_ty) = lat_lon_to_tile(min_lat, max_lon, zoom);

        let tiles: Vec<(u32, u32)> = (min_tx..=max_tx)
            .flat_map(|tx| (min_ty..=max_ty).map(move |ty| (tx, ty)))
            .collect();

        info!("Zoom {}: {} tiles", zoom, tiles.len());

        // Note: GDAL Dataset is not Send, so we process sequentially per zoom
        // For parallelism, we'd need to open a Dataset per thread
        for (tx, ty) in &tiles {
            let tile_dir = args.output.join(format!("{}/{}", zoom, tx));
            fs::create_dir_all(&tile_dir)?;
            let tile_path = tile_dir.join(format!("{}.png", ty));

            match render_tile(&dataset, *tx, *ty, zoom, args.tile_size) {
                Ok(Some(img)) => {
                    img.save(&tile_path)
                        .with_context(|| format!("Failed to save tile {:?}", tile_path))?;
                    total_tiles += 1;
                }
                Ok(None) => {} // Outside bounds, skip
                Err(e) => {
                    warn!("Failed to render tile {}/{}/{}: {}", zoom, tx, ty, e);
                }
            }
        }
    }

    info!("Generated {} tiles total", total_tiles);
    Ok(())
}
```

**Step 3: Commit**

```bash
git add rust/enlace-tiles/
git commit -m "feat(rust): add enlace-tiles XYZ tile generator"
```

---

## Task 5: FastAPI Satellite Router

**Files:**
- Create: `python/api/routers/satellite.py`
- Modify: `python/api/main.py` (register router)

**Step 1: Write the satellite router**

```python
"""
ENLACE Satellite Intelligence Router

Endpoints for Sentinel-2 urban growth indices, growth comparisons
with IBGE census data, satellite composite tiles, and growth rankings.
"""
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db

router = APIRouter(prefix="/api/v1/satellite", tags=["satellite"])


# ═══════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════


class SatelliteYearData(BaseModel):
    year: int
    mean_ndvi: Optional[float] = None
    mean_ndbi: Optional[float] = None
    mean_mndwi: Optional[float] = None
    mean_bsi: Optional[float] = None
    built_up_area_km2: Optional[float] = None
    built_up_pct: Optional[float] = None
    water_area_km2: Optional[float] = None
    bare_soil_area_km2: Optional[float] = None
    built_up_change_pct: Optional[float] = None
    ndvi_change_pct: Optional[float] = None
    scenes_used: Optional[int] = None


class GrowthComparison(BaseModel):
    municipality_code: str
    municipality_name: str
    satellite_growth: list[dict[str, Any]]
    ibge_growth: list[dict[str, Any]]
    correlation_summary: dict[str, Any]


class GrowthRankingEntry(BaseModel):
    municipality_code: str
    municipality_name: str
    state_abbrev: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    built_up_change_pct: Optional[float] = None
    built_up_area_km2: Optional[float] = None
    mean_ndvi: Optional[float] = None
    population: Optional[int] = None


# ═══════════════════════════════════════════════════════════════════════
# GET /indices — Annual time series for a municipality
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/indices")
async def get_indices(
    municipality_code: str,
    from_year: int = Query(2016, ge=2016, le=2030),
    to_year: int = Query(2026, ge=2016, le=2030),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Annual satellite indices time series for a municipality."""
    result = await db.execute(
        sa_text("""
            SELECT s.year, s.mean_ndvi, s.ndvi_std, s.mean_ndbi,
                   s.built_up_area_km2, s.built_up_pct,
                   s.mean_mndwi, s.water_area_km2,
                   s.mean_bsi, s.bare_soil_area_km2,
                   s.built_up_change_km2, s.built_up_change_pct,
                   s.ndvi_change_pct, s.scenes_used
            FROM sentinel_urban_indices s
            JOIN admin_level_2 a2 ON a2.id = s.l2_id
            WHERE a2.code = :code
              AND s.year BETWEEN :from_year AND :to_year
            ORDER BY s.year
        """),
        {"code": municipality_code, "from_year": from_year, "to_year": to_year},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No satellite data for municipality {municipality_code}",
        )

    return [
        {
            "year": r.year,
            "mean_ndvi": r.mean_ndvi,
            "ndvi_std": r.ndvi_std,
            "mean_ndbi": r.mean_ndbi,
            "built_up_area_km2": r.built_up_area_km2,
            "built_up_pct": r.built_up_pct,
            "mean_mndwi": r.mean_mndwi,
            "water_area_km2": r.water_area_km2,
            "mean_bsi": r.mean_bsi,
            "bare_soil_area_km2": r.bare_soil_area_km2,
            "built_up_change_km2": r.built_up_change_km2,
            "built_up_change_pct": r.built_up_change_pct,
            "ndvi_change_pct": r.ndvi_change_pct,
            "scenes_used": r.scenes_used,
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# GET /growth — Satellite vs IBGE growth comparison
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/growth")
async def get_growth_comparison(
    municipality_code: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compare satellite-detected urban growth with IBGE census population growth."""
    # Satellite growth
    sat_result = await db.execute(
        sa_text("""
            SELECT s.year, s.built_up_area_km2, s.built_up_pct,
                   s.built_up_change_pct, s.mean_ndvi, s.ndvi_change_pct
            FROM sentinel_urban_indices s
            JOIN admin_level_2 a2 ON a2.id = s.l2_id
            WHERE a2.code = :code
            ORDER BY s.year
        """),
        {"code": municipality_code},
    )
    sat_rows = sat_result.fetchall()

    # IBGE data (population from census + estimates)
    ibge_result = await db.execute(
        sa_text("""
            SELECT a2.name, a2.population, a2.area_km2,
                   a1.code AS state_code
            FROM admin_level_2 a2
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE a2.code = :code
        """),
        {"code": municipality_code},
    )
    mun = ibge_result.fetchone()

    if not mun:
        raise HTTPException(status_code=404, detail=f"Municipality {municipality_code} not found")

    # Population projections if available
    pop_result = await db.execute(
        sa_text("""
            SELECT year, projected_population
            FROM population_projections
            WHERE l2_id = (SELECT id FROM admin_level_2 WHERE code = :code)
            ORDER BY year
        """),
        {"code": municipality_code},
    )
    pop_rows = pop_result.fetchall()

    satellite_growth = [
        {
            "year": r.year,
            "built_up_area_km2": r.built_up_area_km2,
            "built_up_pct": r.built_up_pct,
            "built_up_change_pct": r.built_up_change_pct,
            "mean_ndvi": r.mean_ndvi,
        }
        for r in sat_rows
    ]

    ibge_growth = [
        {"year": r.year, "population": r.projected_population}
        for r in pop_rows
    ]

    # Simple correlation: does built-up growth track population growth?
    sat_changes = [r.built_up_change_pct for r in sat_rows if r.built_up_change_pct is not None]
    avg_sat_growth = sum(sat_changes) / len(sat_changes) if sat_changes else 0

    return {
        "municipality_code": municipality_code,
        "municipality_name": mun.name,
        "satellite_growth": satellite_growth,
        "ibge_growth": ibge_growth,
        "correlation_summary": {
            "avg_annual_built_up_change_pct": round(avg_sat_growth, 2),
            "ibge_population": mun.population,
            "area_km2": float(mun.area_km2) if mun.area_km2 else None,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# GET /ranking — Top municipalities by satellite growth
# ═══════════════════════════════════════════════════════════════════════


@router.get("/ranking")
async def get_growth_ranking(
    state: Optional[str] = Query(None, description="State abbreviation filter"),
    metric: str = Query("built_up_change_pct", description="Ranking metric"),
    years: int = Query(3, ge=1, le=10, description="Number of recent years to average"),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Rank municipalities by satellite-detected urban growth."""
    where_parts = ["1=1"]
    params: dict[str, Any] = {"years": years, "limit": limit}

    if state:
        where_parts.append("a1.code = (SELECT code FROM admin_level_1 WHERE code = :state_code)")
        # Map abbreviation to code
        state_map = await db.execute(
            sa_text("SELECT code FROM admin_level_1 WHERE name ILIKE :abbrev OR code = :abbrev"),
            {"abbrev": state},
        )
        row = state_map.fetchone()
        if row:
            params["state_code"] = row.code
        else:
            params["state_code"] = state

    where_sql = " AND ".join(where_parts)

    result = await db.execute(
        sa_text(f"""
            SELECT a2.code AS municipality_code,
                   a2.name AS municipality_name,
                   a2.population,
                   ST_Y(a2.centroid) AS latitude,
                   ST_X(a2.centroid) AS longitude,
                   AVG(s.built_up_change_pct) AS avg_built_up_change_pct,
                   MAX(s.built_up_area_km2) AS latest_built_up_area_km2,
                   AVG(s.mean_ndvi) AS avg_ndvi
            FROM sentinel_urban_indices s
            JOIN admin_level_2 a2 ON a2.id = s.l2_id
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE s.year >= (EXTRACT(YEAR FROM CURRENT_DATE) - :years)
              AND s.built_up_change_pct IS NOT NULL
              AND {where_sql}
            GROUP BY a2.code, a2.name, a2.population, a2.centroid
            ORDER BY avg_built_up_change_pct DESC NULLS LAST
            LIMIT :limit
        """),
        params,
    )
    rows = result.fetchall()

    return [
        {
            "municipality_code": r.municipality_code,
            "municipality_name": r.municipality_name,
            "population": r.population,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "avg_built_up_change_pct": round(r.avg_built_up_change_pct, 2) if r.avg_built_up_change_pct else None,
            "latest_built_up_area_km2": round(r.latest_built_up_area_km2, 2) if r.latest_built_up_area_km2 else None,
            "avg_ndvi": round(r.avg_ndvi, 3) if r.avg_ndvi else None,
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════════
# GET /composite — Composite metadata
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_code}/composite/{year}")
async def get_composite_metadata(
    municipality_code: str,
    year: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get metadata for available satellite composites."""
    result = await db.execute(
        sa_text("""
            SELECT sc.composite_type, sc.filepath, sc.resolution_m,
                   ST_AsGeoJSON(sc.bbox) AS bbox_geojson
            FROM sentinel_composites sc
            JOIN admin_level_2 a2 ON a2.id = sc.l2_id
            WHERE a2.code = :code AND sc.year = :year
        """),
        {"code": municipality_code, "year": year},
    )
    rows = result.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No composites for {municipality_code}/{year}",
        )

    return [
        {
            "composite_type": r.composite_type,
            "filepath": r.filepath,
            "resolution_m": r.resolution_m,
            "tile_url": f"/api/v1/satellite/{municipality_code}/tiles/{year}/{{z}}/{{x}}/{{y}}.png",
        }
        for r in rows
    ]
```

**Step 2: Register router in `python/api/main.py`**

Add import:
```python
from python.api.routers import satellite
```

Add router registration (after existing routers):
```python
app.include_router(satellite.router)
```

**Step 3: Commit**

```bash
git add python/api/routers/satellite.py python/api/main.py
git commit -m "feat(api): add satellite router with indices, growth, ranking endpoints"
```

---

## Task 6: Frontend — TypeScript Types & API Client

**Files:**
- Modify: `frontend/src/lib/types.ts` (add satellite types)
- Modify: `frontend/src/lib/api.ts` (add satellite API functions)

**Step 1: Add TypeScript types to `frontend/src/lib/types.ts`**

Add at end of file:
```typescript
// ═══════════════════════════════════════════════════════════════════════════════
// Satellite Intelligence
// ═══════════════════════════════════════════════════════════════════════════════

export interface SatelliteYearData {
  year: number;
  mean_ndvi: number | null;
  ndvi_std: number | null;
  mean_ndbi: number | null;
  built_up_area_km2: number | null;
  built_up_pct: number | null;
  mean_mndwi: number | null;
  water_area_km2: number | null;
  mean_bsi: number | null;
  bare_soil_area_km2: number | null;
  built_up_change_km2: number | null;
  built_up_change_pct: number | null;
  ndvi_change_pct: number | null;
  scenes_used: number | null;
}

export interface SatelliteGrowthComparison {
  municipality_code: string;
  municipality_name: string;
  satellite_growth: Array<{
    year: number;
    built_up_area_km2: number | null;
    built_up_pct: number | null;
    built_up_change_pct: number | null;
    mean_ndvi: number | null;
  }>;
  ibge_growth: Array<{
    year: number;
    population: number | null;
  }>;
  correlation_summary: {
    avg_annual_built_up_change_pct: number;
    ibge_population: number | null;
    area_km2: number | null;
  };
}

export interface SatelliteGrowthRanking {
  municipality_code: string;
  municipality_name: string;
  population: number | null;
  latitude: number | null;
  longitude: number | null;
  avg_built_up_change_pct: number | null;
  latest_built_up_area_km2: number | null;
  avg_ndvi: number | null;
}
```

**Step 2: Add API functions to `frontend/src/lib/api.ts`**

Add at end of file (before the closing, or in the appropriate section):
```typescript
// ═══════════════════════════════════════════════════════════════════════════════
// Satellite Intelligence
// ═══════════════════════════════════════════════════════════════════════════════

export async function getSatelliteIndices(
  municipalityCode: string,
  fromYear = 2016,
  toYear = 2026,
): Promise<SatelliteYearData[]> {
  return fetchApi(
    `/api/v1/satellite/${municipalityCode}/indices?from_year=${fromYear}&to_year=${toYear}`,
  );
}

export async function getSatelliteGrowth(
  municipalityCode: string,
): Promise<SatelliteGrowthComparison> {
  return fetchApi(`/api/v1/satellite/${municipalityCode}/growth`);
}

export async function getSatelliteRanking(
  state?: string,
  metric = 'built_up_change_pct',
  years = 3,
  limit = 50,
): Promise<SatelliteGrowthRanking[]> {
  const params = new URLSearchParams({ metric, years: String(years), limit: String(limit) });
  if (state) params.append('state', state);
  return fetchApi(`/api/v1/satellite/ranking?${params}`);
}

export function getSatelliteTileUrl(
  municipalityCode: string,
  year: number,
): string {
  return `${API_BASE}/api/v1/satellite/${municipalityCode}/tiles/${year}/{z}/{x}/{y}.png`;
}
```

Also add the new types to the import block at the top of `api.ts`:
```typescript
import type {
  // ... existing imports ...
  SatelliteYearData,
  SatelliteGrowthComparison,
  SatelliteGrowthRanking,
} from './types';
```

**Step 3: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(frontend): add satellite TypeScript types and API client"
```

---

## Task 7: Frontend — Satellite Page Component

**Files:**
- Create: `frontend/src/app/satelite/page.tsx`

**Step 1: Write the satellite page**

This is the main page that shows satellite growth analysis. It includes:
- A municipality selector
- Year timeline slider
- Growth comparison chart (satellite built-up vs IBGE population)
- Satellite indices time series chart
- Growth ranking table
- Map integration with satellite tile overlay

The page should follow the existing patterns in the codebase (e.g., `expansao/page.tsx` for layout, `saude/page.tsx` for charts). Use recharts for charts (already available in the project). Use the existing MapView component for map integration with a TileLayer from deck.gl for satellite tiles.

Key components to build:
1. `SatelliteGrowthChart` — dual-axis line chart: built_up_area_km2 (left axis) vs IBGE population (right axis) over years
2. `SatelliteIndicesChart` — multi-line chart showing NDVI, NDBI, MNDWI, BSI trends over years
3. `YearSlider` — range input from 2016-2026 that controls which year's satellite tiles display on the map
4. `GrowthRankingTable` — sortable table showing municipalities ranked by satellite growth
5. `SatelliteVsIBGECard` — comparison card highlighting discrepancy (e.g. "Satellite: +12% built-up, IBGE: +8% pop")

The page should be in Portuguese (matching the rest of the app). Route: `/satelite`.

**Step 2: Add navigation link**

Add to the sidebar/navigation component (check existing nav structure first — likely in `frontend/src/components/layout/` or similar).

**Step 3: Commit**

```bash
git add frontend/src/app/satelite/
git commit -m "feat(frontend): add satellite growth intelligence page"
```

---

## Task 8: Frontend — Map Satellite Tile Layer

**Files:**
- Modify: `frontend/src/components/map/MapView.tsx` (add satellite tile layer support)

**Step 1: Add satellite tile layer**

Add a new layer option to MapView that renders XYZ tiles from the satellite API endpoint. Use deck.gl's `TileLayer` with `BitmapLayer` sublayer. The layer should:
- Accept municipality code and year as props
- Fetch tiles from `/api/v1/satellite/{code}/tiles/{year}/{z}/{x}/{y}.png`
- Show/hide via a toggle control on the map
- Include opacity slider

**Step 2: Commit**

```bash
git add frontend/src/components/map/MapView.tsx
git commit -m "feat(map): add satellite tile layer with year selector"
```

---

## Task 9: Integration Tests

**Files:**
- Create: `tests/test_satellite_router.py`
- Create: `tests/test_sentinel_pipeline.py`

**Step 1: Write API router tests**

Test the satellite endpoints with mock database data:
- `test_get_indices_returns_time_series`
- `test_get_indices_404_unknown_municipality`
- `test_get_growth_comparison`
- `test_get_ranking_default`
- `test_get_ranking_with_state_filter`
- `test_get_composite_metadata`

**Step 2: Write pipeline unit tests**

Test the pipeline's transform logic:
- `test_safe_float_conversions`
- `test_safe_int_conversions`
- `test_year_over_year_change_computation`
- `test_transform_parses_csv_correctly`

**Step 3: Run tests**

```bash
pytest tests/test_satellite_router.py tests/test_sentinel_pipeline.py -v
```

**Step 4: Commit**

```bash
git add tests/test_satellite_router.py tests/test_sentinel_pipeline.py
git commit -m "test: add satellite router and pipeline tests"
```

---

## Task 10: Docker & Documentation

**Files:**
- Modify: `docker-compose.yml` (add GEE env vars)
- Modify: `Dockerfile.api` or `python/Dockerfile` (install earthengine-api)

**Step 1: Add environment variables to docker-compose**

Add to the API service:
```yaml
environment:
  - GEE_SERVICE_ACCOUNT_KEY=/secrets/gee-key.json
  - GEE_EXPORT_BUCKET=enlace-sentinel
  - GEE_PROJECT=enlace-platform
  - ENLACE_TILES_BIN=/usr/local/bin/enlace-tiles
```

**Step 2: Add Rust build stage for enlace-tiles**

Create a multi-stage Dockerfile or add to existing:
```dockerfile
FROM rust:1.77 AS tiles-builder
WORKDIR /build
COPY rust/enlace-tiles/ .
RUN cargo build --release

# In the API stage, copy the binary:
COPY --from=tiles-builder /build/target/release/enlace-tiles /usr/local/bin/
```

**Step 3: Commit**

```bash
git add docker-compose.yml Dockerfile.api
git commit -m "chore: add Sentinel/GEE config to Docker setup"
```
