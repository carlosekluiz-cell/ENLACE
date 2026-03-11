"""5G Coverage Obligation Tracker Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import coverage_obligations

router = APIRouter(prefix="/api/v1/obligations", tags=["obligations"])


@router.get("/5g")
async def get_5g_obligations(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get all 5G coverage obligations with progress."""
    return await coverage_obligations.get_obligations(db)


@router.get("/5g/{provider_name}")
async def get_provider_obligations(
    provider_name: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get 5G obligations for a specific operator."""
    return await coverage_obligations.get_obligations(db, provider_name=provider_name)


@router.get("/5g/gap-analysis")
async def get_gap_analysis(
    provider_name: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Analyze gaps in 5G coverage obligation fulfillment."""
    return await coverage_obligations.gap_analysis(db, provider_name=provider_name)
