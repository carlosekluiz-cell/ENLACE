"""
ENLACE Fiber Route Planning Router

Endpoints for pgRouting-based fiber route computation, corridor analysis,
and Bill of Materials generation.  Routes are computed on the 6.4M-segment
OSM road network using pgr_dijkstra.

Requires pgRouting topology to be built on the road_segments table
(source/target columns populated, road_segments_vertices_pgr table present).
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.fiber_routing import (
    compute_corridor,
    compute_route,
    find_nearest_vertex,
    generate_bom,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/fiber", tags=["fiber"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RouteRequest(BaseModel):
    """Request body for fiber route computation."""
    start_lon: float = Field(..., ge=-180, le=180, description="Start longitude (WGS84)")
    start_lat: float = Field(..., ge=-90, le=90, description="Start latitude (WGS84)")
    end_lon: float = Field(..., ge=-180, le=180, description="End longitude (WGS84)")
    end_lat: float = Field(..., ge=-90, le=90, description="End latitude (WGS84)")


class CorridorRequest(BaseModel):
    """Request body for fiber corridor analysis."""
    start_lon: float = Field(..., ge=-180, le=180, description="Start longitude (WGS84)")
    start_lat: float = Field(..., ge=-90, le=90, description="Start latitude (WGS84)")
    end_lon: float = Field(..., ge=-180, le=180, description="End longitude (WGS84)")
    end_lat: float = Field(..., ge=-90, le=90, description="End latitude (WGS84)")
    buffer_m: float = Field(
        1000.0, ge=100, le=10000,
        description="Buffer width in meters around the route (default 1000)",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/route")
async def fiber_route(
    request: RouteRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute the shortest fiber route between two geographic points.

    Uses pgr_dijkstra on the OSM road network to find the least-cost
    path.  Returns the route as a GeoJSON FeatureCollection (one Feature
    per road segment), total distance, and a full Bill of Materials with
    cost estimate.

    The start and end coordinates are snapped to the nearest road network
    vertex before routing.
    """
    try:
        result = await compute_route(
            db,
            start_lon=request.start_lon,
            start_lat=request.start_lat,
            end_lon=request.end_lon,
            end_lat=request.end_lat,
        )
        return result

    except ValueError as e:
        # Topology not built or vertex not found
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Fiber route computation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/corridor")
async def fiber_corridor(
    request: CorridorRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute fiber route with a buffer corridor for right-of-way analysis.

    Same as /route but also returns a corridor polygon (buffered around the
    route geometry) useful for:
    - Right-of-way (ROW) analysis
    - Environmental impact assessment
    - Infrastructure co-location identification (power lines, existing fiber)

    The buffer_m parameter controls the corridor width (default 1000m).
    """
    try:
        result = await compute_corridor(
            db,
            start_lon=request.start_lon,
            start_lat=request.start_lat,
            end_lon=request.end_lon,
            end_lat=request.end_lat,
            buffer_m=request.buffer_m,
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Fiber corridor computation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/bom")
async def fiber_bom(
    distance_m: float = Query(..., gt=0, description="Total route distance in meters"),
    highway_classes: Optional[str] = Query(
        None,
        description=(
            "Comma-separated list of highway classes along the route "
            "(e.g. 'trunk,primary,residential'). Used to determine cable type "
            "proportions. If omitted, all distance is treated as distribution."
        ),
    ),
    user: dict = Depends(require_auth),
):
    """Generate a fiber deployment Bill of Materials.

    Returns an itemized BOM with quantities, unit costs, and total cost
    for a given route distance.  The highway_classes parameter controls
    the cable type breakdown:

    - **Trunk** classes (motorway, trunk): 48-core fiber at R$18,000/km
    - **Distribution** classes (primary, secondary): 12-core fiber at R$8,000/km
    - **Drop/last-mile** classes (tertiary, residential, etc.): 2-core at R$2,500/km

    Additional items include splice closures (every 2km), handholes (every 500m),
    OLT ports, and ONTs.
    """
    classes_list = []
    if highway_classes:
        classes_list = [c.strip() for c in highway_classes.split(",") if c.strip()]

    # If no classes provided, default to distribution-level cable
    if not classes_list:
        classes_list = ["secondary"]

    bom = generate_bom(distance_m, classes_list)
    return bom
