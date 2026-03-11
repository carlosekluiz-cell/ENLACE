"""Spatial Analytics Router — PostGIS advanced spatial analysis."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import spatial_analytics

router = APIRouter(prefix="/api/v1/spatial", tags=["spatial"])


@router.get("/clusters")
async def get_clusters(
    num_clusters: int = Query(10, ge=2, le=50),
    state: Optional[str] = Query(None),
    technology: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Cluster base stations using ST_ClusterKMeans."""
    return await spatial_analytics.cluster_towers(db, num_clusters=num_clusters, state=state, technology=technology)


@router.get("/voronoi")
async def get_voronoi(
    state: Optional[str] = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Generate Voronoi coverage polygons from tower positions."""
    return await spatial_analytics.voronoi_coverage(db, state=state, limit=limit)


@router.get("/footprint/{provider_id}")
async def get_footprint(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute concave hull network footprint for a provider."""
    return await spatial_analytics.provider_footprint(db, provider_id=provider_id)
