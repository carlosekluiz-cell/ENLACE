"""
ENLACE Rural Connectivity Router

Endpoints for hybrid network design, solar power sizing, funding program
matching, community demand profiling, and river crossing design for
underserved rural areas in Brazil.
"""

import asyncio
import dataclasses
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from python.api.auth.dependencies import require_auth

from python.rural.hybrid_designer import (
    CommunityProfile,
    design_hybrid_network,
)
from python.rural.solar_power import size_solar_system
from python.rural.funding_matcher import (
    match_funding,
    get_all_programs,
)
from python.rural.community_profiler import profile_community
from python.rural.river_crossing import design_crossing

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/rural", tags=["rural"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dataclass_to_dict(obj):
    """Recursively convert a dataclass instance to a plain dict."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = _dataclass_to_dict(value)
        return result
    if isinstance(obj, list):
        return [_dataclass_to_dict(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class HybridDesignRequest(BaseModel):
    """Request body for hybrid network design."""
    community_lat: float = Field(..., description="Community center latitude")
    community_lon: float = Field(..., description="Community center longitude")
    population: int = Field(..., ge=0, description="Total population")
    area_km2: float = Field(..., gt=0, description="Community area in km^2")
    grid_power: bool = Field(False, description="Grid electricity available")
    terrain_type: str = Field("flat", description="Terrain: flat, hilly, mountainous, riverine, island")
    biome: str = Field("cerrado", description="Biome: amazonia, cerrado, caatinga, mata_atlantica, pampa, pantanal")


class FundingMatchRequest(BaseModel):
    """Request body for funding program matching."""
    municipality_code: str = Field(..., description="IBGE municipality code")
    municipality_population: int = Field(..., ge=0, description="Municipality population")
    state_code: str = Field(..., min_length=2, max_length=2, description="Two-letter state code")
    technology: str = Field(..., description="Deployment technology (e.g. 4g_700mhz, fiber)")
    capex_brl: float = Field(..., ge=0, description="Estimated CAPEX in BRL")
    latitude: Optional[float] = Field(None, description="Latitude for geographic checks")
    longitude: Optional[float] = Field(None, description="Longitude for geographic checks")


class CommunityProfileRequest(BaseModel):
    """Request body for community demand profiling."""
    population: int = Field(..., ge=0, description="Community population")
    avg_income_brl: float = Field(1200, ge=0, description="Average monthly household income (BRL)")
    has_school: bool = Field(True, description="Community has a school")
    has_health_unit: bool = Field(True, description="Community has a health unit")
    agricultural: bool = Field(True, description="Community is primarily agricultural")


class RiverCrossingRequest(BaseModel):
    """Request body for river crossing design."""
    width_m: float = Field(..., gt=0, description="River width in meters")
    depth_m: float = Field(10.0, ge=0, description="Average depth in meters")
    current_speed_ms: float = Field(1.5, ge=0, description="Current speed in m/s")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/design")
async def hybrid_design(
    request: HybridDesignRequest,
    user: dict = Depends(require_auth),
):
    """Generate a complete hybrid network design for a rural community.

    Selects optimal backhaul, last mile, and power technologies based on
    community characteristics (location, population, terrain, biome).
    Returns a full design with equipment list, CAPEX, and OPEX estimates.
    """
    loop = asyncio.get_event_loop()

    def _run():
        profile = CommunityProfile(
            latitude=request.community_lat,
            longitude=request.community_lon,
            population=request.population,
            area_km2=request.area_km2,
            grid_power=request.grid_power,
            terrain_type=request.terrain_type,
            biome=request.biome,
        )
        return design_hybrid_network(profile)

    try:
        result = await loop.run_in_executor(None, _run)
        return _dataclass_to_dict(result)
    except ValueError as e:
        logger.warning("Hybrid design validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid design parameters")
    except Exception as e:
        logger.error("Hybrid design failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/solar")
async def solar_design(
    lat: float = Query(..., description="Site latitude"),
    lon: float = Query(..., description="Site longitude"),
    power_watts: float = Query(..., gt=0, description="Power consumption in watts"),
    autonomy_days: int = Query(3, ge=1, le=30, description="Days of battery autonomy"),
    battery_type: str = Query("lithium", description="Battery type: lithium or lead_acid"),
    user: dict = Depends(require_auth),
):
    """Size a solar power system for an off-grid telecom site.

    Uses regional solar irradiance data for Brazil to calculate panel array,
    battery bank, charge controller, and inverter sizing with cost estimates.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return size_solar_system(
            latitude=lat,
            longitude=lon,
            power_consumption_watts=power_watts,
            autonomy_days=autonomy_days,
            battery_type=battery_type,
        )

    try:
        result = await loop.run_in_executor(None, _run)
        return _dataclass_to_dict(result)
    except ValueError as e:
        logger.warning("Solar design validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid solar design parameters")
    except Exception as e:
        logger.error("Solar design failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/funding/match")
async def funding_match(
    request: FundingMatchRequest,
    user: dict = Depends(require_auth),
):
    """Match a rural deployment to available government funding programs.

    Evaluates all tracked Brazilian federal programs (FUST, Norte Conectado,
    New PAC, 5G Obligations, WiFi Brasil, BNDES ProConectividade) and returns
    matches sorted by eligibility score.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return match_funding(
            municipality_code=request.municipality_code,
            municipality_population=request.municipality_population,
            state_code=request.state_code,
            technology=request.technology,
            capex_brl=request.capex_brl,
            latitude=request.latitude,
            longitude=request.longitude,
        )

    try:
        result = await loop.run_in_executor(None, _run)
        return [_dataclass_to_dict(m) for m in result]
    except Exception as e:
        logger.error("Funding match failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/funding/programs")
async def list_funding_programs(
    user: dict = Depends(require_auth),
):
    """List all tracked government funding programs for rural telecom.

    Returns details on FUST, Norte Conectado, New PAC, 5G Obligations,
    WiFi Brasil, and BNDES ProConectividade including eligibility criteria,
    funding amounts, and application URLs.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return get_all_programs()

    try:
        result = await loop.run_in_executor(None, _run)
        return [_dataclass_to_dict(p) for p in result]
    except Exception as e:
        logger.error("Listing funding programs failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/community/profile")
async def community_profile(
    request: CommunityProfileRequest,
    user: dict = Depends(require_auth),
):
    """Profile a rural community's connectivity demand.

    Estimates subscriber count, bandwidth requirements, primary use cases,
    revenue potential, and willingness to pay based on population,
    income, and local infrastructure.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return profile_community(
            population=request.population,
            avg_income_brl=request.avg_income_brl,
            has_school=request.has_school,
            has_health_unit=request.has_health_unit,
            agricultural=request.agricultural,
        )

    try:
        result = await loop.run_in_executor(None, _run)
        return _dataclass_to_dict(result)
    except Exception as e:
        logger.error("Community profiling failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/crossing")
async def river_crossing(
    request: RiverCrossingRequest,
    user: dict = Depends(require_auth),
):
    """Design river crossing options for telecom infrastructure.

    Evaluates aerial cable, submarine cable, and microwave link options
    for crossing Amazon basin rivers. Returns feasible options sorted
    by estimated cost.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return design_crossing(
            width_m=request.width_m,
            depth_m=request.depth_m,
            current_speed_ms=request.current_speed_ms,
        )

    try:
        result = await loop.run_in_executor(None, _run)
        return [_dataclass_to_dict(c) for c in result]
    except ValueError as e:
        logger.warning("River crossing validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid crossing parameters")
    except Exception as e:
        logger.error("River crossing design failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")
