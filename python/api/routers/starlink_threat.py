"""Starlink Threat Index Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import starlink_threat

router = APIRouter(prefix="/api/v1/starlink", tags=["starlink"])


@router.get("/threat")
async def get_threat_index(
    state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute Starlink threat index for municipalities."""
    return await starlink_threat.compute_threat_index(db, state=state, limit=limit)


@router.get("/threat/{l2_id}")
async def get_threat_detail(
    l2_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get detailed Starlink threat for a municipality."""
    return await starlink_threat.get_threat_detail(db, l2_id=l2_id)


@router.get("/threat/summary")
async def get_threat_summary(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """National summary of Starlink threat distribution."""
    return await starlink_threat.threat_summary(db)
