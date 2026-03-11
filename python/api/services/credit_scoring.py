"""ISP Credit Scoring Service

Computes credit scores for ISP providers based on subscriber data, market
position, infrastructure quality, and regulatory compliance.  Results are
persisted to the ``isp_credit_scores`` table.

Rating scale:
    AAA  90+       AA  80-89      A   70-79
    BBB  60-69     BB  50-59      B   40-49      CCC  <40

Probability of default uses a logistic transform of the composite score.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _to_float(value: Any) -> float:
    """Coerce Decimal / None to float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _rating_from_score(score: float) -> str:
    """Map composite score to letter rating."""
    if score >= 90:
        return "AAA"
    if score >= 80:
        return "AA"
    if score >= 70:
        return "A"
    if score >= 60:
        return "BBB"
    if score >= 50:
        return "BB"
    if score >= 40:
        return "B"
    return "CCC"


def _probability_of_default(composite_score: float) -> float:
    """Simple logistic function: PD rises as score drops.

    At score=50 PD~50%; at score=90 PD~2%; at score=10 PD~98%.
    Formula: 1 / (1 + exp(0.1 * (score - 50)))
    """
    try:
        return round(1.0 / (1.0 + math.exp(0.1 * (composite_score - 50.0))), 4)
    except OverflowError:
        return 0.0 if composite_score > 50 else 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# Individual factor computations
# ═══════════════════════════════════════════════════════════════════════════════


async def _compute_revenue_stability(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """Coefficient of variation of monthly subscriber totals.

    Lower CV (more stable) maps to a higher score.
    """
    sql = text("""
        SELECT
            year_month,
            SUM(subscribers) AS monthly_total
        FROM broadband_subscribers
        WHERE provider_id = :pid
        GROUP BY year_month
        ORDER BY year_month
    """)
    result = await db.execute(sql, {"pid": provider_id})
    rows = result.fetchall()

    if len(rows) < 3:
        return 50.0, {"months_available": len(rows), "note": "insufficient history"}

    totals = [float(r.monthly_total) for r in rows]
    mean = sum(totals) / len(totals)
    if mean == 0:
        return 50.0, {"mean_subscribers": 0, "cv": None}

    variance = sum((x - mean) ** 2 for x in totals) / len(totals)
    std_dev = math.sqrt(variance)
    cv = std_dev / mean  # coefficient of variation

    # CV of 0 => score 100, CV of 1.0+ => score 0
    score = max(0.0, min(100.0, 100.0 * (1.0 - cv)))

    return round(score, 1), {
        "months_available": len(rows),
        "mean_subscribers": round(mean, 0),
        "std_dev": round(std_dev, 1),
        "cv": round(cv, 4),
    }


async def _compute_growth_trajectory(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """12-month subscriber growth trend.

    Compares latest month to the month 12 periods ago (or earliest available).
    Positive sustained growth scores higher.
    """
    sql = text("""
        SELECT year_month, SUM(subscribers) AS total
        FROM broadband_subscribers
        WHERE provider_id = :pid
        GROUP BY year_month
        ORDER BY year_month DESC
    """)
    result = await db.execute(sql, {"pid": provider_id})
    rows = result.fetchall()

    if len(rows) < 2:
        return 50.0, {"note": "insufficient history"}

    latest = float(rows[0].total)
    # Use the 12th month back, or the oldest available
    comparison_idx = min(11, len(rows) - 1)
    earlier = float(rows[comparison_idx].total)

    if earlier == 0:
        growth_pct = 100.0 if latest > 0 else 0.0
    else:
        growth_pct = ((latest - earlier) / earlier) * 100.0

    # Map growth to score: -50% or worse => 0, 0% => 50, +50% or more => 100
    score = max(0.0, min(100.0, 50.0 + growth_pct))

    return round(score, 1), {
        "latest_subscribers": int(latest),
        "comparison_subscribers": int(earlier),
        "months_span": comparison_idx + 1,
        "growth_pct": round(growth_pct, 2),
        "latest_month": rows[0].year_month.strip() if rows[0].year_month else None,
        "comparison_month": rows[comparison_idx].year_month.strip() if rows[comparison_idx].year_month else None,
    }


async def _compute_market_position(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """Market share rank in operating municipalities.

    Computes the average rank of this provider across its municipalities
    (by subscriber count in the latest month), then normalises.
    """
    sql = text("""
        WITH latest_month AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        provider_municipalities AS (
            SELECT DISTINCT l2_id
            FROM broadband_subscribers
            WHERE provider_id = :pid
              AND year_month = (SELECT ym FROM latest_month)
        ),
        ranked AS (
            SELECT
                bs.l2_id,
                bs.provider_id,
                SUM(bs.subscribers) AS total,
                RANK() OVER (
                    PARTITION BY bs.l2_id
                    ORDER BY SUM(bs.subscribers) DESC
                ) AS rnk,
                COUNT(*) OVER (PARTITION BY bs.l2_id) AS providers_in_muni
            FROM broadband_subscribers bs
            JOIN provider_municipalities pm ON bs.l2_id = pm.l2_id
            WHERE bs.year_month = (SELECT ym FROM latest_month)
            GROUP BY bs.l2_id, bs.provider_id
        )
        SELECT
            COUNT(*) AS municipalities,
            AVG(rnk) AS avg_rank,
            AVG(providers_in_muni) AS avg_providers,
            SUM(CASE WHEN rnk = 1 THEN 1 ELSE 0 END) AS top1_count,
            SUM(CASE WHEN rnk <= 3 THEN 1 ELSE 0 END) AS top3_count,
            SUM(total) AS total_subscribers
        FROM ranked
        WHERE provider_id = :pid
    """)
    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row or not row.municipalities or row.municipalities == 0:
        return 30.0, {"note": "no municipality data"}

    municipalities = int(row.municipalities)
    avg_rank = _to_float(row.avg_rank)
    avg_providers = max(1.0, _to_float(row.avg_providers))
    top1_pct = int(row.top1_count) / municipalities * 100
    top3_pct = int(row.top3_count) / municipalities * 100

    # Normalised rank score: rank 1 of N => 100, rank N of N => 0
    rank_score = max(0.0, (1.0 - (avg_rank - 1) / avg_providers) * 100.0)

    # Blend rank score with breadth bonus (more municipalities = better)
    breadth_bonus = min(20.0, municipalities / 5.0)
    score = min(100.0, rank_score * 0.7 + top1_pct * 0.15 + breadth_bonus * 0.15 / 20.0 * 100.0)

    return round(score, 1), {
        "municipalities": municipalities,
        "avg_rank": round(avg_rank, 2),
        "avg_providers_per_muni": round(avg_providers, 1),
        "top1_count": int(row.top1_count),
        "top3_count": int(row.top3_count),
        "top1_pct": round(top1_pct, 1),
        "top3_pct": round(top3_pct, 1),
        "total_subscribers": int(row.total_subscribers or 0),
    }


async def _compute_infrastructure_quality(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """Fiber percentage + average quality indicator score.

    Fiber share is weighted 60%, quality indicator average 40%.
    """
    # Fiber share
    fiber_sql = text("""
        WITH latest_month AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        )
        SELECT
            SUM(subscribers) AS total,
            SUM(CASE WHEN LOWER(technology) = 'fiber' THEN subscribers ELSE 0 END) AS fiber
        FROM broadband_subscribers
        WHERE provider_id = :pid
          AND year_month = (SELECT ym FROM latest_month)
    """)
    fiber_result = await db.execute(fiber_sql, {"pid": provider_id})
    fiber_row = fiber_result.fetchone()

    total_subs = _to_float(fiber_row.total) if fiber_row else 0.0
    fiber_subs = _to_float(fiber_row.fiber) if fiber_row else 0.0
    fiber_pct = (fiber_subs / total_subs * 100.0) if total_subs > 0 else 0.0

    # Quality indicators average for municipalities where this provider operates
    qi_sql = text("""
        WITH provider_munis AS (
            SELECT DISTINCT l2_id
            FROM broadband_subscribers
            WHERE provider_id = :pid
        )
        SELECT AVG(qi.value) AS avg_quality
        FROM quality_indicators qi
        JOIN provider_munis pm ON qi.l2_id = pm.l2_id
        WHERE qi.provider_id = :pid
    """)
    qi_result = await db.execute(qi_sql, {"pid": provider_id})
    qi_row = qi_result.fetchone()
    avg_quality = _to_float(qi_row.avg_quality) if qi_row and qi_row.avg_quality else 50.0

    # Normalise: fiber_pct is already 0-100; quality avg we cap at 100
    fiber_score = min(100.0, fiber_pct)
    quality_score = min(100.0, avg_quality)

    score = fiber_score * 0.6 + quality_score * 0.4

    return round(score, 1), {
        "fiber_pct": round(fiber_pct, 2),
        "fiber_subscribers": int(fiber_subs),
        "total_subscribers": int(total_subs),
        "avg_quality_indicator": round(avg_quality, 2),
    }


async def _compute_regulatory_compliance(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """Check regulatory licensing thresholds.

    Anatel thresholds: 5K subscribers requires SCM Class II,
    50K subscribers requires SCM Class I with additional obligations.
    Score penalised for providers near thresholds without evidence of
    compliance (proxy: check if they have quality_indicators data).
    """
    # Total subscribers
    subs_sql = text("""
        SELECT SUM(subscribers) AS total
        FROM broadband_subscribers
        WHERE provider_id = :pid
          AND year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
    """)
    subs_result = await db.execute(subs_sql, {"pid": provider_id})
    subs_row = subs_result.fetchone()
    total_subs = int(_to_float(subs_row.total)) if subs_row else 0

    # Check if provider has quality indicator data (proxy for compliance)
    qi_sql = text("""
        SELECT COUNT(*) AS qi_count
        FROM quality_indicators
        WHERE provider_id = :pid
    """)
    qi_result = await db.execute(qi_sql, {"pid": provider_id})
    qi_row = qi_result.fetchone()
    has_quality_data = (qi_row.qi_count or 0) > 0 if qi_row else False

    # Check provider status
    status_sql = text("""
        SELECT status, classification FROM providers WHERE id = :pid
    """)
    status_result = await db.execute(status_sql, {"pid": provider_id})
    status_row = status_result.fetchone()
    provider_status = status_row.status if status_row else None
    classification = status_row.classification if status_row else None

    score = 80.0  # base: assumed compliant
    factors_detail: dict[str, Any] = {
        "total_subscribers": total_subs,
        "has_quality_data": has_quality_data,
        "provider_status": provider_status,
        "classification": classification,
    }

    # Active status bonus
    if provider_status and "ativ" in str(provider_status).lower():
        score += 10.0
        factors_detail["active_bonus"] = True
    elif provider_status:
        score -= 20.0
        factors_detail["inactive_penalty"] = True

    # Quality data bonus (compliance with reporting obligations)
    if has_quality_data:
        score += 10.0
        factors_detail["quality_reporting_bonus"] = True

    # Threshold risk penalties
    if total_subs >= 50000 and not has_quality_data:
        score -= 25.0
        factors_detail["large_isp_no_quality_data_penalty"] = True
    elif total_subs >= 5000 and not has_quality_data:
        score -= 10.0
        factors_detail["mid_isp_no_quality_data_penalty"] = True

    score = max(0.0, min(100.0, score))

    return round(score, 1), factors_detail


async def _compute_subscriber_concentration(
    db: AsyncSession,
    provider_id: int,
) -> tuple[float, dict[str, Any]]:
    """Geographic HHI of subscriber distribution across municipalities.

    Lower HHI (more diversified) scores higher.
    HHI 10,000 (single municipality) => score 0.
    HHI near 0 (perfectly spread) => score 100.
    """
    sql = text("""
        WITH latest_month AS (
            SELECT MAX(year_month) AS ym FROM broadband_subscribers
        ),
        muni_subs AS (
            SELECT l2_id, SUM(subscribers) AS subs
            FROM broadband_subscribers
            WHERE provider_id = :pid
              AND year_month = (SELECT ym FROM latest_month)
            GROUP BY l2_id
        )
        SELECT
            COUNT(*) AS muni_count,
            SUM(subs) AS total_subs,
            SUM(subs * subs) AS sum_sq
        FROM muni_subs
    """)
    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    muni_count = int(row.muni_count or 0) if row else 0
    total_subs = _to_float(row.total_subs) if row else 0.0

    if muni_count <= 1 or total_subs == 0:
        hhi = 10000.0
        score = 0.0 if muni_count <= 1 else 50.0
        return round(score, 1), {
            "municipality_count": muni_count,
            "hhi": hhi,
            "note": "single municipality or no data",
        }

    sum_sq = _to_float(row.sum_sq) if row else 0.0
    # HHI = sum of squared market shares (each share in percentage points)
    hhi = (sum_sq / (total_subs * total_subs)) * 10000.0

    # Map HHI to score: 10000 => 0, 0 => 100
    score = max(0.0, min(100.0, 100.0 * (1.0 - hhi / 10000.0)))

    return round(score, 1), {
        "municipality_count": muni_count,
        "total_subscribers": int(total_subs),
        "hhi": round(hhi, 1),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Main computation
# ═══════════════════════════════════════════════════════════════════════════════


async def compute_credit_score(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Compute full credit assessment for a provider.

    Calculates six factor scores, combines them into a composite score,
    derives a letter rating and probability of default, then persists the
    result to ``isp_credit_scores``.

    Returns:
        Credit score dictionary with all factors and metadata.
    """
    # Verify provider exists
    provider_sql = text("SELECT id, name FROM providers WHERE id = :pid")
    provider_result = await db.execute(provider_sql, {"pid": provider_id})
    provider_row = provider_result.fetchone()

    if not provider_row:
        return {"error": "provider_not_found", "provider_id": provider_id}

    # Compute all six factors
    rev_score, rev_factors = await _compute_revenue_stability(db, provider_id)
    growth_score, growth_factors = await _compute_growth_trajectory(db, provider_id)
    market_score, market_factors = await _compute_market_position(db, provider_id)
    infra_score, infra_factors = await _compute_infrastructure_quality(db, provider_id)
    reg_score, reg_factors = await _compute_regulatory_compliance(db, provider_id)
    conc_score, conc_factors = await _compute_subscriber_concentration(db, provider_id)

    # Weighted composite score
    # Revenue stability and growth most important for creditworthiness
    weights = {
        "revenue_stability": 0.20,
        "growth_trajectory": 0.20,
        "market_position": 0.15,
        "infrastructure_quality": 0.15,
        "regulatory_compliance": 0.15,
        "subscriber_concentration": 0.15,
    }

    composite = (
        rev_score * weights["revenue_stability"]
        + growth_score * weights["growth_trajectory"]
        + market_score * weights["market_position"]
        + infra_score * weights["infrastructure_quality"]
        + reg_score * weights["regulatory_compliance"]
        + conc_score * weights["subscriber_concentration"]
    )
    composite = round(composite, 1)

    rating = _rating_from_score(composite)
    pd = _probability_of_default(composite)

    # Debt service ratio placeholder — derived from subscriber stability
    # (actual financials not available in Anatel data)
    debt_service_ratio = round(max(0.0, min(5.0, composite / 20.0)), 2)

    # Build factors JSONB
    factors = {
        "revenue_stability": rev_factors,
        "growth_trajectory": growth_factors,
        "market_position": market_factors,
        "infrastructure_quality": infra_factors,
        "regulatory_compliance": reg_factors,
        "subscriber_concentration": conc_factors,
        "weights": weights,
    }

    computed_at = datetime.now(timezone.utc)

    # Persist to isp_credit_scores
    upsert_sql = text("""
        INSERT INTO isp_credit_scores (
            provider_id, credit_rating, probability_of_default,
            revenue_stability, growth_trajectory, market_position,
            infrastructure_quality, regulatory_compliance,
            debt_service_ratio, subscriber_concentration,
            composite_score, factors, computed_at
        ) VALUES (
            :provider_id, :credit_rating, :probability_of_default,
            :revenue_stability, :growth_trajectory, :market_position,
            :infrastructure_quality, :regulatory_compliance,
            :debt_service_ratio, :subscriber_concentration,
            :composite_score, CAST(:factors AS jsonb), :computed_at
        )
        RETURNING id
    """)

    import json

    insert_result = await db.execute(upsert_sql, {
        "provider_id": provider_id,
        "credit_rating": rating,
        "probability_of_default": pd,
        "revenue_stability": rev_score,
        "growth_trajectory": growth_score,
        "market_position": market_score,
        "infrastructure_quality": infra_score,
        "regulatory_compliance": reg_score,
        "debt_service_ratio": debt_service_ratio,
        "subscriber_concentration": conc_score,
        "composite_score": composite,
        "factors": json.dumps(factors),
        "computed_at": computed_at,
    })
    record_id = insert_result.fetchone()

    return {
        "id": record_id.id if record_id else None,
        "provider_id": provider_id,
        "provider_name": provider_row.name,
        "credit_rating": rating,
        "composite_score": composite,
        "probability_of_default": pd,
        "debt_service_ratio": debt_service_ratio,
        "factor_scores": {
            "revenue_stability": rev_score,
            "growth_trajectory": growth_score,
            "market_position": market_score,
            "infrastructure_quality": infra_score,
            "regulatory_compliance": reg_score,
            "subscriber_concentration": conc_score,
        },
        "factors": factors,
        "computed_at": computed_at.isoformat(),
    }
