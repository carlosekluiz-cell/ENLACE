"""Regional ARPU (Average Revenue Per User) estimation for Brazilian broadband.

Estimates blended ARPU based on technology, regional income levels, and
competitive pressure.  Price benchmarks are derived from public Anatel data
and BNDES/Abrint market reports.
"""

import logging
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Brazilian broadband price benchmarks (BRL/month, 2025-2026 reference)
# ---------------------------------------------------------------------------
PRICE_BENCHMARKS = {
    "fiber": {"basic": 79.90, "mid": 129.90, "premium": 199.90},
    "fwa":   {"basic": 69.90, "mid": 109.90, "premium": 149.90},
    "dsl":   {"basic": 59.90, "mid": 89.90,  "premium": 129.90},
}

# Income thresholds for plan mix (monthly household income in BRL)
# These roughly correspond to IBGE social class boundaries
INCOME_THRESHOLDS = {
    "low":     2500.0,   # Mostly basic plans
    "mid_low": 4000.0,   # Mix of basic and mid
    "mid":     7000.0,   # Mix of mid and premium
    "high":    12000.0,  # Mostly premium plans
}

# Competition adjustment factors (applied to ARPU)
COMPETITION_ADJUSTMENTS = {
    0: 1.05,    # No competitors — can charge a slight premium
    1: 1.00,    # One competitor — standard pricing
    2: 0.95,    # Two competitors — mild price pressure
    3: 0.90,    # Three competitors — noticeable price pressure
    4: 0.85,    # Four competitors — heavy price war territory
}


def _estimate_plan_mix(household_income_brl: float) -> dict:
    """Estimate the fraction of subscribers on each plan tier.

    Args:
        household_income_brl: Estimated average monthly household income.

    Returns:
        Dict with keys 'basic', 'mid', 'premium' summing to 1.0.
    """
    if household_income_brl <= INCOME_THRESHOLDS["low"]:
        return {"basic": 0.70, "mid": 0.25, "premium": 0.05}
    elif household_income_brl <= INCOME_THRESHOLDS["mid_low"]:
        return {"basic": 0.50, "mid": 0.35, "premium": 0.15}
    elif household_income_brl <= INCOME_THRESHOLDS["mid"]:
        return {"basic": 0.25, "mid": 0.45, "premium": 0.30}
    elif household_income_brl <= INCOME_THRESHOLDS["high"]:
        return {"basic": 0.10, "mid": 0.40, "premium": 0.50}
    else:
        return {"basic": 0.05, "mid": 0.30, "premium": 0.65}


def _get_competition_factor(provider_count: int) -> float:
    """Return a multiplier for ARPU based on number of competitors.

    More competitors create downward price pressure.
    """
    if provider_count >= 5:
        return 0.80
    return COMPETITION_ADJUSTMENTS.get(provider_count, 0.90)


def _lookup_provider_count(municipality_code: Optional[str], conn=None) -> int:
    """Query the database for the number of broadband providers in a municipality.

    Args:
        municipality_code: admin_level_2.code (IBGE code).
        conn: Optional database connection.

    Returns:
        Number of distinct providers, or 2 as a default fallback.
    """
    if not municipality_code:
        return 2

    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception:
            logger.warning("Could not connect to database; using default provider count")
            return 2

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT bs.provider_id)
                FROM broadband_subscribers bs
                JOIN admin_level_2 a2 ON a2.id = bs.l2_id
                WHERE a2.code = %s
                  AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
                """,
                (municipality_code,),
            )
            row = cur.fetchone()
            return int(row[0]) if row and row[0] else 0
    except Exception as exc:
        logger.warning("Error querying provider count: %s", exc)
        return 2
    finally:
        if own_conn:
            conn.close()


def estimate_arpu(
    state_code: str,
    municipality_population: int,
    avg_income: float,
    technology: str = "fiber",
    provider_count: Optional[int] = None,
    municipality_code: Optional[str] = None,
) -> dict:
    """Estimate blended ARPU for a municipality.

    Args:
        state_code: Two-letter Brazilian state code (e.g. 'SP', 'MG').
        municipality_population: Total population of the municipality.
        avg_income: Average per-capita monthly income in BRL.
        technology: Primary access technology — 'fiber', 'fwa', or 'dsl'.
        provider_count: Number of competing broadband providers. If None,
            looks up from database using municipality_code.
        municipality_code: IBGE municipality code for DB lookup.

    Returns:
        Dictionary with:
            min_arpu:  Lower-bound blended ARPU (BRL/month)
            base_arpu: Expected blended ARPU (BRL/month)
            max_arpu:  Upper-bound blended ARPU (BRL/month)
            plan_mix:  Estimated plan distribution
            technology: Technology used for pricing
    """
    tech = technology.lower() if technology else "fiber"
    if tech not in PRICE_BENCHMARKS:
        logger.warning("Unknown technology '%s', defaulting to 'fiber'", tech)
        tech = "fiber"

    prices = PRICE_BENCHMARKS[tech]

    # Estimate household income from per-capita income
    # Brazilian average household size ~2.9 persons (IBGE 2022 Census)
    household_income = avg_income * 2.9

    # Determine plan mix based on income
    plan_mix = _estimate_plan_mix(household_income)

    # Base blended ARPU (weighted average across plan tiers)
    blended_arpu = (
        plan_mix["basic"] * prices["basic"]
        + plan_mix["mid"] * prices["mid"]
        + plan_mix["premium"] * prices["premium"]
    )

    # Competition adjustment
    if provider_count is None:
        provider_count = _lookup_provider_count(municipality_code)
    comp_factor = _get_competition_factor(provider_count)
    blended_arpu *= comp_factor

    # Population-size adjustment: very small municipalities tend to have
    # slightly higher churn and lower willingness to pay for premium plans,
    # while larger cities support premium pricing.
    if municipality_population < 10000:
        size_factor = 0.92
    elif municipality_population < 50000:
        size_factor = 0.96
    elif municipality_population < 200000:
        size_factor = 1.00
    elif municipality_population < 1000000:
        size_factor = 1.03
    else:
        size_factor = 1.06

    blended_arpu *= size_factor

    # Compute min/max as variance around the blended estimate
    min_arpu = round(blended_arpu * 0.85, 2)
    max_arpu = round(blended_arpu * 1.15, 2)
    base_arpu = round(blended_arpu, 2)

    # Sanity-check: clamp to reasonable range for the technology
    floor_price = prices["basic"] * 0.70
    ceil_price = prices["premium"] * 1.10
    min_arpu = round(max(floor_price, min_arpu), 2)
    base_arpu = round(max(floor_price, min(ceil_price, base_arpu)), 2)
    max_arpu = round(max(base_arpu, min(ceil_price, max_arpu)), 2)

    logger.info(
        "ARPU estimate for %s (pop=%d, income=R$%.0f, tech=%s, providers=%d): "
        "R$%.2f (range R$%.2f - R$%.2f)",
        state_code,
        municipality_population,
        avg_income,
        tech,
        provider_count,
        base_arpu,
        min_arpu,
        max_arpu,
    )

    return {
        "min_arpu": min_arpu,
        "base_arpu": base_arpu,
        "max_arpu": max_arpu,
        "plan_mix": plan_mix,
        "technology": tech,
        "competition_factor": round(comp_factor, 4),
        "provider_count": provider_count,
    }
