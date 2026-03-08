"""
ENLACE M&A Intelligence Router

Standalone M&A intelligence endpoints for ISP mergers and acquisitions.
Provides three valuation methods, acquirer target evaluation, seller
preparation reports, and market overview data.

IMPORTANT: This module reads ONLY public Anatel/IBGE data through read-only
views. It never accesses tenant-specific data from the operations platform.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from python.mna.valuation import subscriber_multiple, revenue_multiple, dcf
from python.mna import acquirer, seller


router = APIRouter(prefix="/api/v1/mna", tags=["mna"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic request/response models
# ═══════════════════════════════════════════════════════════════════════════════


class ValuationRequest(BaseModel):
    """Request body for the combined valuation calculator."""

    subscriber_count: int = Field(..., ge=1, description="Total active subscribers")
    fiber_pct: float = Field(0.5, ge=0.0, le=1.0, description="Fiber subscriber fraction")
    monthly_revenue_brl: float = Field(..., gt=0, description="Monthly recurring revenue (BRL)")
    ebitda_margin_pct: float = Field(30.0, ge=0, le=100, description="EBITDA margin %")
    state_code: str = Field("SP", min_length=2, max_length=2, description="State code")
    monthly_churn_pct: float = Field(2.0, ge=0, description="Monthly churn %")
    growth_rate_12m: float = Field(0.05, description="12-month subscriber growth rate")
    net_debt_brl: float = Field(0.0, ge=0, description="Net debt (BRL)")


class ValuationResponse(BaseModel):
    """Combined valuation result from all three methods."""

    subscriber_multiple: dict[str, Any]
    revenue_multiple: dict[str, Any]
    dcf: dict[str, Any]
    combined_range: dict[str, float]


class TargetsRequest(BaseModel):
    """Request body for acquirer target search."""

    acquirer_states: list[str] = Field(..., min_length=1, description="Acquirer's operating states")
    acquirer_subscribers: int = Field(..., ge=1, description="Acquirer's subscriber count")
    min_subs: int = Field(1_000, ge=0, description="Min target subscriber count")
    max_subs: int = Field(50_000, ge=0, description="Max target subscriber count")


class AcquisitionTargetResponse(BaseModel):
    """Single acquisition target in response."""

    provider_id: int
    provider_name: str
    state_codes: list[str]
    subscriber_count: int
    fiber_pct: float
    estimated_revenue_brl: float
    valuation_subscriber: float
    valuation_revenue: float
    valuation_dcf: float
    strategic_score: float
    financial_score: float
    integration_risk: str
    synergy_estimate_brl: float
    overall_score: float


class SellerPrepareRequest(BaseModel):
    """Request body for seller preparation report."""

    provider_name: str = Field(..., min_length=1, description="ISP name")
    state_codes: list[str] = Field(..., min_length=1, description="Operating states")
    subscriber_count: int = Field(..., ge=1, description="Total subscribers")
    fiber_pct: float = Field(0.5, ge=0.0, le=1.0, description="Fiber subscriber fraction")
    monthly_revenue_brl: float = Field(..., gt=0, description="Monthly revenue (BRL)")
    ebitda_margin_pct: float = Field(30.0, ge=0, le=100, description="EBITDA margin %")
    net_debt_brl: float = Field(0.0, ge=0, description="Net debt (BRL)")


class SellerReportResponse(BaseModel):
    """Seller preparation report response."""

    provider_name: str
    subscriber_count: int
    estimated_value_range: list[float]
    valuation_methods: dict[str, Any]
    strengths: list[str]
    weaknesses: list[str]
    value_enhancement_opportunities: list[dict[str, Any]]
    preparation_checklist: list[dict[str, Any]]
    estimated_timeline_months: int


class MarketOverviewResponse(BaseModel):
    """Market overview for a state or region."""

    state: str
    total_isps: int
    total_subscribers: int
    avg_valuation_per_sub: float
    fiber_pct_avg: float
    recent_transactions: list[dict[str, Any]]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /valuation — Combined valuation calculator
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/valuation", response_model=ValuationResponse)
async def calculate_valuation(request: ValuationRequest):
    """Calculate ISP valuation using all three methods.

    Returns subscriber-multiple, revenue-multiple, and DCF valuations,
    plus a combined range spanning all methods.
    """
    # Subscriber multiple
    val_sub = subscriber_multiple.calculate(
        total_subscribers=request.subscriber_count,
        fiber_pct=request.fiber_pct,
        monthly_churn_pct=request.monthly_churn_pct,
        growth_rate_12m=request.growth_rate_12m,
        state_code=request.state_code,
    )

    # Revenue multiple
    val_rev = revenue_multiple.calculate(
        monthly_revenue_brl=request.monthly_revenue_brl,
        ebitda_margin_pct=request.ebitda_margin_pct,
        subscriber_count=request.subscriber_count,
        revenue_growth_12m=request.growth_rate_12m,
        fiber_pct=request.fiber_pct,
    )

    # DCF
    val_dcf = dcf.calculate(
        monthly_revenue_brl=request.monthly_revenue_brl,
        ebitda_margin_pct=request.ebitda_margin_pct,
        net_debt_brl=request.net_debt_brl,
    )

    # Combined range
    all_lows = [
        val_sub.valuation_range[0],
        val_rev.valuation_range[0],
        val_dcf.equity_value_brl * 0.85,
    ]
    all_highs = [
        val_sub.valuation_range[1],
        val_rev.valuation_range[1],
        val_dcf.equity_value_brl * 1.15,
    ]

    combined_low = min(all_lows)
    combined_high = max(all_highs)
    combined_mid = (
        val_sub.adjusted_valuation_brl
        + (val_rev.ev_revenue_brl + val_rev.ev_ebitda_brl) / 2
        + val_dcf.equity_value_brl
    ) / 3

    return ValuationResponse(
        subscriber_multiple={
            "adjusted_valuation_brl": val_sub.adjusted_valuation_brl,
            "range": list(val_sub.valuation_range),
            "fiber_multiple": val_sub.fiber_multiple,
            "other_multiple": val_sub.other_multiple,
            "adjustments": val_sub.adjustments,
            "confidence": val_sub.confidence,
        },
        revenue_multiple={
            "ev_revenue_brl": val_rev.ev_revenue_brl,
            "ev_ebitda_brl": val_rev.ev_ebitda_brl,
            "range": list(val_rev.valuation_range),
            "revenue_multiple": val_rev.revenue_multiple,
            "ebitda_multiple": val_rev.ebitda_multiple,
            "annual_revenue_brl": val_rev.annual_revenue_brl,
            "ebitda_brl": val_rev.ebitda_brl,
            "adjustments": val_rev.adjustments,
        },
        dcf={
            "enterprise_value_brl": val_dcf.enterprise_value_brl,
            "equity_value_brl": val_dcf.equity_value_brl,
            "terminal_value_brl": val_dcf.terminal_value_brl,
            "wacc_pct": val_dcf.wacc_pct,
            "net_debt_brl": val_dcf.net_debt_brl,
            "projected_cashflows": val_dcf.projected_cashflows,
            "sensitivity_table": val_dcf.sensitivity_table,
        },
        combined_range={
            "low_brl": round(combined_low, 2),
            "mid_brl": round(combined_mid, 2),
            "high_brl": round(combined_high, 2),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /targets — Acquirer target discovery
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/targets", response_model=list[AcquisitionTargetResponse])
async def find_targets(request: TargetsRequest):
    """Find and evaluate potential ISP acquisition targets.

    Scores targets on strategic fit, financial attractiveness,
    integration risk, and synergy potential.
    """
    targets = acquirer.evaluate_targets(
        acquirer_states=request.acquirer_states,
        acquirer_subscribers=request.acquirer_subscribers,
        min_target_subs=request.min_subs,
        max_target_subs=request.max_subs,
    )

    return [
        AcquisitionTargetResponse(
            provider_id=t.provider_id,
            provider_name=t.provider_name,
            state_codes=t.state_codes,
            subscriber_count=t.subscriber_count,
            fiber_pct=t.fiber_pct,
            estimated_revenue_brl=t.estimated_revenue_brl,
            valuation_subscriber=t.valuation_subscriber,
            valuation_revenue=t.valuation_revenue,
            valuation_dcf=t.valuation_dcf,
            strategic_score=t.strategic_score,
            financial_score=t.financial_score,
            integration_risk=t.integration_risk,
            synergy_estimate_brl=t.synergy_estimate_brl,
            overall_score=t.overall_score,
        )
        for t in targets
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /seller/prepare — Seller preparation report
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/seller/prepare", response_model=SellerReportResponse)
async def seller_prepare(request: SellerPrepareRequest):
    """Generate a comprehensive seller preparation report.

    Includes valuations from all three methods, strengths/weaknesses analysis,
    value enhancement opportunities, and a due diligence preparation checklist.
    """
    report = seller.prepare_for_sale(
        provider_name=request.provider_name,
        state_codes=request.state_codes,
        subscriber_count=request.subscriber_count,
        fiber_pct=request.fiber_pct,
        monthly_revenue_brl=request.monthly_revenue_brl,
        ebitda_margin_pct=request.ebitda_margin_pct,
        net_debt_brl=request.net_debt_brl,
    )

    return SellerReportResponse(
        provider_name=report.provider_name,
        subscriber_count=report.subscriber_count,
        estimated_value_range=list(report.estimated_value_range),
        valuation_methods=report.valuation_methods,
        strengths=report.strengths,
        weaknesses=report.weaknesses,
        value_enhancement_opportunities=report.value_enhancement_opportunities,
        preparation_checklist=report.preparation_checklist,
        estimated_timeline_months=report.estimated_timeline_months,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /market — Market overview
# ═══════════════════════════════════════════════════════════════════════════════

# Simulated market data for development/testing.
# In production, this would query the read-only database views.
_MARKET_DATA: dict[str, dict] = {
    "SP": {
        "total_isps": 1_850,
        "total_subscribers": 4_200_000,
        "avg_valuation_per_sub": 2_800.0,
        "fiber_pct_avg": 0.72,
    },
    "MG": {
        "total_isps": 1_420,
        "total_subscribers": 2_100_000,
        "avg_valuation_per_sub": 2_200.0,
        "fiber_pct_avg": 0.58,
    },
    "RJ": {
        "total_isps": 980,
        "total_subscribers": 1_800_000,
        "avg_valuation_per_sub": 2_500.0,
        "fiber_pct_avg": 0.65,
    },
    "PR": {
        "total_isps": 820,
        "total_subscribers": 1_400_000,
        "avg_valuation_per_sub": 2_600.0,
        "fiber_pct_avg": 0.70,
    },
    "SC": {
        "total_isps": 650,
        "total_subscribers": 1_100_000,
        "avg_valuation_per_sub": 2_700.0,
        "fiber_pct_avg": 0.75,
    },
    "RS": {
        "total_isps": 780,
        "total_subscribers": 1_300_000,
        "avg_valuation_per_sub": 2_300.0,
        "fiber_pct_avg": 0.62,
    },
    "BA": {
        "total_isps": 620,
        "total_subscribers": 950_000,
        "avg_valuation_per_sub": 1_800.0,
        "fiber_pct_avg": 0.48,
    },
    "GO": {
        "total_isps": 480,
        "total_subscribers": 720_000,
        "avg_valuation_per_sub": 2_000.0,
        "fiber_pct_avg": 0.55,
    },
}

# Simulated recent transactions
_RECENT_DEALS: list[dict] = [
    {
        "acquirer": "Brasil TecPar",
        "target": "FibraLocal Telecom",
        "state": "PR",
        "date": "2025-08",
        "subscribers": 18_000,
        "value_per_sub_brl": 2_950,
    },
    {
        "acquirer": "Sumicity",
        "target": "NetVia Internet",
        "state": "SP",
        "date": "2025-06",
        "subscribers": 12_500,
        "value_per_sub_brl": 3_200,
    },
    {
        "acquirer": "Brisanet",
        "target": "ConectNordeste",
        "state": "CE",
        "date": "2025-04",
        "subscribers": 8_200,
        "value_per_sub_brl": 1_650,
    },
    {
        "acquirer": "Desktop",
        "target": "VelozNet SP",
        "state": "SP",
        "date": "2025-02",
        "subscribers": 25_000,
        "value_per_sub_brl": 3_100,
    },
    {
        "acquirer": "Unifique",
        "target": "SulFibra Internet",
        "state": "SC",
        "date": "2024-11",
        "subscribers": 9_800,
        "value_per_sub_brl": 2_800,
    },
]


@router.get("/market", response_model=MarketOverviewResponse)
async def market_overview(
    state: str = Query("SP", min_length=2, max_length=2, description="State code"),
):
    """Get M&A market overview for a Brazilian state.

    Returns aggregate statistics including total ISPs, subscriber count,
    average valuation per subscriber, and recent transactions.
    """
    state_upper = state.upper()
    data = _MARKET_DATA.get(state_upper)

    if data is None:
        # Return generic data for states not in the sample set
        data = {
            "total_isps": 300,
            "total_subscribers": 450_000,
            "avg_valuation_per_sub": 1_800.0,
            "fiber_pct_avg": 0.45,
        }

    # Filter recent deals for this state
    state_deals = [d for d in _RECENT_DEALS if d["state"] == state_upper]

    return MarketOverviewResponse(
        state=state_upper,
        total_isps=data["total_isps"],
        total_subscribers=data["total_subscribers"],
        avg_valuation_per_sub=data["avg_valuation_per_sub"],
        fiber_pct_avg=data["fiber_pct_avg"],
        recent_transactions=state_deals,
    )
