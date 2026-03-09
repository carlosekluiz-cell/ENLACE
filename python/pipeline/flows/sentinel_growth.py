"""Sentinel-2 urban growth pipeline.

Orchestrates Google Earth Engine computation, downloads results from GCS,
loads spectral indices into PostgreSQL (sentinel_urban_indices), and uploads
Cloud-Optimised GeoTIFF composites to MinIO (sentinel-composites bucket).

Lifecycle (via BasePipeline):
    check_for_updates -> download -> validate_raw -> transform -> load -> post_load

Environment variables:
    GEE_EXPORT_BUCKET: GCS bucket where GEE exports land (default: "enlace-sentinel").

Depends on:
    python.pipeline.gee.sentinel_compute — GEE task submission
    google.cloud.storage — downloading results from GCS
    boto3 — uploading COGs to MinIO
"""
from __future__ import annotations

import csv
import io
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import execute_values

from python.pipeline.base import BasePipeline
from python.pipeline.config import DOWNLOAD_CACHE_DIR, MinIOConfig

# Optional dependencies — imported lazily at runtime to avoid breaking
# other pipelines when earthengine-api / google-cloud-storage aren't installed.
try:
    import boto3
    from google.cloud import storage as gcs_storage
    from python.pipeline.gee.sentinel_compute import (
        GEE_EXPORT_BUCKET,
        MunicipalitySpec,
        TaskPair,
        batch_compute,
        check_task_status,
        initialize_gee,
    )
    _HAS_SENTINEL_DEPS = True
except ImportError:
    _HAS_SENTINEL_DEPS = False

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

START_YEAR = 2016
TASK_POLL_INTERVAL_SECONDS = 60
TASK_MAX_WAIT_SECONDS = 2 * 60 * 60  # 2 hours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(val: Any) -> Optional[float]:
    """Parse a value into float, returning None for empty/invalid values."""
    if val is None:
        return None
    s = str(val).strip()
    if s == "" or s.lower() == "none" or s.lower() == "null":
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _safe_int(val: Any) -> Optional[int]:
    """Parse a value into int, returning None for empty/invalid values."""
    f = _safe_float(val)
    if f is None:
        return None
    return int(f)


class SentinelGrowthPipeline(BasePipeline):
    """Download Sentinel-2 urban growth indices from GEE and store in PostgreSQL + MinIO."""

    def __init__(self):
        super().__init__("sentinel_growth")
        if not _HAS_SENTINEL_DEPS:
            raise ImportError(
                "Sentinel pipeline requires: pip install earthengine-api google-cloud-storage boto3"
            )
        self.minio_config = MinIOConfig()
        self.cache_dir = Path(DOWNLOAD_CACHE_DIR) / "sentinel"
        self.gcs_bucket = os.getenv("GEE_EXPORT_BUCKET", GEE_EXPORT_BUCKET)

    # ------------------------------------------------------------------
    # check_for_updates
    # ------------------------------------------------------------------

    def check_for_updates(self) -> bool:
        """Return True if sentinel_urban_indices is missing expected rows.

        Expected row count = number_of_municipalities * years (2016..current_year).
        """
        current_year = datetime.utcnow().year
        num_years = current_year - START_YEAR + 1

        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) FROM admin_level_2 WHERE country_code = 'BR'"
            )
            num_municipalities = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM sentinel_urban_indices")
            existing = cur.fetchone()[0]
        finally:
            cur.close()
            conn.close()

        expected = num_municipalities * num_years
        if existing < expected:
            logger.info(
                "sentinel_urban_indices has %d rows, expected %d (%d municipalities x %d years)",
                existing,
                expected,
                num_municipalities,
                num_years,
            )
            return True

        logger.info(
            "sentinel_urban_indices is up to date (%d rows)", existing
        )
        return False

    # ------------------------------------------------------------------
    # download
    # ------------------------------------------------------------------

    def download(self) -> dict:
        """Submit GEE tasks, wait for completion, download results from GCS.

        Returns dict with keys: stats_files, composite_files, municipalities.
        """
        # 1) Initialise GEE
        initialize_gee()

        current_year = datetime.utcnow().year
        all_years = list(range(START_YEAR, current_year + 1))

        # 2) Fetch municipalities with bounding boxes
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT a2.id, a2.code, a2.name,
                       ST_XMin(a2.geom) AS xmin,
                       ST_YMin(a2.geom) AS ymin,
                       ST_XMax(a2.geom) AS xmax,
                       ST_YMax(a2.geom) AS ymax
                FROM admin_level_2 a2
                WHERE a2.country_code = 'BR'
                  AND a2.geom IS NOT NULL
            """)
            municipality_rows = cur.fetchall()

            # 3) Find which municipality/year combos already exist
            cur.execute("""
                SELECT a2.code, sui.year
                FROM sentinel_urban_indices sui
                JOIN admin_level_2 a2 ON a2.id = sui.l2_id
            """)
            existing_combos: Set[Tuple[str, int]] = {
                (str(row[0]), int(row[1])) for row in cur.fetchall()
            }
        finally:
            cur.close()
            conn.close()

        # Build MunicipalitySpec list for missing combos
        # Group by municipality, track which years are missing
        missing_specs: List[MunicipalitySpec] = []
        missing_years_by_code: Dict[str, List[int]] = {}

        for l2_id, code, name, xmin, ymin, xmax, ymax in municipality_rows:
            code_str = str(code)
            years_needed = [
                y for y in all_years if (code_str, y) not in existing_combos
            ]
            if not years_needed:
                continue
            missing_specs.append(
                MunicipalitySpec(
                    code=code_str,
                    bbox=[xmin, ymin, xmax, ymax],
                    name=name or "",
                )
            )
            missing_years_by_code[code_str] = years_needed

        if not missing_specs:
            logger.info("No missing municipality/year combos — nothing to compute")
            return {
                "stats_files": [],
                "composite_files": [],
                "municipalities": municipality_rows,
            }

        # Flatten to get all unique years needed across all municipalities
        all_missing_years = sorted(
            {y for yrs in missing_years_by_code.values() for y in yrs}
        )

        logger.info(
            "Submitting GEE tasks for %d municipalities, years %s",
            len(missing_specs),
            all_missing_years,
        )

        # 4) Submit GEE batch tasks
        task_pairs: List[TaskPair] = batch_compute(
            municipalities=missing_specs,
            years=all_missing_years,
        )

        # 5) Wait for all tasks to complete (poll every 60s, max 2 hours)
        self._wait_for_tasks(task_pairs)

        # 6) Download CSV stats and COG composites from GCS
        stats_files, composite_files = self._download_from_gcs(task_pairs)

        return {
            "stats_files": stats_files,
            "composite_files": composite_files,
            "municipalities": municipality_rows,
        }

    # ------------------------------------------------------------------
    # validate_raw
    # ------------------------------------------------------------------

    def validate_raw(self, data: dict) -> None:
        """Validate that we have stats files to process."""
        stats = data.get("stats_files", [])
        composites = data.get("composite_files", [])
        logger.info(
            "Validation: %d stats files, %d composite files",
            len(stats),
            len(composites),
        )
        # It is acceptable to have zero files if check_for_updates found
        # nothing missing — the pipeline will simply skip loading.

    # ------------------------------------------------------------------
    # transform
    # ------------------------------------------------------------------

    def transform(self, raw_data: dict) -> dict:
        """Parse CSV stats, compute year-over-year changes, return load-ready rows.

        Returns dict with keys: index_rows, composite_files.
        """
        stats_files: List[dict] = raw_data.get("stats_files", [])
        municipality_rows = raw_data.get("municipalities", [])

        # Build code -> l2_id mapping
        code_to_l2_id: Dict[str, int] = {}
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, code FROM admin_level_2 WHERE country_code = 'BR'"
            )
            for l2_id, code in cur.fetchall():
                code_to_l2_id[str(code)] = l2_id
        finally:
            cur.close()
            conn.close()

        # Parse CSV stats into row dicts
        parsed_rows: List[dict] = []
        for sf in stats_files:
            csv_content = sf.get("content", "")
            code = sf.get("municipality_code", "")
            year = sf.get("year")

            l2_id = code_to_l2_id.get(code)
            if l2_id is None:
                logger.warning(
                    "No admin_level_2 match for municipality code %s", code
                )
                continue

            row = self._parse_stats_csv(csv_content, l2_id, code, year)
            if row:
                parsed_rows.append(row)

        self.rows_processed = len(parsed_rows)
        logger.info("Parsed %d index rows from CSV stats", len(parsed_rows))

        # Compute year-over-year changes
        index_rows = self._compute_yoy_changes(parsed_rows)

        return {
            "index_rows": index_rows,
            "composite_files": raw_data.get("composite_files", []),
        }

    # ------------------------------------------------------------------
    # load
    # ------------------------------------------------------------------

    def load(self, data: dict) -> None:
        """UPSERT index rows into sentinel_urban_indices, upload COGs to MinIO."""
        index_rows: List[dict] = data.get("index_rows", [])
        composite_files: List[dict] = data.get("composite_files", [])

        # 1) UPSERT spectral indices into PostgreSQL
        if index_rows:
            self._load_indices(index_rows)

        # 2) Upload COGs to MinIO and register in sentinel_composites
        if composite_files:
            self._upload_composites(composite_files)

    # ------------------------------------------------------------------
    # post_load
    # ------------------------------------------------------------------

    def post_load(self) -> None:
        """Log that tile generation would be triggered.

        The Rust CLI (enlace-tiles) handles COG-to-tile conversion
        and will be invoked as a separate step in Task 4.
        """
        logger.info(
            "[%s] Post-load: tile generation would be triggered via "
            "enlace-tiles CLI (not yet implemented — see Task 4)",
            self.name,
        )

    # ==================================================================
    # Private helpers
    # ==================================================================

    def _wait_for_tasks(self, task_pairs: List[TaskPair]) -> None:
        """Poll GEE tasks until all complete or timeout (2 hours)."""
        if not task_pairs:
            return

        start = time.time()
        total_tasks = len(task_pairs) * 2  # stats + rgb per pair

        while True:
            elapsed = time.time() - start
            if elapsed > TASK_MAX_WAIT_SECONDS:
                logger.warning(
                    "Timeout after %.0f seconds waiting for GEE tasks", elapsed
                )
                break

            completed = 0
            failed = 0
            running = 0

            for tp in task_pairs:
                for task_id in (tp.stats_task_id, tp.rgb_task_id):
                    if task_id is None:
                        completed += 1
                        continue
                    status = check_task_status(task_id)
                    state = status.get("state", "UNKNOWN")
                    if state == "COMPLETED":
                        completed += 1
                    elif state == "FAILED":
                        failed += 1
                        completed += 1  # count as done (won't retry)
                        logger.warning(
                            "GEE task %s FAILED: %s",
                            task_id,
                            status.get("error_message", "unknown"),
                        )
                    elif state in ("READY", "RUNNING"):
                        running += 1

            logger.info(
                "GEE tasks: %d/%d completed (%d failed), %d running (%.0fs elapsed)",
                completed,
                total_tasks,
                failed,
                running,
                elapsed,
            )

            if completed >= total_tasks:
                logger.info("All GEE tasks finished")
                break

            time.sleep(TASK_POLL_INTERVAL_SECONDS)

    def _download_from_gcs(
        self, task_pairs: List[TaskPair]
    ) -> Tuple[List[dict], List[dict]]:
        """Download CSV stats and COG composites from GCS.

        Returns (stats_files, composite_files) where each entry is a dict
        with metadata and file content/path.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        client = gcs_storage.Client()
        bucket = client.bucket(self.gcs_bucket)

        stats_files: List[dict] = []
        composite_files: List[dict] = []

        for tp in task_pairs:
            code = tp.municipality_code
            year = tp.year

            # Download stats CSV
            stats_prefix = f"stats/{code}/{year}"
            try:
                blobs = list(bucket.list_blobs(prefix=stats_prefix))
                csv_blobs = [b for b in blobs if b.name.endswith(".csv")]
                if csv_blobs:
                    csv_content = csv_blobs[0].download_as_text()
                    stats_files.append({
                        "municipality_code": code,
                        "year": year,
                        "content": csv_content,
                        "gcs_path": csv_blobs[0].name,
                    })
                    logger.debug("Downloaded stats CSV: %s", csv_blobs[0].name)
                else:
                    logger.warning("No stats CSV found for %s/%d", code, year)
            except Exception as e:
                logger.warning(
                    "Failed to download stats for %s/%d: %s", code, year, e
                )

            # Download RGB composite COG
            rgb_prefix = f"rgb/{code}/{year}"
            try:
                blobs = list(bucket.list_blobs(prefix=rgb_prefix))
                tif_blobs = [b for b in blobs if b.name.endswith(".tif")]
                if tif_blobs:
                    local_path = self.cache_dir / f"{code}_{year}.tif"
                    tif_blobs[0].download_to_filename(str(local_path))
                    composite_files.append({
                        "municipality_code": code,
                        "year": year,
                        "local_path": str(local_path),
                        "gcs_path": tif_blobs[0].name,
                        "file_size_bytes": local_path.stat().st_size,
                    })
                    logger.debug(
                        "Downloaded composite COG: %s", tif_blobs[0].name
                    )
                else:
                    logger.warning(
                        "No composite COG found for %s/%d", code, year
                    )
            except Exception as e:
                logger.warning(
                    "Failed to download composite for %s/%d: %s",
                    code,
                    year,
                    e,
                )

        logger.info(
            "Downloaded %d stats files and %d composite files from GCS",
            len(stats_files),
            len(composite_files),
        )
        return stats_files, composite_files

    def _parse_stats_csv(
        self, csv_content: str, l2_id: int, code: str, year: int
    ) -> Optional[dict]:
        """Parse a single GEE-exported stats CSV into a row dict."""
        if not csv_content or not csv_content.strip():
            return None

        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            return {
                "l2_id": l2_id,
                "year": year,
                "municipality_code": code,
                "ndvi_mean": _safe_float(row.get("ndvi_mean")),
                "ndbi_mean": _safe_float(row.get("ndbi_mean")),
                "mndwi_mean": _safe_float(row.get("mndwi_mean")),
                "bsi_mean": _safe_float(row.get("bsi_mean")),
                "built_up_area_km2": _safe_float(row.get("builtup_area_km2")),
                "built_up_pct": _safe_float(row.get("builtup_pct")),
                "pixel_count": _safe_int(row.get("total_pixels")),
                "cloud_free_pct": None,  # not exported by GEE; could be added later
            }
        return None

    def _compute_yoy_changes(self, rows: List[dict]) -> List[dict]:
        """Compute year-over-year changes for built-up area and NDVI.

        For each municipality, sort by year and compute deltas against the
        previous year.
        """
        # Group by municipality
        by_municipality: Dict[int, List[dict]] = {}
        for r in rows:
            by_municipality.setdefault(r["l2_id"], []).append(r)

        result: List[dict] = []
        for l2_id, muni_rows in by_municipality.items():
            muni_rows.sort(key=lambda x: x["year"])
            prev: Optional[dict] = None

            for r in muni_rows:
                if prev is not None:
                    prev_area = prev.get("built_up_area_km2")
                    curr_area = r.get("built_up_area_km2")
                    prev_ndvi = prev.get("ndvi_mean")
                    curr_ndvi = r.get("ndvi_mean")

                    # built_up_change_km2
                    if curr_area is not None and prev_area is not None:
                        r["built_up_change_km2"] = curr_area - prev_area
                    else:
                        r["built_up_change_km2"] = None

                    # built_up_change_pct
                    if (
                        curr_area is not None
                        and prev_area is not None
                        and prev_area > 0
                    ):
                        r["built_up_change_pct"] = (
                            (curr_area - prev_area) / prev_area
                        ) * 100.0
                    else:
                        r["built_up_change_pct"] = None

                    # ndvi_change_pct
                    if (
                        curr_ndvi is not None
                        and prev_ndvi is not None
                        and prev_ndvi != 0
                    ):
                        r["ndvi_change_pct"] = (
                            (curr_ndvi - prev_ndvi) / abs(prev_ndvi)
                        ) * 100.0
                    else:
                        r["ndvi_change_pct"] = None
                else:
                    # First year — no previous data
                    r["built_up_change_km2"] = None
                    r["built_up_change_pct"] = None
                    r["ndvi_change_pct"] = None

                result.append(r)
                prev = r

        return result

    def _load_indices(self, index_rows: List[dict]) -> None:
        """UPSERT rows into sentinel_urban_indices."""
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            values = []
            for r in index_rows:
                values.append((
                    r["l2_id"],
                    r["year"],
                    r.get("ndvi_mean"),
                    r.get("ndbi_mean"),
                    r.get("mndwi_mean"),
                    r.get("bsi_mean"),
                    r.get("built_up_area_km2"),
                    r.get("built_up_pct"),
                    r.get("built_up_change_km2"),
                    r.get("built_up_change_pct"),
                    r.get("ndvi_change_pct"),
                    r.get("pixel_count"),
                    r.get("cloud_free_pct"),
                ))

            execute_values(
                cur,
                """
                INSERT INTO sentinel_urban_indices (
                    l2_id, year,
                    ndvi_mean, ndbi_mean, mndwi_mean, bsi_mean,
                    built_up_area_km2, built_up_pct,
                    built_up_change_km2, built_up_change_pct, ndvi_change_pct,
                    pixel_count, cloud_free_pct
                ) VALUES %s
                ON CONFLICT (l2_id, year) DO UPDATE SET
                    ndvi_mean = EXCLUDED.ndvi_mean,
                    ndbi_mean = EXCLUDED.ndbi_mean,
                    mndwi_mean = EXCLUDED.mndwi_mean,
                    bsi_mean = EXCLUDED.bsi_mean,
                    built_up_area_km2 = EXCLUDED.built_up_area_km2,
                    built_up_pct = EXCLUDED.built_up_pct,
                    built_up_change_km2 = EXCLUDED.built_up_change_km2,
                    built_up_change_pct = EXCLUDED.built_up_change_pct,
                    ndvi_change_pct = EXCLUDED.ndvi_change_pct,
                    pixel_count = EXCLUDED.pixel_count,
                    cloud_free_pct = EXCLUDED.cloud_free_pct,
                    computed_at = NOW()
                """,
                values,
                template=(
                    "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ),
                page_size=500,
            )
            conn.commit()
            self.rows_inserted = len(values)
            logger.info(
                "Upserted %d rows into sentinel_urban_indices", len(values)
            )
        finally:
            cur.close()
            conn.close()

    def _upload_composites(self, composite_files: List[dict]) -> None:
        """Upload COG files to MinIO and register in sentinel_composites table."""
        # Build code -> l2_id map
        conn = self._get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, code FROM admin_level_2 WHERE country_code = 'BR'"
            )
            code_to_l2_id: Dict[str, int] = {
                str(code): l2_id for l2_id, code in cur.fetchall()
            }
        finally:
            cur.close()
            conn.close()

        # Set up MinIO (S3-compatible) client
        minio_s3 = boto3.client(
            "s3",
            endpoint_url=f"http://{self.minio_config.endpoint}",
            aws_access_key_id=self.minio_config.access_key,
            aws_secret_access_key=self.minio_config.secret_key,
        )

        # Ensure bucket exists
        bucket_name = self.minio_config.bucket_sentinel
        try:
            minio_s3.head_bucket(Bucket=bucket_name)
        except Exception:
            try:
                minio_s3.create_bucket(Bucket=bucket_name)
                logger.info("Created MinIO bucket: %s", bucket_name)
            except Exception as e:
                logger.warning("Could not create MinIO bucket %s: %s", bucket_name, e)

        uploaded = 0
        conn = self._get_connection()
        cur = conn.cursor()

        try:
            for cf in composite_files:
                code = cf["municipality_code"]
                year = cf["year"]
                local_path = cf["local_path"]
                file_size = cf.get("file_size_bytes", 0)

                l2_id = code_to_l2_id.get(code)
                if l2_id is None:
                    logger.warning(
                        "No admin_level_2 match for code %s, skipping composite",
                        code,
                    )
                    continue

                minio_key = f"rgb/{code}/{year}.tif"

                # Upload to MinIO
                try:
                    minio_s3.upload_file(
                        local_path,
                        bucket_name,
                        minio_key,
                        ExtraArgs={"ContentType": "image/tiff"},
                    )
                except Exception as e:
                    logger.warning(
                        "MinIO upload failed for %s/%d: %s", code, year, e
                    )
                    continue

                storage_path = f"s3://{bucket_name}/{minio_key}"

                # Register in sentinel_composites table
                cur.execute(
                    """
                    INSERT INTO sentinel_composites (
                        l2_id, year, band_combo, storage_path, file_size_bytes
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (l2_id, year, band_combo) DO UPDATE SET
                        storage_path = EXCLUDED.storage_path,
                        file_size_bytes = EXCLUDED.file_size_bytes,
                        created_at = NOW()
                    """,
                    (l2_id, year, "RGB", storage_path, file_size),
                )
                uploaded += 1

            conn.commit()
            logger.info(
                "Uploaded %d composites to MinIO bucket '%s'",
                uploaded,
                bucket_name,
            )
        finally:
            cur.close()
            conn.close()
