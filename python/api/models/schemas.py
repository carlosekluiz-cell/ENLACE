"""
ENLACE Pydantic Schemas

Request/response models for the FastAPI endpoints.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════════════
# Geographic
# ═══════════════════════════════════════════════════════════════════════════════


class MunicipalitySearch(BaseModel):
    """Search query for municipalities."""

    q: str
    country: str = "BR"
    limit: int = 20


class MunicipalityResponse(BaseModel):
    """Municipality summary returned from search."""

    id: int
    code: str
    name: str
    state_abbrev: Optional[str] = None
    country_code: str
    area_km2: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class GeoWithinRequest(BaseModel):
    """Request to find geographic entities within a radius."""

    lat: float
    lng: float
    radius_km: float = 50
    country: str = "BR"


# ═══════════════════════════════════════════════════════════════════════════════
# Market
# ═══════════════════════════════════════════════════════════════════════════════


class MarketSummary(BaseModel):
    """Aggregated market data for a municipality."""

    municipality_id: int
    code: str
    name: str
    state_abbrev: Optional[str] = None
    year_month: str
    total_subscribers: int
    fiber_subscribers: int
    provider_count: int
    total_households: Optional[int] = None
    total_population: Optional[int] = None
    broadband_penetration_pct: Optional[float] = None
    fiber_share_pct: Optional[float] = None


class ProviderBreakdown(BaseModel):
    """Individual provider share within a market."""

    provider_id: int
    name: str
    subscribers: int
    share_pct: float
    technology: Optional[str] = None
    growth_3m: Optional[float] = None


class CompetitorResponse(BaseModel):
    """Competitive landscape for a municipality."""

    hhi_index: float
    providers: list[ProviderBreakdown]
    threats: list[dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# Opportunity
# ═══════════════════════════════════════════════════════════════════════════════


class OpportunityScoreRequest(BaseModel):
    """Request to compute or retrieve an opportunity score."""

    country_code: str = "BR"
    area_type: str = "municipality"
    area_id: str


class OpportunityScoreResponse(BaseModel):
    """Opportunity score result."""

    composite_score: float
    confidence: float
    sub_scores: dict[str, float]
    top_factors: list[dict[str, Any]]
    market_summary: dict[str, Any]


class FinancialRequest(BaseModel):
    """Request for financial viability analysis."""

    municipality_code: str
    from_network_lat: float
    from_network_lon: float
    monthly_price_brl: float = 89.90
    technology: str = "fiber"


class FinancialResponse(BaseModel):
    """Financial viability analysis result."""

    subscriber_projection: dict[str, Any]
    capex_estimate: dict[str, Any]
    financial_metrics: dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# Design (RF Coverage)
# ═══════════════════════════════════════════════════════════════════════════════


class CoverageRequest(BaseModel):
    """Request for RF coverage simulation."""

    tower_lat: float
    tower_lon: float
    tower_height_m: float = 30
    frequency_mhz: float = 700
    tx_power_dbm: float = 43
    antenna_gain_dbi: float = 15
    radius_m: float = 10000
    grid_resolution_m: float = 30
    apply_vegetation: bool = True
    country_code: str = "BR"


class DesignJobStatus(BaseModel):
    """Status of an async design/coverage job."""

    job_id: str
    status: str
    progress_pct: float = 0.0
    result: Optional[dict[str, Any]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════════════════


class TokenRequest(BaseModel):
    """OAuth2-style token request."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"


class TenantCreate(BaseModel):
    """Request to create a new tenant (ISP organization)."""

    name: str
    country_code: str = "BR"
    primary_state: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════════
# Health
# ═══════════════════════════════════════════════════════════════════════════════


class HealthCheckResponse(BaseModel):
    """API health check response."""

    status: str
    version: str
    database: str = "unknown"
    redis: str = "unknown"
