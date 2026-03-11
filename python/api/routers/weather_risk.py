"""Weather-Infrastructure Risk Correlation Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import weather_risk

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])


@router.get("/risk")
async def get_weather_risk(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compute weather risk scores for municipalities."""
    return await weather_risk.compute_weather_risk(db, state=state, limit=limit)


@router.get("/risk/{l2_id}")
async def get_risk_detail(
    l2_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get detailed weather risk for a municipality."""
    return await weather_risk.get_risk_detail(db, l2_id=l2_id)


@router.get("/risk/seasonal")
async def get_seasonal_risk(
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get seasonal weather risk patterns."""
    return await weather_risk.seasonal_risk(db, state=state)
