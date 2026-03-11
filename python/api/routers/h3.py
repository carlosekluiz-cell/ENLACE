"""
ENLACE H3 Hexagonal Grid Router

Endpoints for querying, computing, and analyzing H3 hexagonal grids.
Uses the PostgreSQL h3 extension for spatial operations and aggregates
telecom data (subscribers, towers, population) per hexagonal cell.
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.h3_service import (
    get_h3_cells,
    compute_municipality_h3,
    get_municipality_h3_analysis,
)

router = APIRouter(prefix="/api/v1/h3", tags=["h3"])


@router.get("/cells")
async def h3_cells(
    bbox: str = Query(
        ...,
        description="Bounding box as 'west,south,east,north' (lng,lat,lng,lat)",
    ),
    resolution: int = Query(
        7, ge=4, le=10, description="H3 resolution (4-10). Default 7"
    ),
    metric: str = Query(
        "subscribers",
        description=(
            "Metric to include per cell. Options: subscribers, tower_count, "
            "building_count, building_area_m2, population_estimate, "
            "penetration_pct, growth_pct_12m, avg_download_mbps"
        ),
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Return H3 cells within a bounding box as a GeoJSON FeatureCollection.

    Each feature is a hexagonal polygon with the requested metric value
    and contextual properties (subscribers, towers, population, penetration).

    Results are limited to 5,000 cells per request. Use a smaller bounding
    box or a lower resolution for large areas.
    """
    try:
        return await get_h3_cells(
            db=db,
            bbox=bbox,
            resolution=resolution,
            metric=metric,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{municipality_id}/analysis")
async def h3_municipality_analysis(
    municipality_id: int,
    resolution: int = Query(
        7, ge=4, le=10, description="H3 resolution (4-10). Default 7"
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Retrieve pre-computed H3 analysis for a municipality.

    Returns a GeoJSON FeatureCollection of all H3 cells within the
    municipality boundary along with aggregate statistics (total
    subscribers, towers, population, coverage ratio).

    If no cells have been computed yet, returns a 404 with instructions
    to trigger computation via the POST endpoint.
    """
    try:
        return await get_municipality_h3_analysis(
            db=db,
            municipality_id=municipality_id,
            resolution=resolution,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        if "no h3 cells found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)


@router.post("/{municipality_id}/compute")
async def h3_compute_municipality(
    municipality_id: int,
    resolution: int = Query(
        7, ge=4, le=10, description="H3 resolution (4-10). Default 7"
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Trigger H3 grid computation for a municipality.

    Polyfills the municipality geometry with H3 cells at the requested
    resolution, then aggregates subscriber, tower, and population data
    per hexagonal cell. Results are stored in the h3_cells table.

    This operation is idempotent: re-running it updates existing cells
    with fresh data.

    Returns computation summary with cell count and aggregate stats.
    """
    try:
        result = await compute_municipality_h3(
            db=db,
            municipality_id=municipality_id,
            resolution=resolution,
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg.lower():
            raise HTTPException(status_code=404, detail=error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
