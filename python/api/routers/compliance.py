"""
ENLACE Compliance Router

Regulatory compliance endpoints for Brazilian ISPs. Provides compliance
dashboards, Norma no. 4 tax impact calculations, licensing threshold
checks, quality assessments, deadline tracking, and regulation lookups.
"""

import dataclasses
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from python.api.auth.dependencies import require_auth

from python.regulatory.analyzer.norma4 import (
    calculate_impact,
    calculate_multi_state_impact,
)
from python.regulatory.analyzer.profile import analyze_profile
from python.regulatory.analyzer.licensing import check_licensing
from python.regulatory.analyzer.quality import (
    check_quality,
    QUALITY_THRESHOLDS,
)
from python.regulatory.knowledge_base.regulations import (
    get_regulation,
    get_active_regulations,
    REGULATIONS,
)
from python.regulatory.knowledge_base.deadlines import (
    get_all_deadlines,
    get_upcoming_deadlines,
)
from python.regulatory.knowledge_base.tax_rates import ICMS_RATES_SCM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------

class StateRevenue(BaseModel):
    """Revenue data for a single state."""
    state_code: str = Field(..., min_length=2, max_length=2, description="Two-letter UF code")
    revenue_monthly_brl: float = Field(..., gt=0, description="Monthly revenue in BRL")


class MultiStateRequest(BaseModel):
    """Request body for multi-state Norma no. 4 impact calculation."""
    states: list[StateRevenue] = Field(..., min_length=1, description="List of state revenue entries")
    subscriber_count: int = Field(..., ge=0, description="Total subscriber count")
    current_classification: str = Field(
        "SVA",
        description="Current classification: SVA or SCM",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_dataclass(obj):
    """Convert a dataclass to a dict, handling nested dataclasses and dates."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = _serialize_value(value)
        return result
    raise TypeError(f"Expected a dataclass instance, got {type(obj)}")


def _serialize_value(value):
    """Recursively serialize a value for JSON response."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _serialize_dataclass(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if hasattr(value, 'value'):
        # Handle enums
        return value.value
    return value


def _validate_state_code(state_code: str) -> str:
    """Validate and normalize a state code. Raises HTTPException on invalid."""
    code = state_code.strip().upper()
    if code not in ICMS_RATES_SCM:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown state code '{state_code}'. Must be a valid Brazilian UF code.",
        )
    return code


def _validate_subscribers(subscribers: int) -> int:
    """Validate subscriber count. Raises HTTPException if negative."""
    if subscribers < 0:
        raise HTTPException(
            status_code=400,
            detail="Subscriber count cannot be negative.",
        )
    return subscribers


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def compliance_status(
    provider_name: str = Query(..., min_length=1, description="ISP provider name"),
    state: str = Query(..., min_length=2, max_length=2, description="Two-letter state UF code"),
    subscribers: int = Query(..., ge=0, description="Number of subscribers"),
    services: str = Query("SCM", description="Comma-separated service types (e.g. SCM,broadband)"),
    classification: str = Query("SVA", description="Current classification: SVA or SCM"),
    revenue_monthly: Optional[float] = Query(None, ge=0, description="Monthly revenue in BRL"),
    user: dict = Depends(require_auth),
):
    """
    Full compliance dashboard for an ISP provider.

    Returns an overall compliance score, individual regulatory checks,
    critical issues count, warnings, and prioritized action items.
    """
    state_code = _validate_state_code(state)
    service_list = [s.strip() for s in services.split(",") if s.strip()]

    profile = analyze_profile(
        provider_name=provider_name,
        state_codes=[state_code],
        subscriber_count=subscribers,
        services=service_list,
        current_classification=classification,
        monthly_revenue_brl=revenue_monthly,
    )

    return _serialize_dataclass(profile)


@router.get("/norma4/impact")
async def norma4_impact(
    state: str = Query(..., min_length=2, max_length=2, description="Two-letter state UF code"),
    subscribers: int = Query(..., ge=0, description="Number of subscribers"),
    revenue_monthly: float = Query(..., ge=0, description="Monthly broadband revenue in BRL"),
    classification: str = Query("SVA", description="Current classification: SVA or SCM"),
    user: dict = Depends(require_auth),
):
    """
    Calculate the Norma no. 4 tax impact for a single state.

    Returns ICMS rate, additional monthly/annual tax amounts,
    restructuring options with scores, and readiness assessment.
    """
    state_code = _validate_state_code(state)
    _validate_subscribers(subscribers)

    try:
        impact = calculate_impact(
            state_code=state_code,
            monthly_broadband_revenue_brl=revenue_monthly,
            subscriber_count=subscribers,
            current_classification=classification,
        )
    except ValueError as e:
        logger.warning("Norma4 impact validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid impact calculation parameters")

    return _serialize_dataclass(impact)


@router.post("/norma4/multi-state")
async def norma4_multi_state(
    request: MultiStateRequest,
    user: dict = Depends(require_auth),
):
    """
    Calculate aggregate Norma no. 4 tax impact across multiple states.

    Accepts a list of state/revenue pairs and returns per-state impacts
    plus aggregate totals including blended ICMS rate.
    """
    # Validate all state codes
    state_revenues: dict[str, float] = {}
    for entry in request.states:
        code = _validate_state_code(entry.state_code)
        state_revenues[code] = entry.revenue_monthly_brl

    _validate_subscribers(request.subscriber_count)

    try:
        result = calculate_multi_state_impact(
            state_revenues=state_revenues,
            subscriber_count=request.subscriber_count,
            current_classification=request.current_classification,
        )
    except ValueError as e:
        logger.warning("Multi-state impact validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid multi-state impact parameters")

    # Serialize per-state Norma4Impact dataclass objects
    serialized = dict(result)
    if "per_state" in serialized:
        serialized["per_state"] = {
            code: _serialize_dataclass(impact)
            for code, impact in result["per_state"].items()
        }

    return serialized


@router.get("/licensing/check")
async def licensing_check(
    subscribers: int = Query(..., ge=0, description="Number of subscribers"),
    services: str = Query("SCM", description="Comma-separated service types"),
    revenue_monthly: Optional[float] = Query(None, ge=0, description="Monthly revenue in BRL"),
    user: dict = Depends(require_auth),
):
    """
    Check licensing threshold status for an ISP.

    Evaluates whether the ISP's subscriber count exceeds the 5,000
    threshold requiring formal Anatel authorization, and provides
    cost estimates and urgency assessment.
    """
    _validate_subscribers(subscribers)
    service_list = [s.strip() for s in services.split(",") if s.strip()]

    try:
        status = check_licensing(
            subscriber_count=subscribers,
            services=service_list,
            monthly_revenue_brl=revenue_monthly,
        )
    except ValueError as e:
        logger.warning("Licensing check validation error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid licensing check parameters")

    return _serialize_dataclass(status)


@router.get("/deadlines")
async def deadlines(
    days_ahead: int = Query(365, ge=1, le=3650, description="Number of days ahead to search"),
    user: dict = Depends(require_auth),
):
    """
    Get all upcoming regulatory deadlines within the specified window.

    Returns milestones and final deadlines sorted by date, each with
    urgency classification and days remaining.
    """
    upcoming = get_upcoming_deadlines(within_days=days_ahead)
    return [_serialize_dataclass(d) for d in upcoming]


@router.get("/quality/check")
async def quality_check(
    provider_id: str = Query(..., description="Provider identifier"),
    download_speed_pct: Optional[float] = Query(None, ge=0, le=100, description="Download speed compliance %"),
    upload_speed_pct: Optional[float] = Query(None, ge=0, le=100, description="Upload speed compliance %"),
    latency_pct: Optional[float] = Query(None, ge=0, le=100, description="Latency compliance %"),
    availability_pct: Optional[float] = Query(None, ge=0, le=100, description="Network availability %"),
    ida_score: Optional[float] = Query(None, ge=0, le=10, description="IDA composite score"),
    subscribers: int = Query(0, ge=0, description="Subscriber count for reporting threshold"),
    user: dict = Depends(require_auth),
):
    """
    Check quality metrics against Anatel regulatory thresholds.

    If no metric values are provided, returns the thresholds and a
    status of 'unknown'. When metrics are provided, evaluates each
    against regulatory minimums and flags violations and warnings.
    """
    metrics: dict[str, float] = {}
    if download_speed_pct is not None:
        metrics["download_speed_compliance_pct"] = download_speed_pct
    if upload_speed_pct is not None:
        metrics["upload_speed_compliance_pct"] = upload_speed_pct
    if latency_pct is not None:
        metrics["latency_compliance_pct"] = latency_pct
    if availability_pct is not None:
        metrics["availability_pct"] = availability_pct
    if ida_score is not None:
        metrics["ida_score_min"] = ida_score

    if not metrics:
        # No metrics provided: return thresholds with unknown status
        return {
            "provider_id": provider_id,
            "status": "unknown",
            "message": "No quality metrics provided. Supply metric query parameters for assessment.",
            "thresholds": QUALITY_THRESHOLDS,
        }

    status = check_quality(
        metrics=metrics,
        subscriber_count=subscribers,
    )

    result = _serialize_dataclass(status)
    result["provider_id"] = provider_id
    return result


@router.get("/regulations")
async def list_regulations(user: dict = Depends(require_auth)):
    """
    Get all active regulations in the knowledge base.

    Returns the full regulatory database including compliance
    requirements, penalties, and impact classification.
    """
    active = get_active_regulations()
    return [_serialize_dataclass(r) for r in active]


@router.get("/regulations/{regulation_id}")
async def get_regulation_detail(regulation_id: str, user: dict = Depends(require_auth)):
    """
    Get detailed information about a specific regulation.

    Returns full regulation details including compliance requirements,
    penalties, affected services, and source URL.
    """
    reg = get_regulation(regulation_id)
    if reg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Regulation '{regulation_id}' not found. "
            f"Valid IDs: {', '.join(r.id for r in REGULATIONS)}",
        )
    return _serialize_dataclass(reg)
