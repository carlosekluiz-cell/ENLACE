"""
ENLACE Reports Router

PDF report generation endpoints for market analysis, expansion opportunity,
regulatory compliance, and rural feasibility reports.  Returns PDF via
WeasyPrint when available, otherwise falls back to HTML.
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import io

from python.api.auth.dependencies import require_auth

from python.reports.generator import (
    generate_market_report,
    generate_expansion_report,
    generate_compliance_report,
    generate_rural_report,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class MarketReportRequest(BaseModel):
    """Request body for market analysis report."""
    municipality_id: int = Field(..., description="IBGE municipality identifier")
    provider_id: Optional[int] = Field(None, description="Optional provider ID for focused analysis")


class ExpansionReportRequest(BaseModel):
    """Request body for expansion opportunity report."""
    municipality_id: int = Field(..., description="IBGE municipality identifier")


class ComplianceReportRequest(BaseModel):
    """Request body for compliance report."""
    provider_name: str = Field(..., min_length=1, description="ISP provider name")
    state_codes: list[str] = Field(..., min_length=1, description="List of two-letter state codes")
    subscriber_count: int = Field(..., ge=0, description="Total subscriber count")
    revenue_monthly: Optional[float] = Field(None, ge=0, description="Monthly revenue in BRL")


class RuralReportRequest(BaseModel):
    """Request body for rural feasibility report."""
    community_lat: float = Field(..., description="Community center latitude")
    community_lon: float = Field(..., description="Community center longitude")
    population: int = Field(..., ge=0, description="Community population")
    area_km2: float = Field(..., gt=0, description="Community area in km^2")
    grid_power: bool = Field(False, description="Grid electricity available")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/market")
async def market_report(
    request: MarketReportRequest,
    user: dict = Depends(require_auth),
):
    """Generate a market analysis PDF report for a municipality.

    Returns a PDF document (or HTML fallback) with market overview,
    competitive landscape, technology distribution, and recommendations.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return generate_market_report(
            municipality_id=request.municipality_id,
            provider_id=request.provider_id,
        )

    try:
        content_bytes, media_type = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Market report generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")

    filename = f"enlace_market_{request.municipality_id}.pdf"
    if media_type == "text/html":
        filename = f"enlace_market_{request.municipality_id}.html"

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/expansion")
async def expansion_report(
    request: ExpansionReportRequest,
    user: dict = Depends(require_auth),
):
    """Generate an expansion opportunity PDF report for a municipality.

    Returns a PDF document with opportunity scoring, financial viability
    analysis, CAPEX estimates, and strategic recommendations.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return generate_expansion_report(municipality_id=request.municipality_id)

    try:
        content_bytes, media_type = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Expansion report generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")

    filename = f"enlace_expansion_{request.municipality_id}.pdf"
    if media_type == "text/html":
        filename = f"enlace_expansion_{request.municipality_id}.html"

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/compliance")
async def compliance_report(request: ComplianceReportRequest):
    """Generate a regulatory compliance PDF report for an ISP.

    Returns a PDF document with licensing status, Norma no. 4 tax impact,
    quality obligations, deadline tracking, and compliance recommendations.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return generate_compliance_report(
            provider_name=request.provider_name,
            state_codes=request.state_codes,
            subscriber_count=request.subscriber_count,
            revenue=request.revenue_monthly,
        )

    try:
        content_bytes, media_type = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Compliance report generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")

    safe_name = request.provider_name.replace(" ", "_")[:30]
    filename = f"enlace_compliance_{safe_name}.pdf"
    if media_type == "text/html":
        filename = f"enlace_compliance_{safe_name}.html"

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/rural")
async def rural_report(request: RuralReportRequest):
    """Generate a rural feasibility PDF report.

    Returns a PDF document with hybrid network design, equipment list,
    cost estimates, demand analysis, solar power sizing (if off-grid),
    and funding program eligibility.
    """
    loop = asyncio.get_event_loop()

    def _run():
        return generate_rural_report(
            community_lat=request.community_lat,
            community_lon=request.community_lon,
            population=request.population,
            area_km2=request.area_km2,
            grid_power=request.grid_power,
        )

    try:
        content_bytes, media_type = await loop.run_in_executor(None, _run)
    except Exception as e:
        logger.error("Rural report generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")

    filename = f"enlace_rural_{request.community_lat:.2f}_{request.community_lon:.2f}.pdf"
    if media_type == "text/html":
        filename = f"enlace_rural_{request.community_lat:.2f}_{request.community_lon:.2f}.html"

    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
