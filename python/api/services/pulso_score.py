"""
Pulso Score Computation Service

Computes a composite ISP health score (0-100) from seven sub-scores derived
from real Anatel broadband data, quality indicators, spectrum licenses,
BNDES loan access, and market structure metrics.

Sub-score weights:
    growth_score     (20%) — subscriber year-over-year growth percentile
    fiber_score      (15%) — fiber share of total subscribers
    quality_score    (15%) — averaged quality indicator values
    compliance_score (15%) — spectrum/licensing threshold coverage
    financial_score  (15%) — subscriber trend stability (revenue proxy)
    market_score     (10%) — market share across operating municipalities
    bndes_score      (10%) — BNDES telecom loan access indicator
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Weight configuration
WEIGHTS = {
    "growth": 0.20,
    "fiber": 0.15,
    "quality": 0.15,
    "compliance": 0.15,
    "financial": 0.15,
    "market": 0.10,
    "bndes": 0.10,
}

# Tier thresholds
TIER_MAP = [
    (90, "S"),
    (75, "A"),
    (60, "B"),
    (40, "C"),
    (0, "D"),
]


def _to_float(value: Any) -> float:
    """Safely convert Decimal/None to float."""
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _score_to_tier(score: float) -> str:
    for threshold, tier in TIER_MAP:
        if score >= threshold:
            return tier
    return "D"


# ═══════════════════════════════════════════════════════════════════════
# Individual sub-score computations
# ═══════════════════════════════════════════════════════════════════════


async def _compute_growth_score(db: AsyncSession, provider_id: int) -> float:
    """Growth score based on subscriber YoY growth rate.

    Compares latest month total subscribers to 12 months prior.
    Scores on a percentile-like scale: 0% growth = 30, 20%+ = 90, negative = 0-30.
    """
    sql = text("""
        WITH latest AS (
            SELECT year_month, SUM(subscribers) AS total
            FROM broadband_subscribers
            WHERE provider_id = :pid
            GROUP BY year_month
            ORDER BY year_month DESC
            LIMIT 1
        ),
        prior AS (
            SELECT year_month, SUM(subscribers) AS total
            FROM broadband_subscribers
            WHERE provider_id = :pid
              AND year_month <= (
                  SELECT CONCAT(
                      CAST(CAST(LEFT(year_month, 4) AS int) - 1 AS text),
                      '-',
                      RIGHT(year_month, 2)
                  )
                  FROM (
                      SELECT year_month
                      FROM broadband_subscribers
                      WHERE provider_id = :pid
                      GROUP BY year_month
                      ORDER BY year_month DESC
                      LIMIT 1
                  ) lm
              )
            GROUP BY year_month
            ORDER BY year_month DESC
            LIMIT 1
        )
        SELECT
            l.total AS latest_total,
            p.total AS prior_total
        FROM latest l
        LEFT JOIN prior p ON TRUE
    """)

    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row or not row.latest_total:
        return 0.0

    latest = _to_float(row.latest_total)
    prior = _to_float(row.prior_total) if row.prior_total else 0.0

    if prior <= 0:
        # No prior data; give a neutral score
        return 40.0

    growth_rate = (latest - prior) / prior

    if growth_rate < -0.20:
        return 0.0
    elif growth_rate < 0:
        # Declining: linear 0-30
        return _clamp(30.0 * (1.0 + growth_rate / 0.20))
    elif growth_rate < 0.20:
        # Moderate growth: linear 30-90
        return _clamp(30.0 + 60.0 * (growth_rate / 0.20))
    else:
        # Strong growth: 90-100
        return _clamp(90.0 + 10.0 * min(growth_rate - 0.20, 0.30) / 0.30)


async def _compute_fiber_score(db: AsyncSession, provider_id: int) -> float:
    """Fiber score based on fiber percentage of total subscribers.

    100% fiber = 100, 0% fiber = 0, linear interpolation.
    """
    sql = text("""
        SELECT
            SUM(subscribers) AS total,
            SUM(CASE WHEN LOWER(technology) = 'fiber' THEN subscribers ELSE 0 END) AS fiber
        FROM broadband_subscribers
        WHERE provider_id = :pid
          AND year_month = (
              SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid
          )
    """)

    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row or not row.total or row.total == 0:
        return 0.0

    fiber_pct = _to_float(row.fiber) / _to_float(row.total)
    return _clamp(fiber_pct * 100.0)


async def _compute_quality_score(db: AsyncSession, provider_id: int) -> float:
    """Quality score from quality_indicators table.

    Uses broadband_penetration_pct, fiber_penetration_pct, technology_diversity,
    and yoy_growth_pct metrics for the provider's operating municipalities.
    Falls back to municipality-level data linked via broadband_subscribers.
    """
    # Direct provider quality indicators
    sql = text("""
        SELECT AVG(qi.value) AS avg_value, COUNT(*) AS cnt
        FROM quality_indicators qi
        WHERE qi.provider_id = :pid
          AND qi.metric_type IN (
              'broadband_penetration_pct', 'fiber_penetration_pct',
              'technology_diversity', 'yoy_growth_pct'
          )
    """)
    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if row and row.cnt and row.cnt > 0 and row.avg_value is not None:
        # Normalize: avg_value is in varying units, but penetration ~0-100
        # Use a sigmoid-like mapping capped at 100
        avg = _to_float(row.avg_value)
        return _clamp(min(avg, 100.0))

    # Fallback: quality indicators for municipalities where provider operates
    sql_fallback = text("""
        SELECT AVG(qi.value) AS avg_value
        FROM quality_indicators qi
        WHERE qi.l2_id IN (
            SELECT DISTINCT l2_id FROM broadband_subscribers WHERE provider_id = :pid
        )
        AND qi.metric_type IN (
            'broadband_penetration_pct', 'fiber_penetration_pct',
            'technology_diversity'
        )
    """)
    result = await db.execute(sql_fallback, {"pid": provider_id})
    row = result.fetchone()

    if row and row.avg_value is not None:
        avg = _to_float(row.avg_value)
        return _clamp(min(avg, 100.0))

    return 30.0  # Default neutral for providers with no quality data


async def _compute_compliance_score(db: AsyncSession, provider_id: int) -> float:
    """Compliance score based on licensing and spectrum coverage.

    Factors:
    - Has active provider status: +30 points
    - Has spectrum licenses: +30 points
    - Has quality seals: +20 points
    - Services breadth (SCM, STFC, etc.): up to +20 points
    """
    score = 0.0

    # Provider status check
    prov_sql = text("""
        SELECT status, services, classification
        FROM providers
        WHERE id = :pid
    """)
    result = await db.execute(prov_sql, {"pid": provider_id})
    prov = result.fetchone()

    if prov:
        if prov.status and prov.status.lower() == 'active':
            score += 30.0

        # Services breadth
        if prov.services:
            services = prov.services if isinstance(prov.services, list) else []
            if isinstance(prov.services, dict):
                services = list(prov.services.keys())
            service_count = len(services)
            score += min(service_count * 5.0, 20.0)

    # Spectrum licenses
    spec_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM spectrum_licenses
        WHERE provider_id = :pid
    """)
    result = await db.execute(spec_sql, {"pid": provider_id})
    spec = result.fetchone()
    if spec and spec.cnt > 0:
        score += 30.0

    # Quality seals
    seal_sql = text("""
        SELECT COUNT(*) AS cnt
        FROM quality_seals
        WHERE provider_id = :pid
    """)
    try:
        result = await db.execute(seal_sql, {"pid": provider_id})
        seal = result.fetchone()
        if seal and seal.cnt > 0:
            score += 20.0
    except Exception:
        # quality_seals may not exist for all providers
        pass

    return _clamp(score)


async def _compute_financial_score(db: AsyncSession, provider_id: int) -> float:
    """Financial score based on subscriber trend stability.

    Measures coefficient of variation of monthly subscriber counts
    over the last 12 months. Lower variance = more stable = higher score.
    Also rewards absolute subscriber scale.
    """
    sql = text("""
        SELECT year_month, SUM(subscribers) AS total
        FROM broadband_subscribers
        WHERE provider_id = :pid
        GROUP BY year_month
        ORDER BY year_month DESC
        LIMIT 12
    """)

    result = await db.execute(sql, {"pid": provider_id})
    rows = result.fetchall()

    if not rows or len(rows) < 2:
        return 20.0  # Too few data points

    totals = [_to_float(r.total) for r in rows if r.total]
    if not totals:
        return 0.0

    mean = sum(totals) / len(totals)
    if mean <= 0:
        return 0.0

    variance = sum((t - mean) ** 2 for t in totals) / len(totals)
    std_dev = variance ** 0.5
    cv = std_dev / mean  # Coefficient of variation

    # Low CV (stable) = high score. CV < 0.05 = 90+, CV > 0.50 = 10
    stability_score = _clamp(90.0 - (cv * 160.0), 10.0, 90.0)

    # Scale bonus: larger providers get a slight bonus (up to 10 points)
    # Log scale: 1000 subs = +3, 10000 = +6, 100000 = +10
    import math
    scale_bonus = min(10.0, max(0.0, math.log10(max(mean, 1)) - 1.0) * 3.33)

    return _clamp(stability_score + scale_bonus)


async def _compute_market_score(db: AsyncSession, provider_id: int) -> float:
    """Market score based on market share in operating municipalities.

    Averages the provider's share across all municipalities where it operates.
    High share in few municipalities or moderate share in many both score well.
    """
    sql = text("""
        WITH provider_subs AS (
            SELECT l2_id, SUM(subscribers) AS prov_total
            FROM broadband_subscribers
            WHERE provider_id = :pid
              AND year_month = (
                  SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid
              )
            GROUP BY l2_id
        ),
        market_totals AS (
            SELECT bs.l2_id, SUM(bs.subscribers) AS market_total
            FROM broadband_subscribers bs
            WHERE bs.l2_id IN (SELECT l2_id FROM provider_subs)
              AND bs.year_month = (
                  SELECT MAX(year_month) FROM broadband_subscribers WHERE provider_id = :pid
              )
            GROUP BY bs.l2_id
        )
        SELECT
            COUNT(ps.l2_id) AS municipality_count,
            AVG(
                CASE WHEN mt.market_total > 0
                     THEN ps.prov_total::float / mt.market_total
                     ELSE 0
                END
            ) AS avg_share,
            SUM(ps.prov_total) AS total_subs
        FROM provider_subs ps
        JOIN market_totals mt ON ps.l2_id = mt.l2_id
    """)

    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row or not row.municipality_count or row.municipality_count == 0:
        return 0.0

    avg_share = _to_float(row.avg_share)
    muni_count = int(row.municipality_count)

    # Share component: 50% market share = 50 points, linear
    share_score = avg_share * 100.0

    # Reach component: operating in more municipalities adds up to 30 points
    import math
    reach_bonus = min(30.0, math.log10(max(muni_count, 1)) * 15.0)

    # Combine: 70% share, 30% reach
    return _clamp(share_score * 0.7 + reach_bonus)


async def _compute_bndes_score(db: AsyncSession, provider_id: int) -> float:
    """BNDES score based on telecom loan access.

    Checks if the provider (or its operating municipalities) has received
    BNDES telecom loans. Having loans indicates financial credibility and
    infrastructure investment capacity.
    """
    # Direct provider BNDES loans
    direct_sql = text("""
        SELECT COUNT(*) AS cnt, COALESCE(SUM(contract_value_brl), 0) AS total_brl
        FROM bndes_loans
        WHERE provider_id = :pid
    """)
    result = await db.execute(direct_sql, {"pid": provider_id})
    row = result.fetchone()

    if row and row.cnt and row.cnt > 0:
        total = _to_float(row.total_brl)
        # Has direct BNDES loans: base 60, scale by amount
        import math
        amount_bonus = min(40.0, math.log10(max(total, 1)) / 8.0 * 40.0)
        return _clamp(60.0 + amount_bonus)

    # Indirect: BNDES loans in municipalities where provider operates
    indirect_sql = text("""
        SELECT COUNT(DISTINCT bl.id) AS loan_count
        FROM bndes_loans bl
        WHERE bl.l2_id IN (
            SELECT DISTINCT l2_id
            FROM broadband_subscribers
            WHERE provider_id = :pid
        )
        AND bl.sector ILIKE '%telecom%'
    """)
    result = await db.execute(indirect_sql, {"pid": provider_id})
    row = result.fetchone()

    if row and row.loan_count and row.loan_count > 0:
        # Indirect association: up to 50 points
        return _clamp(min(50.0, 20.0 + row.loan_count * 5.0))

    return 15.0  # No BNDES association, baseline score


# ═══════════════════════════════════════════════════════════════════════
# Main score computation
# ═══════════════════════════════════════════════════════════════════════


async def compute_provider_score(
    db: AsyncSession,
    provider_id: int,
) -> dict[str, Any]:
    """Compute composite Pulso Score for a single provider.

    Returns a dictionary with all sub-scores, composite score, tier, and metadata.
    """
    # Verify provider exists
    prov_sql = text("SELECT id, name FROM providers WHERE id = :pid")
    result = await db.execute(prov_sql, {"pid": provider_id})
    provider = result.fetchone()
    if not provider:
        return {"error": "Provider not found", "provider_id": provider_id}

    # Compute all sub-scores in sequence (each is a DB query)
    growth = await _compute_growth_score(db, provider_id)
    fiber = await _compute_fiber_score(db, provider_id)
    quality = await _compute_quality_score(db, provider_id)
    compliance = await _compute_compliance_score(db, provider_id)
    financial = await _compute_financial_score(db, provider_id)
    market = await _compute_market_score(db, provider_id)
    bndes = await _compute_bndes_score(db, provider_id)

    # Weighted composite
    composite = (
        growth * WEIGHTS["growth"]
        + fiber * WEIGHTS["fiber"]
        + quality * WEIGHTS["quality"]
        + compliance * WEIGHTS["compliance"]
        + financial * WEIGHTS["financial"]
        + market * WEIGHTS["market"]
        + bndes * WEIGHTS["bndes"]
    )
    composite = round(_clamp(composite), 2)

    tier = _score_to_tier(composite)

    # Fetch previous score for delta
    prev_sql = text("""
        SELECT score, computed_at
        FROM pulso_scores
        WHERE provider_id = :pid
        ORDER BY computed_at DESC
        LIMIT 1
    """)
    result = await db.execute(prev_sql, {"pid": provider_id})
    prev_row = result.fetchone()
    previous_score = _to_float(prev_row.score) if prev_row else None
    score_change = round(composite - previous_score, 2) if previous_score is not None else None

    return {
        "provider_id": provider_id,
        "provider_name": provider.name,
        "score": composite,
        "growth_score": round(growth, 2),
        "fiber_score": round(fiber, 2),
        "quality_score": round(quality, 2),
        "compliance_score": round(compliance, 2),
        "financial_score": round(financial, 2),
        "market_score": round(market, 2),
        "bndes_score": round(bndes, 2),
        "tier": tier,
        "previous_score": previous_score,
        "score_change": score_change,
        "computed_at": datetime.utcnow().isoformat(),
        "weights": WEIGHTS,
    }


async def save_provider_score(
    db: AsyncSession,
    score_data: dict[str, Any],
) -> int:
    """Persist a computed score to the pulso_scores table.

    Returns the inserted row id.
    """
    sql = text("""
        INSERT INTO pulso_scores (
            provider_id, score, growth_score, fiber_score, quality_score,
            compliance_score, financial_score, market_score, bndes_score,
            tier, previous_score, score_change, computed_at
        ) VALUES (
            :provider_id, :score, :growth_score, :fiber_score, :quality_score,
            :compliance_score, :financial_score, :market_score, :bndes_score,
            :tier, :previous_score, :score_change, NOW()
        )
        RETURNING id
    """)

    result = await db.execute(sql, {
        "provider_id": score_data["provider_id"],
        "score": score_data["score"],
        "growth_score": score_data["growth_score"],
        "fiber_score": score_data["fiber_score"],
        "quality_score": score_data["quality_score"],
        "compliance_score": score_data["compliance_score"],
        "financial_score": score_data["financial_score"],
        "market_score": score_data["market_score"],
        "bndes_score": score_data["bndes_score"],
        "tier": score_data["tier"],
        "previous_score": score_data["previous_score"],
        "score_change": score_data["score_change"],
    })
    row = result.fetchone()
    await db.commit()
    return row.id if row else 0


async def get_provider_score(
    db: AsyncSession,
    provider_id: int,
) -> Optional[dict[str, Any]]:
    """Fetch the latest computed score for a provider."""
    sql = text("""
        SELECT ps.*, p.name AS provider_name
        FROM pulso_scores ps
        JOIN providers p ON ps.provider_id = p.id
        WHERE ps.provider_id = :pid
        ORDER BY ps.computed_at DESC
        LIMIT 1
    """)

    result = await db.execute(sql, {"pid": provider_id})
    row = result.fetchone()

    if not row:
        return None

    return {
        "provider_id": row.provider_id,
        "provider_name": row.provider_name,
        "score": _to_float(row.score),
        "growth_score": _to_float(row.growth_score),
        "fiber_score": _to_float(row.fiber_score),
        "quality_score": _to_float(row.quality_score),
        "compliance_score": _to_float(row.compliance_score),
        "financial_score": _to_float(row.financial_score),
        "market_score": _to_float(row.market_score),
        "bndes_score": _to_float(row.bndes_score),
        "tier": row.tier,
        "rank": row.rank,
        "previous_score": _to_float(row.previous_score) if row.previous_score else None,
        "score_change": _to_float(row.score_change) if row.score_change else None,
        "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        "weights": WEIGHTS,
    }


async def get_ranking(
    db: AsyncSession,
    state: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get provider ranking by Pulso Score.

    Uses DISTINCT ON to pick each provider's latest score, then ranks.
    Optionally filters by state (via broadband_subscribers geography)
    or tier.
    """
    where_clauses = []
    params: dict[str, Any] = {"limit": limit}

    if tier:
        where_clauses.append("ranked.tier = :tier")
        params["tier"] = tier.upper()

    if state:
        where_clauses.append("""
            ranked.provider_id IN (
                SELECT DISTINCT bs.provider_id
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON bs.l2_id = a2.id
                JOIN admin_level_1 a1 ON a2.l1_id = a1.id
                WHERE a1.abbrev = :state
            )
        """)
        params["state"] = state.upper()

    where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    sql = text(f"""
        SELECT * FROM (
            SELECT DISTINCT ON (ps.provider_id)
                ps.provider_id,
                p.name AS provider_name,
                ps.score,
                ps.growth_score,
                ps.fiber_score,
                ps.quality_score,
                ps.compliance_score,
                ps.financial_score,
                ps.market_score,
                ps.bndes_score,
                ps.tier,
                ps.rank,
                ps.previous_score,
                ps.score_change,
                ps.computed_at
            FROM pulso_scores ps
            JOIN providers p ON ps.provider_id = p.id
            ORDER BY ps.provider_id, ps.computed_at DESC
        ) ranked
        {where_sql}
        ORDER BY ranked.score DESC
        LIMIT :limit
    """)

    result = await db.execute(sql, params)
    rows = result.fetchall()

    return [
        {
            "rank": idx + 1,
            "provider_id": row.provider_id,
            "provider_name": row.provider_name,
            "score": _to_float(row.score),
            "growth_score": _to_float(row.growth_score),
            "fiber_score": _to_float(row.fiber_score),
            "quality_score": _to_float(row.quality_score),
            "compliance_score": _to_float(row.compliance_score),
            "financial_score": _to_float(row.financial_score),
            "market_score": _to_float(row.market_score),
            "bndes_score": _to_float(row.bndes_score),
            "tier": row.tier,
            "previous_score": _to_float(row.previous_score) if row.previous_score else None,
            "score_change": _to_float(row.score_change) if row.score_change else None,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for idx, row in enumerate(rows)
    ]


async def get_distribution(db: AsyncSession) -> dict[str, Any]:
    """Get tier distribution statistics from latest scores."""
    sql = text("""
        WITH latest_scores AS (
            SELECT DISTINCT ON (provider_id)
                provider_id, score, tier
            FROM pulso_scores
            ORDER BY provider_id, computed_at DESC
        )
        SELECT
            tier,
            COUNT(*) AS count,
            ROUND(AVG(score)::numeric, 2) AS avg_score,
            ROUND(MIN(score)::numeric, 2) AS min_score,
            ROUND(MAX(score)::numeric, 2) AS max_score
        FROM latest_scores
        GROUP BY tier
        ORDER BY
            CASE tier
                WHEN 'S' THEN 1
                WHEN 'A' THEN 2
                WHEN 'B' THEN 3
                WHEN 'C' THEN 4
                WHEN 'D' THEN 5
            END
    """)

    result = await db.execute(sql)
    rows = result.fetchall()

    total_sql = text("""
        SELECT COUNT(DISTINCT provider_id) AS total
        FROM pulso_scores
    """)
    total_result = await db.execute(total_sql)
    total_row = total_result.fetchone()
    total = int(total_row.total) if total_row else 0

    tiers = {}
    for row in rows:
        tiers[row.tier] = {
            "count": int(row.count),
            "percentage": round(int(row.count) / total * 100, 2) if total > 0 else 0,
            "avg_score": _to_float(row.avg_score),
            "min_score": _to_float(row.min_score),
            "max_score": _to_float(row.max_score),
        }

    return {
        "total_providers_scored": total,
        "tiers": tiers,
    }
