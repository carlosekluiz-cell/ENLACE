"""Maintenance priority scoring.

For each municipality where an ISP operates, compute maintenance priority:

FACTORS:
1. Weather risk (from weather_correlation): 0-100
2. Infrastructure age proxy: first Anatel appearance -> deployment age
3. Quality trend: declining quality = higher priority
4. Revenue at risk: subscriber_count x ARPU
5. Competitive pressure: competitor quality improving while ISP declining

COMPOSITE SCORE:
priority = 0.3 x weather_risk + 0.2 x age_score + 0.2 x quality_trend
         + 0.2 x revenue_risk + 0.1 x competitive_pressure
"""

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG
from python.ml.health.quality_benchmark import (
    QualityBenchmark,
    benchmark_quality,
    compute_trend,
)
from python.ml.health.weather_correlation import WeatherRisk, compute_weather_risk

logger = logging.getLogger(__name__)

# Default Brazilian ISP ARPU (source: Anatel 2025 market reports)
DEFAULT_ARPU_BRL = 89.90

# Weights for composite priority score
WEIGHT_WEATHER = 0.30
WEIGHT_AGE = 0.20
WEIGHT_QUALITY = 0.20
WEIGHT_REVENUE = 0.20
WEIGHT_COMPETITION = 0.10

# Revenue normalisation: monthly revenue that maps to score = 100
# A municipality generating R$ 500k/month in revenue is maximum priority
MAX_REVENUE_BRL = 500_000.0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MaintenancePriority:
    """Maintenance priority assessment for a municipality."""

    municipality_id: int
    municipality_name: str
    priority_score: float  # 0-100
    weather_risk_score: float
    infrastructure_age_score: float
    quality_trend_score: float
    revenue_risk_score: float
    competitive_pressure_score: float
    recommended_action: str
    timing: str  # "immediate", "within_7_days", "within_30_days", "routine"
    details: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Sub-score computation
# ---------------------------------------------------------------------------


def compute_age_score(first_seen_date: Optional[date], current_date: Optional[date] = None) -> float:
    """Score infrastructure age. 0 = new (< 2 yr), 100 = old (> 8 yr).

    Older infrastructure has higher failure probability due to material
    fatigue, weathering, and accumulated micro-damage.

    Args:
        first_seen_date: The date the provider first appeared in Anatel data
            for this municipality.  Used as a proxy for deployment date.
        current_date: Reference date (defaults to today).

    Returns:
        Score 0-100 where higher = older = higher maintenance priority.
    """
    if first_seen_date is None:
        # Unknown age: assume moderate age (4 years)
        return 50.0

    if current_date is None:
        current_date = date.today()

    age_years = (current_date - first_seen_date).days / 365.25

    if age_years >= 8:
        return 100.0
    if age_years <= 2:
        return max(0.0, age_years / 2.0 * 25.0)

    # Linear interpolation from 2yr (25) to 8yr (100)
    return 25.0 + (age_years - 2.0) / 6.0 * 75.0


def compute_revenue_risk(
    subscriber_count: int, arpu_brl: float = DEFAULT_ARPU_BRL,
) -> float:
    """Score revenue at risk. Normalised 0-100 based on monthly revenue.

    Higher subscriber count x ARPU = more revenue at risk if a fault
    occurs, thus higher priority for preventive maintenance.

    Args:
        subscriber_count: Total subscribers in the municipality.
        arpu_brl: Average revenue per user per month in BRL.

    Returns:
        Score 0-100.
    """
    if subscriber_count <= 0:
        return 0.0

    monthly_revenue = subscriber_count * arpu_brl
    # Logarithmic scaling: small municipalities still get some score
    # but large ones are strongly prioritised
    if monthly_revenue >= MAX_REVENUE_BRL:
        return 100.0

    # log scale: revenue R$1k -> ~20, R$50k -> ~65, R$200k -> ~85
    import math

    score = math.log10(max(monthly_revenue, 1.0)) / math.log10(MAX_REVENUE_BRL) * 100.0
    return round(min(100.0, max(0.0, score)), 2)


def _compute_quality_trend_score(benchmark: Optional[QualityBenchmark]) -> float:
    """Convert quality trend into a maintenance priority score.

    Degrading quality = high priority.  Stable or improving = low priority.

    Returns 0-100.
    """
    if benchmark is None:
        return 30.0  # Unknown: moderate default

    if benchmark.trend == "degrading":
        # Scale by magnitude: bigger drop = higher score
        base = 60.0
        magnitude_bonus = min(40.0, abs(benchmark.trend_pct) * 2)
        return min(100.0, base + magnitude_bonus)
    if benchmark.trend == "stable":
        return 20.0
    # improving
    return 5.0


def _compute_competitive_pressure(
    provider_id: int,
    municipality_id: int,
    benchmark: Optional[QualityBenchmark],
    conn,
) -> float:
    """Score competitive pressure (0-100).

    High pressure when:
    - ISP quality is degrading while competitors improve
    - ISP quality is below peer average
    - ISP is an outlier (> 2 stddev below peers)

    Args:
        provider_id: The provider being assessed.
        municipality_id: The municipality.
        benchmark: Pre-computed benchmark, or None.
        conn: Database connection.

    Returns:
        Score 0-100.
    """
    if benchmark is None:
        return 25.0  # Moderate default

    score = 0.0

    # Below peer average
    if benchmark.peer_avg > 0 and benchmark.current_ida < benchmark.peer_avg:
        gap_pct = (benchmark.peer_avg - benchmark.current_ida) / benchmark.peer_avg * 100
        score += min(40.0, gap_pct * 4)

    # Outlier penalty
    if benchmark.is_outlier:
        score += 30.0

    # Degrading while below average is doubly bad
    if benchmark.trend == "degrading" and benchmark.percentile < 50:
        score += 20.0

    # Check if any competitor in the same municipality is improving
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT qi.provider_id, qi.year_month, AVG(qi.value) AS avg_val
                FROM quality_indicators qi
                WHERE qi.l2_id = %s
                  AND qi.provider_id != %s
                GROUP BY qi.provider_id, qi.year_month
                ORDER BY qi.provider_id, qi.year_month
                """,
                (municipality_id, provider_id),
            )
            rows = cur.fetchall()

        # Group by competitor
        competitor_series: dict[int, list[float]] = {}
        for pid, ym, val in rows:
            competitor_series.setdefault(pid, []).append(float(val))

        # If any competitor is improving, add pressure
        for pid, values in competitor_series.items():
            trend_dir, _ = compute_trend(values[-12:])  # Last 12 months
            if trend_dir == "improving":
                score += 10.0
                break  # One improving competitor is enough
    except Exception as exc:
        logger.debug(
            "Could not check competitor trends for municipality %d: %s",
            municipality_id, exc,
        )

    return min(100.0, score)


def _fetch_subscriber_count(
    provider_id: int, municipality_id: int, conn,
) -> int:
    """Fetch current subscriber count for a provider in a municipality."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COALESCE(SUM(subscribers), 0)
            FROM broadband_subscribers
            WHERE provider_id = %s
              AND l2_id = %s
              AND year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
            """,
            (provider_id, municipality_id),
        )
        row = cur.fetchone()
    return int(row[0]) if row and row[0] else 0


def _fetch_first_seen(provider_id: int, municipality_id: int, conn) -> Optional[date]:
    """Determine when a provider first appeared in a municipality.

    Uses the earliest year_month in quality_indicators or
    broadband_subscribers as a proxy for deployment date.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT MIN(year_month) FROM (
                SELECT year_month FROM quality_indicators
                WHERE provider_id = %s AND l2_id = %s
                UNION ALL
                SELECT year_month FROM broadband_subscribers
                WHERE provider_id = %s AND l2_id = %s
            ) combined
            """,
            (provider_id, municipality_id, provider_id, municipality_id),
        )
        row = cur.fetchone()

    if not row or not row[0]:
        return None

    # year_month is 'YYYY-MM'; convert to date (first of month)
    try:
        parts = row[0].split("-")
        return date(int(parts[0]), int(parts[1]), 1)
    except (ValueError, IndexError):
        return None


# ---------------------------------------------------------------------------
# Recommended actions
# ---------------------------------------------------------------------------


def recommend_action(priority: MaintenancePriority) -> str:
    """Generate recommended maintenance action based on top risk factor.

    Identifies which factor contributes most to the priority score and
    returns a domain-specific recommendation.

    Args:
        priority: The computed maintenance priority.

    Returns:
        Human-readable recommendation string.
    """
    factor_scores = {
        "weather": priority.weather_risk_score * WEIGHT_WEATHER,
        "age": priority.infrastructure_age_score * WEIGHT_AGE,
        "quality": priority.quality_trend_score * WEIGHT_QUALITY,
        "revenue": priority.revenue_risk_score * WEIGHT_REVENUE,
        "competition": priority.competitive_pressure_score * WEIGHT_COMPETITION,
    }

    top_factor = max(factor_scores, key=factor_scores.get)

    recommendations = {
        "weather": (
            "Pre-position splice repair crew and spare materials. "
            "Inspect aerial cable routes for vegetation clearance."
        ),
        "age": (
            "Schedule preventive maintenance inspection. "
            "Prioritise OTDR testing on oldest cable segments."
        ),
        "quality": (
            "Investigate quality degradation root cause. "
            "Check for packet loss at aggregation switches and OLT ports."
        ),
        "revenue": (
            "Prioritise customer retention program. "
            "Deploy proactive monitoring on high-revenue access nodes."
        ),
        "competition": (
            "Assess competitive response. Consider speed tier upgrades "
            "and proactive customer outreach in affected areas."
        ),
    }

    return recommendations.get(top_factor, "Schedule routine maintenance inspection.")


def _determine_timing(score: float) -> str:
    """Map priority score to action timing."""
    if score >= 80:
        return "immediate"
    if score >= 60:
        return "within_7_days"
    if score >= 40:
        return "within_30_days"
    return "routine"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_maintenance_priorities(
    provider_id: int,
    municipality_id: int = None,
    conn=None,
) -> list[MaintenancePriority]:
    """Compute maintenance priorities for all municipalities of a provider.

    Orchestrates weather risk, quality benchmarking, infrastructure age,
    revenue-at-risk, and competitive pressure sub-scores into a composite
    priority score for each municipality.

    Args:
        provider_id: providers.id
        municipality_id: Optional single municipality to assess.
        conn: Optional database connection.

    Returns:
        List of MaintenancePriority sorted by priority_score descending
        (highest priority first).
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return []

    try:
        # Step 1: Get quality benchmarks for all municipalities
        benchmarks = benchmark_quality(
            provider_id=provider_id,
            municipality_id=municipality_id,
            months=12,
            conn=conn,
        )

        # Build lookup: municipality_id -> benchmark
        benchmark_map: dict[int, QualityBenchmark] = {
            b.municipality_id: b for b in benchmarks
        }

        # If no benchmarks found but municipality_id given, still proceed
        if municipality_id is not None:
            muni_ids = list({municipality_id} | set(benchmark_map.keys()))
        else:
            # Get all municipalities where provider has subscribers
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT l2_id
                    FROM broadband_subscribers
                    WHERE provider_id = %s
                      AND l2_id IS NOT NULL
                      AND year_month = (
                        SELECT MAX(year_month) FROM broadband_subscribers
                      )
                    """,
                    (provider_id,),
                )
                sub_munis = {row[0] for row in cur.fetchall()}
            muni_ids = list(sub_munis | set(benchmark_map.keys()))

        if not muni_ids:
            logger.info(
                "No municipalities found for provider %d", provider_id,
            )
            return []

        results: list[MaintenancePriority] = []

        for m_id in muni_ids:
            try:
                result = _compute_single_priority(
                    provider_id=provider_id,
                    municipality_id=m_id,
                    benchmark=benchmark_map.get(m_id),
                    conn=conn,
                )
                results.append(result)
            except Exception as exc:
                logger.warning(
                    "Failed to compute priority for municipality %d: %s",
                    m_id, exc,
                )

        # Sort highest priority first
        results.sort(key=lambda p: p.priority_score, reverse=True)

        logger.info(
            "Computed maintenance priorities for %d municipalities "
            "(provider %d): %d immediate, %d within_7_days",
            len(results),
            provider_id,
            sum(1 for r in results if r.timing == "immediate"),
            sum(1 for r in results if r.timing == "within_7_days"),
        )

        return results

    except Exception as exc:
        logger.error(
            "Error computing maintenance priorities for provider %d: %s",
            provider_id, exc,
        )
        return []
    finally:
        if own_conn:
            conn.close()


def _compute_single_priority(
    provider_id: int,
    municipality_id: int,
    benchmark: Optional[QualityBenchmark],
    conn,
) -> MaintenancePriority:
    """Compute maintenance priority for a single municipality."""

    # Municipality name
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM admin_level_2 WHERE id = %s",
            (municipality_id,),
        )
        row = cur.fetchone()
    muni_name = row[0] if row else f"Municipality {municipality_id}"

    # --- Weather risk ---
    weather_risk: WeatherRisk = compute_weather_risk(municipality_id, conn)
    weather_score = weather_risk.overall_risk_score

    # --- Infrastructure age ---
    first_seen = _fetch_first_seen(provider_id, municipality_id, conn)
    age_score = compute_age_score(first_seen)

    # --- Quality trend ---
    quality_score = _compute_quality_trend_score(benchmark)

    # --- Revenue at risk ---
    subs = _fetch_subscriber_count(provider_id, municipality_id, conn)
    revenue_score = compute_revenue_risk(subs)

    # --- Competitive pressure ---
    comp_score = _compute_competitive_pressure(
        provider_id, municipality_id, benchmark, conn,
    )

    # --- Composite score ---
    priority_score = (
        WEIGHT_WEATHER * weather_score
        + WEIGHT_AGE * age_score
        + WEIGHT_QUALITY * quality_score
        + WEIGHT_REVENUE * revenue_score
        + WEIGHT_COMPETITION * comp_score
    )
    priority_score = round(min(100.0, max(0.0, priority_score)), 2)

    timing = _determine_timing(priority_score)

    # Build result
    mp = MaintenancePriority(
        municipality_id=municipality_id,
        municipality_name=muni_name,
        priority_score=priority_score,
        weather_risk_score=round(weather_score, 2),
        infrastructure_age_score=round(age_score, 2),
        quality_trend_score=round(quality_score, 2),
        revenue_risk_score=round(revenue_score, 2),
        competitive_pressure_score=round(comp_score, 2),
        recommended_action="",  # filled below
        timing=timing,
        details={
            "subscriber_count": subs,
            "first_seen": str(first_seen) if first_seen else None,
            "weather_details": weather_risk.details,
            "benchmark_trend": benchmark.trend if benchmark else None,
            "benchmark_trend_pct": benchmark.trend_pct if benchmark else None,
        },
    )

    mp.recommended_action = recommend_action(mp)

    logger.debug(
        "Priority for %s (muni=%d, provider=%d): score=%.1f timing=%s "
        "[weather=%.1f age=%.1f quality=%.1f revenue=%.1f comp=%.1f]",
        muni_name,
        municipality_id,
        provider_id,
        priority_score,
        timing,
        weather_score,
        age_score,
        quality_score,
        revenue_score,
        comp_score,
    )

    return mp
