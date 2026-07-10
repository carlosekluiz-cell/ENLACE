"""
ENLACE Design Router — Network Design endpoints.

RF Coverage & Link Budget endpoints proxy to the Rust RF Engine gRPC service.
FTTH Design and Viability endpoints use pure-Python services (no Rust needed).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form
from fastapi import File as FastAPIFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.models.schemas import CoverageRequest, DesignJobStatus
from python.api.services.rf_client import RfEngineClient
from python.api.services.ftth_design import (
    calculate_optical_budget,
    design_ftth_network,
)
from python.api.services.fwa_fiber import viability_analysis
from python.api.services import clutter as clutter_svc
from python.api.services import terrain_tiles
from python.api.services.terrain_reader import (
    analyze_link,
    get_landcover_reader,
    get_reader,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/design", tags=["design"])


# ---------------------------------------------------------------------------
# Request models for new endpoints
# ---------------------------------------------------------------------------

class FtthDesignRequest(BaseModel):
    lat: float
    lon: float
    radius_km: float = Field(default=3.0, ge=0.1, le=50)
    subscribers: int = Field(default=1000, ge=10, le=100000)
    technology: str = Field(default="GPON", pattern="^(GPON|XGS-PON)$")
    split_ratio: int = Field(default=32)
    cascade_levels: int = Field(default=2, ge=1, le=2)
    deployment_type: str = Field(default="aerial", pattern="^(aerial|underground|mixed)$")
    l2_id: Optional[int] = None


class OpticalBudgetRequest(BaseModel):
    fiber_km: float = Field(default=5.0, ge=0.1, le=100)
    splices: int = Field(default=3, ge=0, le=100)
    connectors: int = Field(default=4, ge=1, le=50)
    splitter_ratios: list[int] = Field(default=[4, 8])
    technology: str = Field(default="GPON", pattern="^(GPON|XGS-PON)$")


class MeasurementIn(BaseModel):
    lat: float = Field(ge=-35, le=6)
    lon: float = Field(ge=-75, le=-28)
    frequency_mhz: float = Field(gt=30, lt=110000)
    measured_dbm: float = Field(gt=-200, lt=50)
    rx_height_m: float = 1.5
    tx_lat: Optional[float] = None
    tx_lon: Optional[float] = None
    tx_height_m: Optional[float] = None
    tx_power_dbm: Optional[float] = None
    tx_gain_dbi: Optional[float] = None
    source: str = Field(default="manual", max_length=100)
    campaign: Optional[str] = Field(default=None, max_length=200)
    measured_at: Optional[str] = None
    meta: Optional[dict] = None


class MeasurementBatch(BaseModel):
    measurements: list[MeasurementIn] = Field(min_length=1, max_length=10000)


class TerrainEnsureRequest(BaseModel):
    min_lat: float = Field(ge=-35, le=6)
    min_lon: float = Field(ge=-75, le=-28)
    max_lat: float = Field(ge=-35, le=6)
    max_lon: float = Field(ge=-75, le=-28)
    surfaces: list[str] = Field(default=["dtm", "dsm"])


class ViabilityRequest(BaseModel):
    l2_id: int
    technology: str = Field(default="FTTH", pattern="^(FTTH|FWA|Hibrido)$")
    subscribers: int = Field(default=1000, ge=10, le=100000)
    arpu: float = Field(default=89.90, ge=10, le=1000)
    capex_override: Optional[float] = None


def _get_client() -> RfEngineClient:
    """Create and connect an RF Engine client."""
    client = RfEngineClient()
    client.connect()
    return client


def _ensure_terrain(names: list[str], surfaces: tuple[str, ...] = ("dtm",)) -> None:
    """Best-effort tile download so any Brazil coordinate has real terrain.

    Downloads are skipped silently on failure — the RF calls degrade
    gracefully (and are flagged) rather than erroring the whole request.
    """
    store = terrain_tiles.get_tile_store()
    for surface in surfaces:
        try:
            missing = [n for n in names if not store.is_available(n, surface)]
            if missing:
                store.ensure_tiles(missing, surface)
        except Exception as e:
            logger.warning("Terrain ensure (%s) failed: %s", surface, e)


def _infer_environment(lat: float, lon: float, sample_radius_m: float = 500.0) -> str:
    """Classify urban/suburban/rural from MapBiomas pixels around a point.

    Falls back to "rural" when land cover is unavailable.
    """
    try:
        terrain_tiles.get_tile_store().ensure_landcover([terrain_tiles.tile_name(lat, lon)])
        lc = get_landcover_reader()
        dlat = sample_radius_m / 111_320.0
        import math as _math

        dlon = sample_radius_m / (111_320.0 * max(0.1, _math.cos(_math.radians(lat))))
        codes = []
        steps = 7
        for i in range(steps):
            for j in range(steps):
                code = lc.code(
                    lat - dlat + 2 * dlat * i / (steps - 1),
                    lon - dlon + 2 * dlon * j / (steps - 1),
                )
                if code is not None:
                    codes.append(code)
        return clutter_svc.infer_environment(codes)
    except Exception as e:
        logger.warning("Environment inference failed: %s", e)
        return "rural"


@router.post("/coverage")
async def compute_coverage(
    request: CoverageRequest,
    user: dict = Depends(require_auth),
):
    """Compute RF coverage footprint for a tower position.

    Returns a coverage grid with signal strength predictions and
    summary statistics including coverage percentage and area.
    """
    loop = asyncio.get_event_loop()

    def _run():
        _ensure_terrain(
            terrain_tiles.tiles_for_radius(
                request.tower_lat, request.tower_lon, request.radius_m
            )
        )
        environment = request.environment
        if environment == "auto":
            environment = _infer_environment(request.tower_lat, request.tower_lon)
        client = _get_client()
        try:
            result = client.compute_coverage(
                tower_lat=request.tower_lat,
                tower_lon=request.tower_lon,
                tower_height_m=request.tower_height_m,
                frequency_mhz=request.frequency_mhz,
                tx_power_dbm=request.tx_power_dbm,
                antenna_gain_dbi=request.antenna_gain_dbi,
                radius_m=request.radius_m,
                grid_resolution_m=request.grid_resolution_m,
                apply_vegetation=request.apply_vegetation,
                country_code=request.country_code,
                environment=environment,
            )
            result["environment"] = environment
            return result
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
        # Measurement-derived bias correction for this environment, if the
        # calibration benchmark is valid (>=100 residuals, >=30 in group).
        calibration_applied = None
        try:
            from python.api.services import calibration as calibration_svc

            corrections = await loop.run_in_executor(
                None, calibration_svc.get_corrections
            )
            bias = corrections.get(result.get("environment") or "")
            if bias is not None:
                for p in result.get("points", []):
                    key = "signal_strength_dbm" if "signal_strength_dbm" in p else "signal_dbm"
                    if key in p:
                        p[key] += bias
                calibration_applied = {
                    "environment": result.get("environment"),
                    "bias_db": bias,
                }
        except Exception as e:
            logger.warning("Calibration correction skipped: %s", e)

        # Flatten nested response to match frontend CoverageResult type:
        # Frontend expects: {coverage_pct, coverage_area_km2, avg_signal_dbm,
        #                    min_signal_dbm, max_signal_dbm, grid: [{lat, lon, signal_dbm}]}
        stats = result.get("stats", {})
        grid = [
            {
                "lat": p.get("latitude", p.get("lat", 0)),
                "lon": p.get("longitude", p.get("lon", 0)),
                "signal_dbm": p.get("signal_strength_dbm", p.get("signal_dbm", 0)),
            }
            for p in result.get("points", [])
        ]
        if calibration_applied and grid:
            # Corrected signals shift the summary stats too (threshold -95).
            covered = sum(1 for p in grid if p["signal_dbm"] >= -95)
            stats = {
                **stats,
                "coverage_pct": 100.0 * covered / len(grid),
                "avg_signal_dbm": sum(p["signal_dbm"] for p in grid) / len(grid),
                "min_signal_dbm": min(p["signal_dbm"] for p in grid),
                "max_signal_dbm": max(p["signal_dbm"] for p in grid),
            }
        return {
            "coverage_pct": stats.get("coverage_pct", 0),
            "coverage_area_km2": stats.get("covered_area_km2", stats.get("area_km2", 0)),
            "avg_signal_dbm": stats.get("avg_signal_dbm", 0),
            "min_signal_dbm": stats.get("min_signal_dbm", 0),
            "max_signal_dbm": stats.get("max_signal_dbm", 0),
            "coverage_pct_p90": stats.get("coverage_pct_p90"),
            "sigma_db": stats.get("sigma_db"),
            "grid": grid,
            "environment": result.get("environment"),
            "calibration_applied": calibration_applied,
            "_mock": result.get("_mock", False),
        }
    except Exception as e:
        logger.error("Coverage computation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/optimize")
async def optimize_towers(
    request: dict,
    user: dict = Depends(require_auth),
):
    """Run tower placement optimization.

    Accepts parameters for the optimization area and constraints, runs
    the set-cover + simulated annealing pipeline, and returns optimal
    tower placements with CAPEX estimates.

    Request body fields:
    - center_lat, center_lon: center of the coverage area
    - radius_m: radius in meters
    - coverage_target_pct: target coverage percentage (default 95)
    - min_signal_dbm: minimum signal threshold (default -95)
    - max_towers: maximum number of towers (default 20)
    - frequency_mhz: carrier frequency (default 700)
    - tx_power_dbm: transmit power (default 43)
    - antenna_gain_dbi: antenna gain (default 15)
    - antenna_height_m: antenna height (default 30)
    """
    loop = asyncio.get_event_loop()

    def _run():
        _ensure_terrain(
            terrain_tiles.tiles_for_radius(
                request.get("center_lat", 0),
                request.get("center_lon", 0),
                request.get("radius_m", 5000),
            )
        )
        client = _get_client()
        try:
            return client.optimize_towers(
                center_lat=request.get("center_lat", 0),
                center_lon=request.get("center_lon", 0),
                radius_m=request.get("radius_m", 5000),
                coverage_target_pct=request.get("coverage_target_pct", 95),
                min_signal_dbm=request.get("min_signal_dbm", -95),
                max_towers=request.get("max_towers", 20),
                frequency_mhz=request.get("frequency_mhz", 700),
                tx_power_dbm=request.get("tx_power_dbm", 43),
                antenna_gain_dbi=request.get("antenna_gain_dbi", 15),
                antenna_height_m=request.get("antenna_height_m", 30),
            )
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
        return result
    except Exception as e:
        logger.error("Tower optimization failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/linkbudget")
async def link_budget(
    request: dict,
    user: dict = Depends(require_auth),
):
    """Calculate microwave link budget using ITU-R P.530 model.

    Request body fields:
    - frequency_ghz: carrier frequency in GHz
    - distance_km: path distance in km
    - tx_power_dbm: transmitter output power
    - tx_antenna_gain_dbi: TX antenna gain
    - rx_antenna_gain_dbi: RX antenna gain
    - rx_threshold_dbm: receiver sensitivity (default -70)
    - rain_rate_mmh: rain rate in mm/h; if omitted and mid_lat/mid_lon are
      given, resolved from the ITU-R P.837-7 grid (falls back to 145)
    - mid_lat, mid_lon: path midpoint for the P.837 rain lookup
    """
    loop = asyncio.get_event_loop()

    def _run():
        rain_mmh = request.get("rain_rate_mmh")
        rain_source = "request"
        if rain_mmh is None:
            mid_lat, mid_lon = request.get("mid_lat"), request.get("mid_lon")
            if mid_lat is not None and mid_lon is not None:
                from python.api.services.rain import rain_rate_p837

                rain_mmh = rain_rate_p837(mid_lat, mid_lon)
                rain_source = "itu_p837"
            if rain_mmh is None:
                rain_mmh = 145
                rain_source = "default"
        client = _get_client()
        try:
            result = client.link_budget(
                frequency_ghz=request.get("frequency_ghz", 18),
                distance_km=request.get("distance_km", 10),
                tx_power_dbm=request.get("tx_power_dbm", 20),
                tx_antenna_gain_dbi=request.get("tx_antenna_gain_dbi", 38),
                rx_antenna_gain_dbi=request.get("rx_antenna_gain_dbi", 38),
                rx_threshold_dbm=request.get("rx_threshold_dbm", -70),
                rain_rate_mmh=rain_mmh,
            )
            result["rain_rate_mmh"] = rain_mmh
            result["rain_rate_source"] = rain_source
            # Indoor terminal: add ITU-R P.2109 building entry loss
            if request.get("rx_indoor"):
                from python.api.services.bel import building_entry_loss_db

                bel_db = building_entry_loss_db(
                    frequency_ghz=request.get("frequency_ghz", 18),
                    probability=request.get("bel_probability", 0.5),
                    building_class=request.get("building_class", "traditional"),
                )
                result["building_entry_loss_db"] = round(bel_db, 1)
                result["received_power_indoor_dbm"] = round(
                    result["received_power_dbm"] - bel_db, 2
                )
                result["fade_margin_indoor_db"] = round(
                    result["fade_margin_db"] - bel_db, 2
                )
            return result
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
        return result
    except Exception as e:
        logger.error("Link budget calculation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/profile")
async def terrain_profile(
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    step_m: float = 30,
    surface: str = "dtm",
    tx_height_m: Optional[float] = None,
    rx_height_m: Optional[float] = None,
    frequency_mhz: Optional[float] = None,
    clutter: bool = True,
    buildings: bool = False,
    user: dict = Depends(require_auth),
):
    """Extract terrain elevation profile between two geographic points.

    Works for any coordinates inside Brazil — missing 30 m tiles are
    downloaded on demand (SRTM GL1 for dtm, Copernicus GLO-30 for dsm).

    Query parameters:
    - start_lat, start_lon: starting point coordinates
    - end_lat, end_lon: ending point coordinates
    - step_m: sample spacing in meters (default 30)
    - surface: "dtm" (bare earth, default) or "dsm" (includes buildings/vegetation)
    - tx_height_m, rx_height_m, frequency_mhz: if all given, a Fresnel-zone
      link analysis is included as `link_analysis`
    - clutter: annotate each point with MapBiomas land cover and add a
      path clutter summary (composition, vegetation depth, environment)
    - buildings: sample Open Buildings 2.5D heights at urban points and
      analyze the link against rooftops (best paired with surface=ground)
    """
    if surface not in terrain_tiles.SURFACES:
        raise HTTPException(status_code=400, detail="surface must be dtm or dsm")
    path_tiles = terrain_tiles.tiles_for_path(start_lat, start_lon, end_lat, end_lon)
    if len(path_tiles) > terrain_tiles.MAX_TILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Enlace muito longo: cruza {len(path_tiles)} tiles de terreno "
                f"(máx {terrain_tiles.MAX_TILES_PER_REQUEST}). Reduza a distância."
            ),
        )
    loop = asyncio.get_event_loop()

    def _run():
        _ensure_terrain(path_tiles, surfaces=(surface,))
        if clutter:
            try:
                terrain_tiles.get_tile_store().ensure_landcover(path_tiles)
            except Exception as e:
                logger.warning("Landcover ensure failed: %s", e)
        client = _get_client()
        try:
            return client.terrain_profile(
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon,
                step_m=step_m,
                surface=surface,
            )
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
        if clutter and result.get("points"):
            # Annotate per-point land cover (points carry lat/lon whether the
            # profile came from the Rust engine or the local reader).
            def _annotate():
                lc = get_landcover_reader()
                codes = []
                for p in result["points"]:
                    code = p.get("lc")
                    if code is None or code == -1:
                        code = lc.code(p["latitude"], p["longitude"])
                        p["lc"] = -1 if code is None else code
                    if p["lc"] >= 0:
                        codes.append(p["lc"])
                        p["clutter"] = clutter_svc.classify(p["lc"]).key
                actual_step = (
                    result["total_distance_m"] / max(1, len(result["points"]) - 1)
                )
                return clutter_svc.summarize_path(codes, actual_step)

            result["clutter_summary"] = await loop.run_in_executor(None, _annotate)
        if buildings and result.get("points"):
            # Rooftop heights (Open Buildings 2.5D) — only at urban points,
            # which is where the 0.5 m data adds signal over the 30 m DSM.
            def _annotate_buildings():
                from python.api.services.buildings import get_buildings_reader

                reader = get_buildings_reader()
                sampled = 0
                for p in result["points"]:
                    if p.get("clutter") == "urban" or not clutter:
                        bh = reader.height_at(p["latitude"], p["longitude"])
                        if bh is not None:
                            p["building_height_m"] = round(bh, 1)
                            sampled += 1
                return sampled

            try:
                result["buildings_sampled"] = await loop.run_in_executor(
                    None, _annotate_buildings
                )
            except Exception as e:
                logger.warning("Building annotation failed: %s", e)
        if (
            tx_height_m is not None
            and rx_height_m is not None
            and frequency_mhz is not None
            and result.get("points")
        ):
            result["link_analysis"] = analyze_link(
                result,
                tx_height_m,
                rx_height_m,
                frequency_mhz,
                use_buildings=buildings,
            )
        return result
    except Exception as e:
        logger.error("Terrain profile extraction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/elevation")
async def elevation(
    lat: float,
    lon: float,
    user: dict = Depends(require_auth),
):
    """Point elevation for any coordinate in Brazil: bare earth (DTM),
    surface (DSM), and derived clutter height (DSM − DTM)."""
    if not terrain_tiles.in_brazil(lat, lon):
        raise HTTPException(status_code=400, detail="Coordinate outside Brazil coverage")
    loop = asyncio.get_event_loop()

    def _run():
        name = terrain_tiles.tile_name(lat, lon)
        _ensure_terrain([name], surfaces=("dtm", "dsm", "ground"))
        try:
            terrain_tiles.get_tile_store().ensure_landcover([name])
        except Exception as e:
            logger.warning("Landcover ensure failed: %s", e)
        dtm = get_reader("dtm").elevation(lat, lon)
        dsm = get_reader("dsm").elevation(lat, lon)
        ground = get_reader("ground").elevation(lat, lon)
        clutter_h = (
            round(max(0.0, dsm - dtm), 1) if dtm is not None and dsm is not None else None
        )
        # Surface height above true bare earth (buildings + canopy)
        surface_h = (
            round(max(0.0, dsm - ground), 1)
            if dsm is not None and ground is not None
            else None
        )
        building_h = None
        try:
            from python.api.services.buildings import get_buildings_reader

            building_h = get_buildings_reader().height_at(lat, lon)
        except Exception as e:
            logger.warning("Open Buildings lookup failed: %s", e)
        lc_code = get_landcover_reader().code(lat, lon)
        landcover = None
        if lc_code is not None:
            cc = clutter_svc.classify(lc_code)
            landcover = {
                "code": lc_code,
                "name_pt": clutter_svc.class_name_pt(lc_code),
                "clutter": cc.key,
                "clutter_label_pt": cc.label_pt,
                "typical_height_m": cc.height_m,
            }
        return {
            "lat": lat,
            "lon": lon,
            "tile": name,
            "elevation_dtm_m": round(dtm, 1) if dtm is not None else None,
            "elevation_dsm_m": round(dsm, 1) if dsm is not None else None,
            "elevation_ground_m": round(ground, 1) if ground is not None else None,
            "clutter_height_m": clutter_h,
            "surface_height_m": surface_h,
            "building_height_m": round(building_h, 1) if building_h is not None else None,
            "landcover": landcover,
            "resolution_m": 30,
            "sources": {
                "dtm": "SRTM GL1 (OpenTopography)",
                "dsm": "Copernicus GLO-30 (ESA/AWS Open Data)",
                "ground": "ANADEM v1 bare-earth (OpenTopography)",
                "landcover": "MapBiomas Collection 9 (2023)",
                "buildings": "Google Open Buildings 2.5D (2023, 0.5 m)",
            },
        }

    try:
        return await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Elevation lookup failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/terrain/status")
async def terrain_status(user: dict = Depends(require_auth)):
    """Local terrain tile cache inventory (both surfaces)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, terrain_tiles.get_tile_store().status
    )


@router.post("/terrain/ensure")
async def terrain_ensure(
    request: TerrainEnsureRequest,
    user: dict = Depends(require_auth),
):
    """Prefetch terrain tiles for a bbox (max 25 one-degree tiles per call).

    Use before batch coverage runs so RF computations never wait on
    downloads. Ocean areas are recorded and skipped on later calls.
    """
    loop = asyncio.get_event_loop()

    def _run():
        store = terrain_tiles.get_tile_store()
        out = []
        for surface in request.surfaces:
            results = store.ensure_for_bbox(
                request.min_lat,
                request.min_lon,
                request.max_lat,
                request.max_lon,
                surface=surface,
            )
            out.extend(
                {
                    "tile": r.tile,
                    "surface": r.surface,
                    "status": r.status,
                    "detail": r.detail,
                }
                for r in results
            )
        return {"tiles": out}

    try:
        return await loop.run_in_executor(None, _run)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Terrain ensure failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Calibration: measurements -> residuals -> published benchmark
# ---------------------------------------------------------------------------

@router.post("/calibration/measurements")
async def ingest_measurements(
    batch: MeasurementBatch,
    user: dict = Depends(require_auth),
):
    """Ingest RF measurements (fleet telemetry, Anatel campaigns, SIMET,
    drive tests). Measurements with TX parameters become residuals via
    POST /calibration/run."""
    from python.api.services import calibration

    loop = asyncio.get_event_loop()

    def _run():
        return calibration.record_measurements(
            [calibration.Measurement(**m.model_dump()) for m in batch.measurements]
        )

    try:
        stored = await loop.run_in_executor(None, _run)
        return {"stored": stored}
    except Exception as e:
        logger.error("Measurement ingest failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/calibration/run")
async def run_calibration(
    limit: int = 500,
    user: dict = Depends(require_auth),
):
    """Score un-scored measurements against the propagation engine and
    store prediction residuals."""
    from python.api.services import calibration

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(
            None, lambda: calibration.compute_residuals(limit=min(limit, 2000))
        )
    except Exception as e:
        logger.error("Calibration run failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/calibration/status")
async def calibration_status(user: dict = Depends(require_auth)):
    """Accuracy benchmark: residual bias/σ/RMSE overall and per
    environment, clutter class, and model. `benchmark_valid` is false
    until ≥100 residuals exist — no claims without data."""
    from python.api.services import calibration

    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, calibration.calibration_summary)
    except Exception as e:
        logger.error("Calibration status failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# ---------------------------------------------------------------------------
# Browser upload for measurement CSVs (token-gated, exposed via nginx at
# https://api.enlace.network/calibration/upload-ui — only these two routes
# are proxied publicly; everything else stays behind auth)
# ---------------------------------------------------------------------------

_UPLOAD_PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Enlace — Upload de Medições RF</title>
<style>
 body{font-family:system-ui,sans-serif;background:#0b1220;color:#e2e8f0;
      display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
 .card{background:#111a2e;border:1px solid #24334f;border-radius:12px;
       padding:32px;max-width:520px;width:92%}
 h1{font-size:18px;margin:0 0 4px} p{color:#94a3b8;font-size:13px;line-height:1.5}
 input[type=file]{margin:16px 0;width:100%;color:#94a3b8}
 button{background:#0f766e;color:#fff;border:0;border-radius:8px;
        padding:10px 18px;font-size:14px;cursor:pointer}
 button:disabled{opacity:.5}
 pre{background:#0b1220;border:1px solid #24334f;border-radius:8px;
     padding:12px;font-size:12px;white-space:pre-wrap;max-height:300px;overflow:auto}
</style></head><body><div class="card">
<h1>Upload de Medições — Calibração RF</h1>
<p>Arquivos da Anatel (medições de campos eletromagnéticos / mapa de exposição)
ou drive test — CSV, TXT, ZIP ou ODT com tabela. Processado na hora: medições
viram resíduos contra o motor de propagação e alimentam o benchmark.</p>
<form id="f">
  <input type="file" name="file" accept=".csv,.txt,.zip,.odt" multiple required>
  <input type="hidden" name="campaign" value="">
  <button type="submit">Enviar e processar</button>
</form>
<pre id="out" hidden></pre>
<script>
const f=document.getElementById('f'),out=document.getElementById('out');
const token=new URLSearchParams(location.search).get('token')||'';
f.addEventListener('submit',async e=>{
  e.preventDefault();
  const btn=f.querySelector('button');btn.disabled=true;
  const files=f.querySelector('input[type=file]').files;
  btn.textContent='Processando '+files.length+' arquivo(s)…';
  out.hidden=false;out.textContent='Enviando…';
  try{
    const fd=new FormData();
    for(const file of files) fd.append('file',file);
    fd.append('campaign',f.querySelector('input[name=campaign]').value);
    const r=await fetch('upload?token='+encodeURIComponent(token),{method:'POST',body:fd});
    const j=await r.json();
    out.textContent=JSON.stringify(j,null,2);
  }catch(err){out.textContent='Erro: '+err}
  btn.disabled=false;btn.textContent='Enviar e processar';
});
</script></div></body></html>"""


def _upload_token_ok(token: str) -> bool:
    import os as _os

    expected = _os.getenv("CALIBRATION_UPLOAD_TOKEN", "")
    return bool(expected) and token == expected


@router.get("/calibration/upload-ui")
async def calibration_upload_ui(token: str = ""):
    """Minimal public upload page (token in URL; endpoint disabled if no
    CALIBRATION_UPLOAD_TOKEN is configured)."""
    from fastapi.responses import HTMLResponse

    if not _upload_token_ok(token):
        raise HTTPException(status_code=403, detail="token inválido")
    return HTMLResponse(_UPLOAD_PAGE)


@router.post("/calibration/upload")
async def calibration_upload(
    token: str = "",
    file: list[UploadFile] = FastAPIFile(...),
    campaign: str = Form(default=""),
):
    """Receive one or more measurement files (CSV/TXT/ZIP/ODT), parse,
    store, and score residuals. Returns per-file results + the benchmark."""
    import sys as _sys
    import tempfile as _tempfile
    from pathlib import Path as _Path

    if not _upload_token_ok(token):
        raise HTTPException(status_code=403, detail="token inválido")
    if len(file) > 10:
        raise HTTPException(status_code=413, detail="máx. 10 arquivos por envio")

    scripts_dir = str(_Path(__file__).resolve().parents[3] / "scripts")
    if scripts_dir not in _sys.path:
        _sys.path.insert(0, scripts_dir)
    from calibration_ingest import load_anatel_emf

    from python.api.services import calibration

    payloads = []
    for up in file:
        raw = await up.read()
        if len(raw) > 300 * 1024 * 1024:
            raise HTTPException(
                status_code=413, detail=f"{up.filename}: acima de 300 MB"
            )
        payloads.append((up.filename or "upload", raw))

    loop = asyncio.get_event_loop()

    def _extract_tabular(data: bytes, filename: str) -> bytes:
        """Normalize ZIP/ODT payloads to raw delimited text bytes."""
        import io
        import zipfile

        name = (filename or "").lower()
        if name.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                members = [
                    m for m in zf.namelist()
                    if m.lower().endswith((".csv", ".txt")) and not m.endswith("/")
                ]
                if not members:
                    raise ValueError(
                        f"ZIP sem CSV/TXT — conteúdo: {zf.namelist()[:10]}"
                    )
                # Largest member = the data file
                biggest = max(members, key=lambda m: zf.getinfo(m).file_size)
                return zf.read(biggest)
        if name.endswith(".odt"):
            # ODT = zip; tables live in content.xml as table:table-row/cell
            import xml.etree.ElementTree as ET

            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                content = zf.read("content.xml")
            ns_table = "{urn:oasis:names:tc:opendocument:xmlns:table:1.0}"
            root = ET.fromstring(content)
            rows_out = []
            for row in root.iter(f"{ns_table}table-row"):
                cells = []
                for cell in row.iter(f"{ns_table}table-cell"):
                    text = "".join(cell.itertext()).strip()
                    repeat = int(
                        cell.get(f"{ns_table}number-columns-repeated", "1")
                    )
                    cells.extend([text] * min(repeat, 50))
                if any(cells):
                    rows_out.append(";".join(cells))
            if len(rows_out) < 2:
                raise ValueError(
                    "ODT sem tabela de dados — se for só o glossário/metadados, "
                    "envie o arquivo de medições (CSV/TXT)"
                )
            return "\n".join(rows_out).encode("latin-1", errors="replace")
        return data

    def _save_upload(filename: str, raw: bytes) -> None:
        """Persist the raw upload so parsing can be iterated server-side
        without asking for another upload."""
        import re as _re
        import time as _time

        updir = _Path("data/uploads")
        updir.mkdir(parents=True, exist_ok=True)
        safe = _re.sub(r"[^A-Za-z0-9._-]", "_", filename)[:120]
        (updir / f"{int(_time.time())}_{safe}").write_bytes(raw)

    def _process_one(filename: str, raw: bytes) -> dict:
        try:
            _save_upload(filename, raw)
        except Exception as e:
            logger.warning("Could not persist upload %s: %s", filename, e)
        try:
            payload = _extract_tabular(raw, filename)
        except ValueError as e:
            return {"arquivo": filename, "error": str(e)}
        except Exception as e:
            return {"arquivo": filename, "error": f"não consegui abrir: {e}"}
        header_preview = payload[:600].decode("latin-1", errors="replace").splitlines()[:1]
        with _tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(payload)
            tmp_path = tmp.name
        try:
            measurements = load_anatel_emf(tmp_path, campaign or filename)
            if not measurements:
                return {
                    "arquivo": filename,
                    "error": "nenhuma medição válida — colunas não reconhecidas "
                    "(arquivo salvo no servidor para ajuste do parser)",
                    "cabecalho": header_preview,
                }
            stored = calibration.record_measurements(measurements)
            return {"arquivo": filename, "medicoes_armazenadas": stored}
        except SystemExit as e:
            return {"arquivo": filename, "error": str(e)}
        finally:
            import os as _os

            try:
                _os.unlink(tmp_path)
            except OSError:
                pass

    def _process():
        results = [_process_one(name, raw) for name, raw in payloads]
        total = sum(r.get("medicoes_armazenadas", 0) for r in results)
        run = calibration.compute_residuals(limit=2000) if total else {}
        return {
            "arquivos": results,
            "total_medicoes": total,
            "residuos_calculados": run.get("scored"),
            "nao_pontuaveis": run.get("remaining_unscorable"),
            "benchmark": calibration.calibration_summary(),
        }

    try:
        return await loop.run_in_executor(None, _process)
    except Exception as e:
        logger.error("Upload processing failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="falha ao processar arquivos")


# ---------------------------------------------------------------------------
# FTTH & Viability endpoints (pure Python — no Rust engine)
# ---------------------------------------------------------------------------

@router.post("/ftth")
async def ftth_design(
    request: FtthDesignRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Design a complete FTTH network with optical budget, splitter cascade,
    OLT sizing, and itemized BOM."""
    try:
        result = await design_ftth_network(
            db=db,
            lat=request.lat,
            lon=request.lon,
            radius_km=request.radius_km,
            subscribers=request.subscribers,
            technology=request.technology,
            split_ratio=request.split_ratio,
            cascade_levels=request.cascade_levels,
            deployment_type=request.deployment_type,
            l2_id=request.l2_id,
        )
        return result
    except Exception as e:
        logger.error("FTTH design failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optical-budget")
async def optical_budget(
    request: OpticalBudgetRequest,
    user: dict = Depends(require_auth),
):
    """Standalone optical budget calculator — no DB required."""
    try:
        result = calculate_optical_budget(
            fiber_km=request.fiber_km,
            splices=request.splices,
            connectors=request.connectors,
            splitter_ratios=request.splitter_ratios,
            technology=request.technology,
        )
        return result
    except Exception as e:
        logger.error("Optical budget calculation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/viability")
async def viability(
    request: ViabilityRequest,
    user: dict = Depends(require_auth),
    db: AsyncSession = Depends(get_db),
):
    """Economic viability analysis with 3 scenarios (optimistic/realistic/conservative),
    NPV, IRR, payback, and market context."""
    try:
        result = await viability_analysis(
            db=db,
            l2_id=request.l2_id,
            technology=request.technology,
            subscribers=request.subscribers,
            arpu=request.arpu,
            capex_override=request.capex_override,
        )
        return result
    except Exception as e:
        logger.error("Viability analysis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
