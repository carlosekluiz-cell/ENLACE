"""
ENLACE Design Router — Network Design endpoints.

RF Coverage & Link Budget endpoints proxy to the Rust RF Engine gRPC service.
FTTH Design and Viability endpoints use pure-Python services (no Rust needed).
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
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
