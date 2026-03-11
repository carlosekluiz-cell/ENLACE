"""Cross-Reference Analytics Router — 10 endpoints for cross-table analytics."""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services import cross_analytics, social_gaps, investment_priority

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/hhi")
async def get_hhi(
    state: Optional[str] = Query(None),
    year_month: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """HHI competition index from precomputed competitive_analysis."""
    return await cross_analytics.hhi_competition_index(db, state=state, year_month=year_month, limit=limit)


@router.get("/coverage-gaps")
async def get_coverage_gaps(
    state: Optional[str] = Query(None),
    min_population: int = Query(10000, ge=0),
    max_towers_per_1000: float = Query(1.0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Find municipalities with high population but low tower density."""
    return await cross_analytics.coverage_gap_analysis(db, state=state, min_population=min_population, max_towers_per_1000=max_towers_per_1000, limit=limit)


@router.get("/provider-overlap")
async def get_provider_overlap(
    provider_a: int = Query(...),
    provider_b: int = Query(...),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Find municipalities where both providers operate and compare market shares."""
    return await cross_analytics.provider_overlap(db, provider_id_a=provider_a, provider_id_b=provider_b)


@router.get("/tower-density")
async def get_tower_density(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Rank municipalities by tower density (lowest = most underserved)."""
    return await cross_analytics.tower_density_analysis(db, state=state, limit=limit)


@router.get("/weather-correlation")
async def get_weather_correlation(
    state: Optional[str] = Query(None),
    months: int = Query(12, ge=1, le=60),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Correlate weather patterns with network quality metrics."""
    return await cross_analytics.weather_quality_correlation(db, state=state, months=months)


@router.get("/employment-correlation")
async def get_employment_correlation(
    state: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Correlate employment indicators with broadband penetration."""
    return await cross_analytics.employment_broadband_correlation(db, state=state, limit=limit)


@router.get("/school-gaps")
async def get_school_gaps(
    state: Optional[str] = Query(None),
    max_distance_km: float = Query(10.0, ge=1, le=100),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Analyze school connectivity gaps by tower proximity."""
    return await social_gaps.school_connectivity_gaps(db, state=state, max_distance_km=max_distance_km, limit=limit)


@router.get("/health-gaps")
async def get_health_gaps(
    state: Optional[str] = Query(None),
    max_distance_km: float = Query(10.0, ge=1, le=100),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Analyze health facility connectivity gaps by tower proximity."""
    return await social_gaps.health_facility_gaps(db, state=state, max_distance_km=max_distance_km, limit=limit)


@router.get("/investment-priority")
async def get_investment_priority(
    state: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Composite investment priority ranking with sub-score breakdown."""
    return await investment_priority.investment_priority_ranking(db, state=state, limit=limit)


@router.get("/anomalies")
async def get_anomalies(
    state: Optional[str] = Query(None),
    lookback_months: int = Query(6, ge=1, le=24),
    limit: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Detect quality anomalies using IForest or z-score fallback."""
    return await investment_priority.anomaly_detection(db, state=state, lookback_months=lookback_months, limit=limit)
