"""RGST 777/2025 Compliance Checker Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import compliance_checker

router = APIRouter(prefix="/api/v1/compliance/rgst777", tags=["compliance"])


@router.get("/{provider_id}")
async def check_provider(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Check RGST 777/2025 compliance for a provider."""
    return await compliance_checker.check_rgst777(db, provider_id=provider_id)


@router.get("/overview")
async def overview(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Overview of RGST 777 compliance across providers."""
    return await compliance_checker.rgst777_overview(db, state=state, limit=limit)
