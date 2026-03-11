"""
ENLACE ISP Credit Scoring Router

Endpoints for ISP credit assessment, ranking, and rating distribution.
Credit scores are computed from Anatel subscriber data, quality indicators,
and regulatory compliance signals.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.credit_scoring import compute_credit_score


router = APIRouter(prefix="/api/v1/credit", tags=["credit"])


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _to_float(value: Any) -> float | None:
    """Convert Decimal or other numeric types to float, returning None for None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


# ═══════════════════════════════════════════════════════════════════════════════
# Response models
# ═══════════════════════════════════════════════════════════════════════════════


class CreditScoreResponse(BaseModel):
    id: Optional[int] = None
    provider_id: int
    provider_name: str
    credit_rating: str
    composite_score: float
    probability_of_default: float
    debt_service_ratio: float
    factor_scores: dict[str, float]
    factors: dict[str, Any]
    computed_at: str


class CreditRankingItem(BaseModel):
    provider_id: int
    provider_name: str
    credit_rating: str
    composite_score: float
    probability_of_default: float
    total_subscribers: int
    state_codes: list[str] = Field(default_factory=list)


class RatingDistributionItem(BaseModel):
    rating: str
    count: int
    pct: float


# ═══════════════════════════════════════════════════════════════════════════════
# GET /credit/ranking — ISP credit ranking
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/ranking", response_model=list[CreditRankingItem])
async def credit_ranking(
    min_rating: str = Query("BBB", description="Minimum credit rating (AAA, AA, A, BBB, BB, B, CCC)"),
    state: Optional[str] = Query(None, min_length=2, max_length=2, description="Filter by state abbreviation"),
    limit: int = Query(50, ge=1, le=500, description="Maximum results"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get ISP credit ranking filtered by minimum rating and optional state.

    Returns the latest credit score for each provider, ordered by composite
    score descending.  Only the most recent score per provider is included.
    """
    # Map rating to minimum composite score threshold
    rating_thresholds = {
        "AAA": 90.0,
        "AA": 80.0,
        "A": 70.0,
        "BBB": 60.0,
        "BB": 50.0,
        "B": 40.0,
        "CCC": 0.0,
    }
    min_score = rating_thresholds.get(min_rating.upper(), 60.0)

    # Build query with optional state filter
    where_clauses = ["ics.composite_score >= :min_score"]
    params: dict[str, Any] = {"min_score": min_score, "limit": limit}

    state_join = ""
    if state:
        state_join = """
            JOIN broadband_subscribers bs_state ON bs_state.provider_id = ics.provider_id
            JOIN admin_level_2 a2_state ON bs_state.l2_id = a2_state.id
            JOIN admin_level_1 a1_state ON a2_state.l1_id = a1_state.id
        """
        where_clauses.append("a1_state.abbrev = :state")
        params["state"] = state.upper()

    where_sql = " AND ".join(where_clauses)

    sql = text(f"""
        WITH latest_scores AS (
            SELECT DISTINCT ON (ics.provider_id)
                ics.provider_id,
                ics.credit_rating,
                ics.composite_score,
                ics.probability_of_default,
                p.name AS provider_name
            FROM isp_credit_scores ics
            JOIN providers p ON ics.provider_id = p.id
            {state_join}
            WHERE {where_sql}
            ORDER BY ics.provider_id, ics.computed_at DESC
        ),
        provider_subs AS (
            SELECT
                bs.provider_id,
                SUM(bs.subscribers) AS total_subscribers,
                ARRAY_AGG(DISTINCT a1.abbrev) AS state_codes
            FROM broadband_subscribers bs
            JOIN admin_level_2 a2 ON bs.l2_id = a2.id
            JOIN admin_level_1 a1 ON a2.l1_id = a1.id
            WHERE bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            GROUP BY bs.provider_id
        )
        SELECT
            ls.provider_id,
            ls.provider_name,
            ls.credit_rating,
            ls.composite_score,
            ls.probability_of_default,
            COALESCE(ps.total_subscribers, 0) AS total_subscribers,
            COALESCE(ps.state_codes, ARRAY[]::varchar[]) AS state_codes
        FROM latest_scores ls
        LEFT JOIN provider_subs ps ON ls.provider_id = ps.provider_id
        ORDER BY ls.composite_score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        CreditRankingItem(
            provider_id=row.provider_id,
            provider_name=row.provider_name,
            credit_rating=row.credit_rating,
            composite_score=_to_float(row.composite_score) or 0.0,
            probability_of_default=_to_float(row.probability_of_default) or 0.0,
            total_subscribers=int(row.total_subscribers),
            state_codes=list(row.state_codes) if row.state_codes else [],
        )
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# GET /credit/distribution — Rating distribution
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/distribution", response_model=list[RatingDistributionItem])
async def rating_distribution(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get the distribution of credit ratings across all scored providers.

    Returns the count and percentage for each rating tier, using only the
    latest score per provider.
    """
    sql = text("""
        WITH latest_scores AS (
            SELECT DISTINCT ON (provider_id)
                provider_id,
                credit_rating
            FROM isp_credit_scores
            ORDER BY provider_id, computed_at DESC
        ),
        total AS (
            SELECT COUNT(*) AS cnt FROM latest_scores
        )
        SELECT
            ls.credit_rating AS rating,
            COUNT(*) AS count,
            ROUND(COUNT(*)::numeric / GREATEST(t.cnt, 1) * 100, 1) AS pct
        FROM latest_scores ls
        CROSS JOIN total t
        GROUP BY ls.credit_rating, t.cnt
        ORDER BY
            CASE ls.credit_rating
                WHEN 'AAA' THEN 1
                WHEN 'AA'  THEN 2
                WHEN 'A'   THEN 3
                WHEN 'BBB' THEN 4
                WHEN 'BB'  THEN 5
                WHEN 'B'   THEN 6
                WHEN 'CCC' THEN 7
                ELSE 8
            END
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    if not rows:
        return []

    return [
        RatingDistributionItem(
            rating=row.rating,
            count=int(row.count),
            pct=_to_float(row.pct) or 0.0,
        )
        for row in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /credit/compute/{provider_id} — Trigger computation
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/compute/{provider_id}", response_model=CreditScoreResponse)
async def trigger_credit_computation(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Trigger a fresh credit score computation for a provider.

    Computes all six factor scores from live Anatel data, persists the
    result to ``isp_credit_scores``, and returns the full assessment.
    """
    result = await compute_credit_score(db, provider_id)

    if "error" in result:
        if result["error"] == "provider_not_found":
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found",
            )
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))

    return CreditScoreResponse(**result)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /credit/{provider_id} — Full credit score (last: path param route)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{provider_id}", response_model=CreditScoreResponse)
async def get_credit_score(
    provider_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """Get the latest credit score for a provider.

    Returns the most recent score from ``isp_credit_scores``, or 404 if
    no score has been computed yet.
    """
    sql = text("""
        SELECT
            ics.id,
            ics.provider_id,
            p.name AS provider_name,
            ics.credit_rating,
            ics.composite_score,
            ics.probability_of_default,
            ics.debt_service_ratio,
            ics.revenue_stability,
            ics.growth_trajectory,
            ics.market_position,
            ics.infrastructure_quality,
            ics.regulatory_compliance,
            ics.subscriber_concentration,
            ics.factors,
            ics.computed_at
        FROM isp_credit_scores ics
        JOIN providers p ON ics.provider_id = p.id
        WHERE ics.provider_id = :provider_id
        ORDER BY ics.computed_at DESC
        LIMIT 1
    """)

    result = await db.execute(sql, {"provider_id": provider_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"No credit score found for provider {provider_id}. Use POST /credit/compute/{provider_id} to generate one.",
        )

    return CreditScoreResponse(
        id=row.id,
        provider_id=row.provider_id,
        provider_name=row.provider_name,
        credit_rating=row.credit_rating,
        composite_score=_to_float(row.composite_score) or 0.0,
        probability_of_default=_to_float(row.probability_of_default) or 0.0,
        debt_service_ratio=_to_float(row.debt_service_ratio) or 0.0,
        factor_scores={
            "revenue_stability": _to_float(row.revenue_stability) or 0.0,
            "growth_trajectory": _to_float(row.growth_trajectory) or 0.0,
            "market_position": _to_float(row.market_position) or 0.0,
            "infrastructure_quality": _to_float(row.infrastructure_quality) or 0.0,
            "regulatory_compliance": _to_float(row.regulatory_compliance) or 0.0,
            "subscriber_concentration": _to_float(row.subscriber_concentration) or 0.0,
        },
        factors=row.factors or {},
        computed_at=row.computed_at.isoformat() if row.computed_at else "",
    )
