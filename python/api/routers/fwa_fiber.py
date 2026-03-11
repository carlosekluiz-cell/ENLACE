"""FWA vs Fiber Calculator Router."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import fwa_fiber

router = APIRouter(prefix="/api/v1/fwa-fiber", tags=["fwa-fiber"])


class CompareRequest(BaseModel):
    l2_id: int = Field(..., description="Municipality ID")
    target_subscribers: Optional[int] = Field(None, ge=1, description="Target subscriber count")
    area_km2: Optional[float] = Field(None, gt=0, description="Override area in km2")


@router.post("/compare")
async def compare(
    request: CompareRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Compare FWA vs Fiber deployment costs."""
    return await fwa_fiber.compare_technologies(
        db, l2_id=request.l2_id,
        target_subscribers=request.target_subscribers,
        area_km2=request.area_km2,
    )


@router.get("/presets")
async def get_presets(user: dict = Depends(require_auth)):
    """Get preset scenarios for the calculator."""
    return fwa_fiber.get_presets()
