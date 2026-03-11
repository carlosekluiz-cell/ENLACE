"""Backhaul Utilization Model Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import backhaul_model

router = APIRouter(prefix="/api/v1/backhaul", tags=["backhaul"])


@router.get("/utilization")
async def get_utilization(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get backhaul utilization estimates per municipality."""
    return await backhaul_model.get_utilization(db, state=state, limit=limit)


@router.get("/forecast/{l2_id}")
async def get_forecast(
    l2_id: int,
    months_ahead: int = Query(12, ge=1, le=36),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Forecast backhaul utilization for a municipality."""
    return await backhaul_model.forecast_utilization(db, l2_id=l2_id, months_ahead=months_ahead)


@router.get("/congestion-risk")
async def get_congestion_risk(
    months_horizon: int = Query(12, ge=1, le=36),
    state: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Find municipalities at risk of backhaul congestion."""
    return await backhaul_model.congestion_risk(db, months_horizon=months_horizon, state=state)
