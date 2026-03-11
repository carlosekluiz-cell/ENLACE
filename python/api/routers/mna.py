"""
ENLACE M&A Intelligence Router

Standalone M&A intelligence endpoints for ISP mergers and acquisitions.
Provides three valuation methods, acquirer target evaluation, seller
preparation reports, and market overview data computed from real Anatel data.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.mna.valuation import subscriber_multiple, revenue_multiple, dcf  # noqa: E501
from python.mna import acquirer, seller


router = APIRouter(prefix="/api/v1/mna", tags=["mna"])


# ═══════════════════════════════════════════════════════════════════════════════
# Pydantic request/response models
# ═══════════════════════════════════════════════════════════════════════════════


class ValuationRequest(BaseModel):
    subscriber_count: int = Field(..., ge=1)
    fiber_pct: float = Field(50.0, ge=0.0, le=100.0)
    monthly_revenue_brl: float = Field(..., gt=0)
    ebitda_margin_pct: float = Field(30.0, ge=0, le=100)
    state_code: str = Field("SP", min_length=2, max_length=2)
    monthly_churn_pct: float = Field(2.0, ge=0)
    growth_rate_12m: float = Field(0.05)
    net_debt_brl: float = Field(0.0, ge=0)


class ValuationResponse(BaseModel):
    subscriber_multiple: dict[str, Any]
    revenue_multiple: dict[str, Any]
    dcf: dict[str, Any]
    combined_range: dict[str, float]


class TargetsRequest(BaseModel):
    acquirer_states: list[str] = Field(..., min_length=1)
    acquirer_subscribers: int = Field(..., ge=1)
    min_subs: int = Field(1_000, ge=0)
    max_subs: int = Field(50_000, ge=0)


class AcquisitionTargetResponse(BaseModel):
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
    provider_name: str = Field(..., min_length=1)
    state_codes: list[str] = Field(..., min_length=1)
    subscriber_count: int = Field(..., ge=1)
    fiber_pct: float = Field(50.0, ge=0.0, le=100.0)
    monthly_revenue_brl: float = Field(..., gt=0)
    ebitda_margin_pct: float = Field(30.0, ge=0, le=100)
    net_debt_brl: float = Field(0.0, ge=0)


class SellerReportResponse(BaseModel):
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
async def calculate_valuation(
    request: ValuationRequest,
    user: dict = Depends(require_auth),
):
    """Calculate ISP valuation using subscriber-multiple, revenue-multiple, and DCF."""
    val_sub = subscriber_multiple.calculate(
        total_subscribers=request.subscriber_count,
        fiber_pct=request.fiber_pct,
        monthly_churn_pct=request.monthly_churn_pct,
        growth_rate_12m=request.growth_rate_12m,
        state_code=request.state_code,
    )

    val_rev = revenue_multiple.calculate(
        monthly_revenue_brl=request.monthly_revenue_brl,
        ebitda_margin_pct=request.ebitda_margin_pct,
        subscriber_count=request.subscriber_count,
        revenue_growth_12m=request.growth_rate_12m,
        fiber_pct=request.fiber_pct,
    )

    val_dcf = dcf.calculate(
        monthly_revenue_brl=request.monthly_revenue_brl,
        ebitda_margin_pct=request.ebitda_margin_pct,
        net_debt_brl=request.net_debt_brl,
    )

    all_lows = [val_sub.valuation_range[0], val_rev.valuation_range[0], val_dcf.equity_value_brl * 0.85]
    all_highs = [val_sub.valuation_range[1], val_rev.valuation_range[1], val_dcf.equity_value_brl * 1.15]
    combined_mid = (val_sub.adjusted_valuation_brl + (val_rev.ev_revenue_brl + val_rev.ev_ebitda_brl) / 2 + val_dcf.equity_value_brl) / 3

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
            "low_brl": round(min(all_lows), 2),
            "mid_brl": round(combined_mid, 2),
            "high_brl": round(max(all_highs), 2),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /targets — Acquirer target discovery
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/targets")
async def find_targets(
    request: TargetsRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Find and evaluate potential ISP acquisition targets, enriched with quality/contract/BNDES data."""
    targets = acquirer.evaluate_targets(
        acquirer_states=request.acquirer_states,
        acquirer_subscribers=request.acquirer_subscribers,
        min_target_subs=request.min_subs,
        max_target_subs=request.max_subs,
    )

    results = []
    for t in targets:
        base = {
            "provider_id": t.provider_id,
            "provider_name": t.provider_name,
            "state_codes": t.state_codes,
            "subscriber_count": t.subscriber_count,
            "fiber_pct": t.fiber_pct,
            "estimated_revenue_brl": t.estimated_revenue_brl,
            "valuation_subscriber": t.valuation_subscriber,
            "valuation_revenue": t.valuation_revenue,
            "valuation_dcf": t.valuation_dcf,
            "strategic_score": t.strategic_score,
            "financial_score": t.financial_score,
            "integration_risk": t.integration_risk,
            "synergy_estimate_brl": t.synergy_estimate_brl,
            "overall_score": t.overall_score,
        }

        # Enrich: average quality seal score
        r = await db.execute(text("""
            SELECT AVG(overall_score) AS avg_score
            FROM quality_seals WHERE provider_id = :pid
        """), {"pid": t.provider_id})
        qs = r.fetchone()
        base["quality_seal_avg"] = round(float(qs.avg_score), 1) if qs and qs.avg_score else None

        # Enrich: government contracts won (matched by provider CNPJ)
        r = await db.execute(text("""
            SELECT COUNT(*) AS cnt
            FROM government_contracts gc
            JOIN providers p ON gc.winner_cnpj = p.national_id
            WHERE p.id = :pid
        """), {"pid": t.provider_id})
        gc = r.fetchone()
        base["government_contracts_won"] = gc.cnt if gc else 0

        # Enrich: BNDES loan total
        r = await db.execute(text("""
            SELECT COALESCE(SUM(contract_value_brl), 0) AS total
            FROM bndes_loans WHERE provider_id = :pid
        """), {"pid": t.provider_id})
        bn = r.fetchone()
        base["bndes_loan_total_brl"] = float(bn.total) if bn else 0

        results.append(base)

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# POST /seller/prepare — Seller preparation report
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/seller/prepare", response_model=SellerReportResponse)
async def seller_prepare(
    request: SellerPrepareRequest,
    user: dict = Depends(require_auth),
):
    """Generate a comprehensive seller preparation report."""
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
# GET /market — Real-time market overview from Anatel data
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/market", response_model=MarketOverviewResponse)
async def market_overview(
    state: str = Query("SP", min_length=2, max_length=2, description="State code"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get M&A market overview for a Brazilian state.

    Computes real statistics from Anatel broadband subscriber data:
    total ISPs, subscribers, fiber share, and top providers.
    """
    state_upper = state.upper()

    sql = text("""
        WITH state_data AS (
            SELECT
                bs.provider_id,
                p.name as provider_name,
                SUM(bs.subscribers) as total_subs,
                SUM(CASE WHEN bs.technology = 'fiber' THEN bs.subscribers ELSE 0 END) as fiber_subs
            FROM broadband_subscribers bs
            JOIN providers p ON bs.provider_id = p.id
            JOIN admin_level_2 a ON bs.l2_id = a.id
            JOIN admin_level_1 l1 ON a.l1_id = l1.id
            WHERE l1.abbrev = :state
              AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY bs.provider_id, p.name
        )
        SELECT
            COUNT(*) as total_isps,
            COALESCE(SUM(total_subs), 0) as total_subscribers,
            CASE WHEN SUM(total_subs) > 0
                 THEN ROUND(SUM(fiber_subs)::numeric / SUM(total_subs), 2)
                 ELSE 0 END as fiber_pct_avg
        FROM state_data
    """)

    result = await db.execute(sql, {"state": state_upper})
    row = result.fetchone()

    total_isps = int(row.total_isps or 0)
    total_subscribers = int(row.total_subscribers or 0)
    fiber_pct = float(row.fiber_pct_avg or 0)

    # Estimate valuation per sub: R$1,500 base + fiber premium + regional premium
    base_valuation = 1500 + (fiber_pct * 2000)
    if state_upper in ('SP', 'RJ', 'MG', 'PR', 'SC', 'RS', 'ES'):
        base_valuation *= 1.15

    # Top 5 providers in this state (potential acquirers/targets)
    top_sql = text("""
        SELECT p.name, SUM(bs.subscribers) as subs,
               SUM(CASE WHEN bs.technology='fiber' THEN bs.subscribers ELSE 0 END) as fiber
        FROM broadband_subscribers bs
        JOIN providers p ON bs.provider_id = p.id
        JOIN admin_level_2 a ON bs.l2_id = a.id
        JOIN admin_level_1 l1 ON a.l1_id = l1.id
        WHERE l1.abbrev = :state
          AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
        GROUP BY p.name
        ORDER BY subs DESC
        LIMIT 5
    """)
    top_result = await db.execute(top_sql, {"state": state_upper})
    top_providers = [
        {
            "name": r.name,
            "subscribers": int(r.subs),
            "fiber_pct": round(int(r.fiber) / int(r.subs), 2) if r.subs else 0,
        }
        for r in top_result.fetchall()
    ]

    return MarketOverviewResponse(
        state=state_upper,
        total_isps=total_isps,
        total_subscribers=total_subscribers,
        avg_valuation_per_sub=round(base_valuation, 0),
        fiber_pct_avg=fiber_pct,
        recent_transactions=top_providers,
    )


@router.get("/provider/{provider_id}/details")
async def provider_details(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get CNPJ enrichment details for a provider (founding date, capital, status)."""
    sql = text("""
        SELECT p.name, p.national_id AS cnpj,
               pd.status, pd.capital_social, pd.founding_date,
               pd.address_city, pd.partner_count, pd.simples_nacional,
               pd.cnae_primary, pd.updated_at
        FROM providers p
        LEFT JOIN provider_details pd ON p.id = pd.provider_id
        WHERE p.id = :provider_id
    """)

    result = await db.execute(sql, {"provider_id": provider_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Provider not found")

    # Also fetch BNDES loans for this provider
    loans_sql = text("""
        SELECT contract_value_brl, disbursed_brl, contract_date, sector
        FROM bndes_loans WHERE provider_id = :pid
        ORDER BY contract_date DESC LIMIT 5
    """)
    loans_result = await db.execute(loans_sql, {"pid": provider_id})
    loans = [
        {
            "value_brl": float(l.contract_value_brl) if l.contract_value_brl else 0,
            "disbursed_brl": float(l.disbursed_brl) if l.disbursed_brl else 0,
            "date": str(l.contract_date) if l.contract_date else None,
            "sector": l.sector,
        }
        for l in loans_result.fetchall()
    ]

    return {
        "provider_id": provider_id,
        "name": row.name,
        "cnpj": row.cnpj,
        "company_status": row.status,
        "capital_social": float(row.capital_social) if row.capital_social else None,
        "founding_date": str(row.founding_date) if row.founding_date else None,
        "city": row.address_city,
        "partner_count": row.partner_count,
        "simples_nacional": row.simples_nacional,
        "cnae_primary": row.cnae_primary,
        "enrichment_date": str(row.updated_at) if row.updated_at else None,
        "bndes_loans": loans,
    }
