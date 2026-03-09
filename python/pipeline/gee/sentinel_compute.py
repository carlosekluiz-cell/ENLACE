"""Google Earth Engine Sentinel-2 computation for municipality-level urban indices.

Authenticates with GEE via service account, computes annual median Sentinel-2
composites per municipality, calculates spectral indices (NDVI, NDBI, MNDWI, BSI),
classifies built-up pixels, reduces to municipality-level stats, and exports
results to Google Cloud Storage as CSV stats and Cloud-Optimized GeoTIFF composites.

Environment variables:
    GEE_SERVICE_ACCOUNT_KEY: Path to GEE service account JSON key file.
    GEE_EXPORT_BUCKET: GCS bucket for exports (default: "enlace-sentinel").
    GEE_PROJECT: GEE project ID (default: "enlace-platform").

Sentinel-2 bands used:
    B2 (Blue), B3 (Green), B4 (Red), B8 (NIR), B11 (SWIR1), B12 (SWIR2),
    SCL (Scene Classification Layer) for cloud masking.

Index formulas:
    NDVI  = (B8 - B4)  / (B8 + B4)
    NDBI  = (B11 - B8) / (B11 + B8)
    MNDWI = (B3 - B11) / (B3 + B11)
    BSI   = ((B11 + B4) - (B8 + B2)) / ((B11 + B4) + (B8 + B2))
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import ee

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEE_SERVICE_ACCOUNT_KEY = os.getenv("GEE_SERVICE_ACCOUNT_KEY", "")
GEE_EXPORT_BUCKET = os.getenv("GEE_EXPORT_BUCKET", "enlace-sentinel")
GEE_PROJECT = os.getenv("GEE_PROJECT", "enlace-platform")

# Sentinel-2 Surface Reflectance collection
S2_SR_COLLECTION = "COPERNICUS/S2_SR_HARMONIZED"

# Bands to select from the Sentinel-2 collection
S2_BANDS = ["B2", "B3", "B4", "B8", "B11", "B12", "SCL"]

# Scene Classification Layer (SCL) values to mask as cloud/shadow:
#   3  = Cloud Shadow
#   8  = Cloud (medium probability)
#   9  = Cloud (high probability)
#   10 = Thin Cirrus
SCL_MASK_VALUES = [3, 8, 9, 10]

# Pixel size in metres for reductions and exports (Sentinel-2 native 10 m
# bands are used, but 10 m over large areas is expensive; 30 m is a good
# balance between accuracy and compute budget).
EXPORT_SCALE_METRES = 30

# Default maximum cloud cover percentage for pre-filtering the image collection.
DEFAULT_CLOUD_THRESHOLD = 20

# Pause between task submissions to avoid hitting GEE quota limits.
TASK_SUBMIT_DELAY_SECONDS = 1.0

# Polling interval when waiting for task completion.
TASK_POLL_INTERVAL_SECONDS = 30


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class MunicipalitySpec:
    """Specification for a single municipality computation."""

    code: str            # IBGE municipality code (7-digit string)
    bbox: List[float]    # [min_lon, min_lat, max_lon, max_lat]
    name: str = ""       # Optional human-readable name


@dataclass
class TaskPair:
    """Holds the GEE export tasks for a single municipality/year."""

    municipality_code: str
    year: int
    stats_task: Optional[ee.batch.Task] = None
    rgb_task: Optional[ee.batch.Task] = None

    @property
    def stats_task_id(self) -> Optional[str]:
        return self.stats_task.id if self.stats_task else None

    @property
    def rgb_task_id(self) -> Optional[str]:
        return self.rgb_task.id if self.rgb_task else None


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

_initialised = False


def initialize_gee() -> None:
    """Authenticate and initialise the Earth Engine API.

    Tries service-account authentication first (using the JSON key file
    pointed to by ``GEE_SERVICE_ACCOUNT_KEY``).  Falls back to interactive
    / application-default credentials when no key file is configured.
    """
    global _initialised
    if _initialised:
        logger.debug("GEE already initialised, skipping")
        return

    key_path = GEE_SERVICE_ACCOUNT_KEY
    if key_path and os.path.isfile(key_path):
        logger.info("Authenticating with GEE service account key: %s", key_path)
        with open(key_path, "r") as f:
            key_data = json.load(f)
        service_account = key_data.get("client_email", "")
        credentials = ee.ServiceAccountCredentials(service_account, key_path)
        ee.Initialize(credentials=credentials, project=GEE_PROJECT)
    else:
        logger.info(
            "No service account key found; falling back to interactive / "
            "application-default credentials"
        )
        ee.Authenticate()
        ee.Initialize(project=GEE_PROJECT)

    _initialised = True
    logger.info("Google Earth Engine initialised (project=%s)", GEE_PROJECT)


# ---------------------------------------------------------------------------
# Cloud masking
# ---------------------------------------------------------------------------

def _mask_clouds(image: ee.Image) -> ee.Image:
    """Mask cloud and cloud-shadow pixels using the SCL band.

    Excluded SCL values:
        3  - Cloud Shadow
        8  - Cloud (medium probability)
        9  - Cloud (high probability)
        10 - Thin Cirrus
    """
    scl = image.select("SCL")
    mask = ee.Image.constant(1)
    for scl_value in SCL_MASK_VALUES:
        mask = mask.And(scl.neq(scl_value))
    return image.updateMask(mask)


# ---------------------------------------------------------------------------
# Spectral indices
# ---------------------------------------------------------------------------

def _add_indices(image: ee.Image) -> ee.Image:
    """Compute NDVI, NDBI, MNDWI, and BSI and append as new bands.

    All indices are normalised differences in the range [-1, 1].
    """
    b2 = image.select("B2")   # Blue
    b3 = image.select("B3")   # Green
    b4 = image.select("B4")   # Red
    b8 = image.select("B8")   # NIR
    b11 = image.select("B11") # SWIR1
    # B12 (SWIR2) is retained in the composite but not used in these indices.

    ndvi = b8.subtract(b4).divide(b8.add(b4)).rename("NDVI")
    ndbi = b11.subtract(b8).divide(b11.add(b8)).rename("NDBI")
    mndwi = b3.subtract(b11).divide(b3.add(b11)).rename("MNDWI")

    # Bare Soil Index
    bsi_num = b11.add(b4).subtract(b8.add(b2))
    bsi_den = b11.add(b4).add(b8.add(b2))
    bsi = bsi_num.divide(bsi_den).rename("BSI")

    return image.addBands([ndvi, ndbi, mndwi, bsi])


def _classify_builtup(image: ee.Image) -> ee.Image:
    """Classify built-up pixels: NDBI > 0 AND NDVI < 0.2.

    Adds a binary band ``builtup`` (1 = built-up, 0 = not).
    """
    builtup = (
        image.select("NDBI").gt(0)
        .And(image.select("NDVI").lt(0.2))
        .rename("builtup")
    )
    return image.addBands(builtup)


# ---------------------------------------------------------------------------
# Composite building
# ---------------------------------------------------------------------------

def _build_annual_composite(
    bbox: List[float],
    year: int,
    cloud_threshold: int = DEFAULT_CLOUD_THRESHOLD,
) -> ee.Image:
    """Build a cloud-free annual median composite for a bounding box.

    Steps:
        1. Filter Sentinel-2 SR collection to AOI, date range, cloud cover.
        2. Select required bands.
        3. Apply cloud mask via SCL band.
        4. Compute pixel-wise median.
        5. Calculate spectral indices.
        6. Classify built-up pixels.

    Args:
        bbox: [min_lon, min_lat, max_lon, max_lat].
        year: Calendar year for the composite.
        cloud_threshold: Maximum CLOUDY_PIXEL_PERCENTAGE for pre-filtering.

    Returns:
        ee.Image with bands B2-B12, SCL, NDVI, NDBI, MNDWI, BSI, builtup.
    """
    aoi = ee.Geometry.Rectangle(bbox)

    start_date = f"{year}-01-01"
    end_date = f"{year + 1}-01-01"

    collection = (
        ee.ImageCollection(S2_SR_COLLECTION)
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .select(S2_BANDS)
        .map(_mask_clouds)
    )

    composite = collection.median().clip(aoi)
    composite = _add_indices(composite)
    composite = _classify_builtup(composite)

    return composite


# ---------------------------------------------------------------------------
# Municipality-level reduction
# ---------------------------------------------------------------------------

def _reduce_to_stats(
    composite: ee.Image,
    bbox: List[float],
    municipality_code: str,
    year: int,
) -> ee.Feature:
    """Reduce a composite image to municipality-level statistics.

    Computes:
        - Mean NDVI, NDBI, MNDWI, BSI over the AOI.
        - Total built-up area (pixel count * pixel area).
        - Built-up percentage (built-up pixels / total valid pixels).

    Returns an ``ee.Feature`` (point geometry at AOI centroid) whose
    properties contain the statistics plus metadata.
    """
    aoi = ee.Geometry.Rectangle(bbox)
    scale = EXPORT_SCALE_METRES

    # Mean indices
    mean_indices = composite.select(["NDVI", "NDBI", "MNDWI", "BSI"]).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
    )

    # Built-up pixel count and total valid pixel count
    builtup_band = composite.select("builtup")
    builtup_sum = builtup_band.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
    )
    valid_count = builtup_band.reduceRegion(
        reducer=ee.Reducer.count(),
        geometry=aoi,
        scale=scale,
        maxPixels=1e9,
    )

    # Pixel area in square metres
    pixel_area_m2 = scale * scale

    builtup_pixels = ee.Number(builtup_sum.get("builtup"))
    total_pixels = ee.Number(valid_count.get("builtup"))

    builtup_area_km2 = builtup_pixels.multiply(pixel_area_m2).divide(1e6)
    builtup_pct = builtup_pixels.divide(total_pixels).multiply(100)

    properties = {
        "municipality_code": municipality_code,
        "year": year,
        "ndvi_mean": mean_indices.get("NDVI"),
        "ndbi_mean": mean_indices.get("NDBI"),
        "mndwi_mean": mean_indices.get("MNDWI"),
        "bsi_mean": mean_indices.get("BSI"),
        "builtup_pixels": builtup_pixels,
        "total_pixels": total_pixels,
        "builtup_area_km2": builtup_area_km2,
        "builtup_pct": builtup_pct,
    }

    centroid = aoi.centroid()
    return ee.Feature(centroid, properties)


# ---------------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------------

def _export_stats_to_gcs(
    feature: ee.Feature,
    municipality_code: str,
    year: int,
) -> ee.batch.Task:
    """Export a stats Feature as a CSV to Google Cloud Storage.

    File path: ``gs://{bucket}/stats/{municipality_code}/{year}.csv``
    """
    fc = ee.FeatureCollection([feature])
    description = f"stats_{municipality_code}_{year}"
    file_prefix = f"stats/{municipality_code}/{year}"

    task = ee.batch.Export.table.toCloudStorage(
        collection=fc,
        description=description,
        bucket=GEE_EXPORT_BUCKET,
        fileNamePrefix=file_prefix,
        fileFormat="CSV",
    )
    return task


def _export_rgb_to_gcs(
    composite: ee.Image,
    bbox: List[float],
    municipality_code: str,
    year: int,
) -> ee.batch.Task:
    """Export an RGB (B4, B3, B2) Cloud-Optimized GeoTIFF to GCS.

    Scales the 0-10000 surface reflectance values to 0-255 byte range
    for visualisation.

    File path: ``gs://{bucket}/rgb/{municipality_code}/{year}.tif``
    """
    aoi = ee.Geometry.Rectangle(bbox)

    # Scale surface reflectance (0-10 000) to byte (0-255) and clamp.
    rgb = (
        composite.select(["B4", "B3", "B2"])
        .divide(10000)
        .multiply(255)
        .clamp(0, 255)
        .toUint8()
    )

    description = f"rgb_{municipality_code}_{year}"
    file_prefix = f"rgb/{municipality_code}/{year}"

    task = ee.batch.Export.image.toCloudStorage(
        image=rgb,
        description=description,
        bucket=GEE_EXPORT_BUCKET,
        fileNamePrefix=file_prefix,
        region=aoi,
        scale=EXPORT_SCALE_METRES,
        crs="EPSG:4326",
        maxPixels=1e9,
        fileFormat="GeoTIFF",
        formatOptions={"cloudOptimized": True},
    )
    return task


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_municipality_indices(
    municipality_code: str,
    bbox: List[float],
    year: int,
    cloud_threshold: int = DEFAULT_CLOUD_THRESHOLD,
) -> TaskPair:
    """Submit GEE export tasks for one municipality/year.

    Builds an annual median Sentinel-2 composite, computes spectral indices,
    classifies built-up pixels, reduces to municipality-level stats, and
    exports both a CSV stats file and an RGB Cloud-Optimized GeoTIFF to GCS.

    Args:
        municipality_code: 7-digit IBGE municipality code.
        bbox: Bounding box as [min_lon, min_lat, max_lon, max_lat].
        year: Calendar year for the composite.
        cloud_threshold: Maximum ``CLOUDY_PIXEL_PERCENTAGE`` for image
            pre-filtering (default 20).

    Returns:
        A ``TaskPair`` containing the submitted GEE tasks for stats and RGB
        exports.  Use ``check_task_status`` to poll their progress.
    """
    initialize_gee()

    logger.info(
        "Computing indices for municipality %s, year %d (cloud_threshold=%d)",
        municipality_code,
        year,
        cloud_threshold,
    )

    composite = _build_annual_composite(bbox, year, cloud_threshold)
    stats_feature = _reduce_to_stats(composite, bbox, municipality_code, year)

    # Submit export tasks
    stats_task = _export_stats_to_gcs(stats_feature, municipality_code, year)
    stats_task.start()
    logger.info(
        "Submitted stats export task %s for %s/%d",
        stats_task.id,
        municipality_code,
        year,
    )

    rgb_task = _export_rgb_to_gcs(composite, bbox, municipality_code, year)
    rgb_task.start()
    logger.info(
        "Submitted RGB export task %s for %s/%d",
        rgb_task.id,
        municipality_code,
        year,
    )

    return TaskPair(
        municipality_code=municipality_code,
        year=year,
        stats_task=stats_task,
        rgb_task=rgb_task,
    )


def check_task_status(task_id: str) -> Dict[str, Any]:
    """Poll the status of a GEE export task.

    Args:
        task_id: The Earth Engine task ID string.

    Returns:
        A dictionary with keys:
            - ``id``: The task ID.
            - ``state``: One of ``READY``, ``RUNNING``, ``COMPLETED``,
              ``FAILED``, ``CANCELLED``, ``CANCEL_REQUESTED``.
            - ``description``: Human-readable task description.
            - ``error_message``: Error message if state is ``FAILED``,
              otherwise ``None``.
    """
    initialize_gee()

    status = ee.data.getTaskStatus(task_id)
    if not status:
        return {
            "id": task_id,
            "state": "UNKNOWN",
            "description": "",
            "error_message": f"No task found with ID {task_id}",
        }

    task_info = status[0] if isinstance(status, list) else status
    return {
        "id": task_info.get("id", task_id),
        "state": task_info.get("state", "UNKNOWN"),
        "description": task_info.get("description", ""),
        "error_message": task_info.get("error_message"),
    }


def batch_compute(
    municipalities: List[MunicipalitySpec],
    years: List[int],
    batch_size: int = 10,
) -> List[TaskPair]:
    """Submit GEE tasks for multiple municipalities across multiple years.

    Tasks are submitted in batches to avoid overloading GEE's quota.  Between
    each task submission a small delay (``TASK_SUBMIT_DELAY_SECONDS``) is
    inserted.

    Args:
        municipalities: List of ``MunicipalitySpec`` objects describing each
            municipality's code and bounding box.
        years: List of calendar years to compute.
        batch_size: Maximum number of task pairs to submit before pausing to
            let existing tasks drain.  When the batch limit is hit, the
            function polls until at least one task in the batch completes
            before continuing.

    Returns:
        A flat list of all submitted ``TaskPair`` objects.
    """
    initialize_gee()

    total_jobs = len(municipalities) * len(years)
    logger.info(
        "Batch compute: %d municipalities x %d years = %d jobs (batch_size=%d)",
        len(municipalities),
        len(years),
        total_jobs,
        batch_size,
    )

    all_task_pairs: List[TaskPair] = []
    pending_in_batch = 0

    for spec in municipalities:
        for year in years:
            # Throttle: if we have hit the batch limit, wait for some tasks
            # to complete before submitting more.
            if pending_in_batch >= batch_size:
                logger.info(
                    "Batch limit reached (%d); waiting for tasks to drain...",
                    batch_size,
                )
                _wait_for_batch_drain(all_task_pairs, batch_size)
                pending_in_batch = 0

            try:
                task_pair = compute_municipality_indices(
                    municipality_code=spec.code,
                    bbox=spec.bbox,
                    year=year,
                )
                all_task_pairs.append(task_pair)
                pending_in_batch += 1
            except Exception:
                logger.exception(
                    "Failed to submit tasks for municipality %s, year %d",
                    spec.code,
                    year,
                )

            time.sleep(TASK_SUBMIT_DELAY_SECONDS)

    logger.info("All %d task pairs submitted", len(all_task_pairs))
    return all_task_pairs


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _wait_for_batch_drain(
    task_pairs: List[TaskPair],
    batch_size: int,
) -> None:
    """Block until fewer than ``batch_size`` tasks are still RUNNING/READY.

    This prevents exceeding GEE's concurrent-task quota.
    """
    while True:
        active = 0
        for tp in task_pairs:
            for tid in (tp.stats_task_id, tp.rgb_task_id):
                if tid is None:
                    continue
                status = check_task_status(tid)
                if status["state"] in ("READY", "RUNNING"):
                    active += 1

        if active < batch_size:
            logger.info("Active tasks: %d (< %d); resuming submissions", active, batch_size)
            return

        logger.debug(
            "Active tasks: %d (>= %d); sleeping %ds",
            active,
            batch_size,
            TASK_POLL_INTERVAL_SECONDS,
        )
        time.sleep(TASK_POLL_INTERVAL_SECONDS)
