"""
ENLACE Design Router — RF Coverage, Optimization, and Link Budget endpoints.

These endpoints proxy requests to the Rust RF Engine gRPC service.
If the RF Engine is unavailable, mock responses are returned with a warning.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from python.api.auth.dependencies import require_auth
from python.api.models.schemas import CoverageRequest, DesignJobStatus
from python.api.services.rf_client import RfEngineClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/design", tags=["design"])


def _get_client() -> RfEngineClient:
    """Create and connect an RF Engine client."""
    client = RfEngineClient()
    client.connect()
    return client


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
        client = _get_client()
        try:
            return client.compute_coverage(
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
            )
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
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
        return {
            "coverage_pct": stats.get("coverage_pct", 0),
            "coverage_area_km2": stats.get("covered_area_km2", stats.get("area_km2", 0)),
            "avg_signal_dbm": stats.get("avg_signal_dbm", 0),
            "min_signal_dbm": stats.get("min_signal_dbm", 0),
            "max_signal_dbm": stats.get("max_signal_dbm", 0),
            "grid": grid,
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
    - rain_rate_mmh: rain rate in mm/h (default 145 for Brazil)
    """
    loop = asyncio.get_event_loop()

    def _run():
        client = _get_client()
        try:
            return client.link_budget(
                frequency_ghz=request.get("frequency_ghz", 18),
                distance_km=request.get("distance_km", 10),
                tx_power_dbm=request.get("tx_power_dbm", 20),
                tx_antenna_gain_dbi=request.get("tx_antenna_gain_dbi", 38),
                rx_antenna_gain_dbi=request.get("rx_antenna_gain_dbi", 38),
                rx_threshold_dbm=request.get("rx_threshold_dbm", -70),
                rain_rate_mmh=request.get("rain_rate_mmh", 145),
            )
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
    user: dict = Depends(require_auth),
):
    """Extract terrain elevation profile between two geographic points.

    Query parameters:
    - start_lat, start_lon: starting point coordinates
    - end_lat, end_lon: ending point coordinates
    - step_m: sample spacing in meters (default 30)
    """
    loop = asyncio.get_event_loop()

    def _run():
        client = _get_client()
        try:
            return client.terrain_profile(
                start_lat=start_lat,
                start_lon=start_lon,
                end_lat=end_lat,
                end_lon=end_lon,
                step_m=step_m,
            )
        finally:
            client.close()

    try:
        result = await loop.run_in_executor(None, _run)
        return result
    except Exception as e:
        logger.error("Terrain profile extraction failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
