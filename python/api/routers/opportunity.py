"""
ENLACE Opportunity & Expansion Planning Router

Endpoints for opportunity scoring, financial viability analysis,
fiber route pre-design, and competitive intelligence.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.database import get_db
from python.api.models.schemas import (
    CompetitorResponse,
    FinancialRequest,
    FinancialResponse,
    OpportunityScoreRequest,
    OpportunityScoreResponse,
    ProviderBreakdown,
)
from python.api.services.market_intelligence import (
    compute_route,
    get_competitors,
    get_top_opportunities,
    run_financial_analysis,
    score_area,
)

router = APIRouter(prefix="/api/v1/opportunity", tags=["opportunity"])


# ═══════════════════════════════════════════════════════════════════════
# Additional Pydantic models for the route endpoint
# ═══════════════════════════════════════════════════════════════════════


class RouteRequest(BaseModel):
    """Request for fiber route pre-design between two geographic points."""

    from_lat: float = Field(..., description="Source latitude (POP location)")
    from_lon: float = Field(..., description="Source longitude")
    to_lat: float = Field(..., description="Destination latitude")
    to_lon: float = Field(..., description="Destination longitude")
    prefer_corridors: bool = Field(
        True,
        description=(
            "Whether to prefer routes along existing infrastructure "
            "corridors (power lines, existing fiber)"
        ),
    )


class BomItem(BaseModel):
    """A single item in the Bill of Materials."""

    name: str
    description: str
    quantity: int
    unit: str = "pcs"
    unit_cost_brl: float
    total_cost_brl: float


class RouteResponse(BaseModel):
    """Fiber route pre-design result."""

    route: Optional[dict[str, Any]] = Field(
        None, description="GeoJSON Feature with LineString geometry"
    )
    total_length_km: float
    estimated_cost_brl: float
    premises_passed: int
    bom: dict[str, Any] = Field(
        default_factory=dict,
        description="Bill of Materials with items, grand_total_brl, and summary",
    )


# ═══════════════════════════════════════════════════════════════════════
# POST /score — Score a specific area
# ═══════════════════════════════════════════════════════════════════════


@router.post("/score", response_model=OpportunityScoreResponse)
async def opportunity_score(
    request: OpportunityScoreRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve the pre-computed opportunity score for a municipality.

    Looks up the latest scoring run in ``opportunity_scores`` for the
    given area, returning the composite score, sub-scores (demand,
    competition, infrastructure, growth), top driving factors, and a
    market summary.
    """
    result = await score_area(
        db=db,
        country_code=request.country_code,
        area_type=request.area_type,
        area_id=request.area_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No opportunity score found for area_id={request.area_id} "
                f"(country={request.country_code}, type={request.area_type}). "
                f"The scoring pipeline may not have been run for this area."
            ),
        )

    return OpportunityScoreResponse(
        composite_score=result["composite_score"],
        confidence=result["confidence"],
        sub_scores=result["sub_scores"],
        top_factors=result["top_factors"],
        market_summary=result["market_summary"],
    )


# ═══════════════════════════════════════════════════════════════════════
# GET /top — Get top expansion opportunities
# ═══════════════════════════════════════════════════════════════════════


@router.get("/top")
async def top_opportunities(
    country: str = Query("BR", description="Country code"),
    state: Optional[str] = Query(None, description="State abbreviation (e.g. SP, MG)"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results to return"),
    min_score: float = Query(
        60.0, ge=0.0, le=100.0, description="Minimum composite score threshold"
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the top-scoring expansion opportunities.

    Returns municipalities ranked by composite opportunity score,
    with optional filters by state and minimum score threshold.
    Each result includes the score breakdown, municipality metadata,
    and demographic summary.
    """
    results = await get_top_opportunities(
        db=db,
        country=country,
        state=state,
        min_score=min_score,
        limit=limit,
    )

    if not results:
        return []

    return results


# ═══════════════════════════════════════════════════════════════════════
# POST /financial — Financial viability analysis
# ═══════════════════════════════════════════════════════════════════════


@router.post("/financial", response_model=FinancialResponse)
async def financial_analysis(request: FinancialRequest):
    """
    Run a full financial viability analysis for a municipality.

    Orchestrates subscriber projections, ARPU estimation, CAPEX modeling,
    and NPV/IRR/payback computation across pessimistic, base-case, and
    optimistic scenarios.

    This endpoint offloads the computation to a thread pool because the
    underlying ML module uses synchronous psycopg2 database access.
    """
    result = await run_financial_analysis(
        municipality_code=request.municipality_code,
        from_lat=request.from_network_lat,
        from_lon=request.from_network_lon,
        price=request.monthly_price_brl,
        technology=request.technology,
    )

    # Handle errors from the ML module
    if result.get("status") == "error":
        raise HTTPException(
            status_code=404,
            detail=result.get(
                "message",
                f"Financial analysis failed for municipality {request.municipality_code}",
            ),
        )

    # Map the full ML result to the API response schema
    subscriber_projection = {
        "market_sizing": result.get("market_sizing", {}),
        "curves": result.get("subscriber_projections", {}),
    }

    capex_estimate = result.get("capex", {})

    # Build financial_metrics from the scenarios + verdict
    financial_metrics = {
        "scenarios": result.get("scenarios", {}),
        "verdict": result.get("verdict", "unknown"),
        "assumptions": result.get("assumptions", {}),
        "municipality": result.get("municipality", {}),
        "arpu": result.get("arpu", {}),
    }

    return FinancialResponse(
        subscriber_projection=subscriber_projection,
        capex_estimate=capex_estimate,
        financial_metrics=financial_metrics,
    )


# ═══════════════════════════════════════════════════════════════════════
# POST /route — Fiber route pre-design
# ═══════════════════════════════════════════════════════════════════════


@router.post("/route", response_model=RouteResponse)
async def fiber_route(request: RouteRequest):
    """
    Compute a fiber route pre-design between two geographic points.

    Builds a road-network graph around the route corridor, optionally
    applies infrastructure corridor bonuses (power lines, existing fiber),
    computes the least-cost path using Dijkstra's algorithm, and generates
    a Bill of Materials.

    This endpoint offloads the computation to a thread pool because the
    underlying routing module uses synchronous psycopg2 database access.
    """
    # Validate that source and destination are different
    if (
        abs(request.from_lat - request.to_lat) < 1e-6
        and abs(request.from_lon - request.to_lon) < 1e-6
    ):
        raise HTTPException(
            status_code=400,
            detail="Source and destination coordinates must be different.",
        )

    result = await compute_route(
        from_lat=request.from_lat,
        from_lon=request.from_lon,
        to_lat=request.to_lat,
        to_lon=request.to_lon,
        prefer_corridors=request.prefer_corridors,
    )

    if result.get("status") == "error":
        raise HTTPException(
            status_code=422,
            detail=result.get("message", "Route computation failed"),
        )

    if result.get("status") == "no_path":
        raise HTTPException(
            status_code=404,
            detail=result.get(
                "message",
                "No connected path found between source and destination",
            ),
        )

    return RouteResponse(
        route=result.get("route"),
        total_length_km=result.get("total_length_km", 0.0),
        estimated_cost_brl=result.get("estimated_cost_brl", 0.0),
        premises_passed=result.get("premises_passed", 0),
        bom=result.get("bom", {}),
    )


# ═══════════════════════════════════════════════════════════════════════
# GET /{municipality_id}/competitors — Competitive analysis
# ═══════════════════════════════════════════════════════════════════════


@router.get("/{municipality_id}/competitors", response_model=CompetitorResponse)
async def municipality_competitors(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Get the competitive landscape for a municipality.

    Returns the HHI concentration index, per-provider breakdown
    (subscribers, market share, dominant technology), and threat
    assessments based on the latest ``competitive_analysis`` data.
    """
    result = await get_competitors(db=db, municipality_id=municipality_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No competitive analysis found for municipality {municipality_id}",
        )

    # Map provider dicts to ProviderBreakdown Pydantic models
    providers = [
        ProviderBreakdown(
            provider_id=p["provider_id"],
            name=p["name"],
            subscribers=p["subscribers"],
            share_pct=p["share_pct"],
            technology=p.get("technology"),
            growth_3m=p.get("growth_3m"),
        )
        for p in result["providers"]
    ]

    return CompetitorResponse(
        hhi_index=result["hhi_index"],
        providers=providers,
        threats=result["threats"],
    )
