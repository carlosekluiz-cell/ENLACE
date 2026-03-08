"""Financial viability analysis: NPV, IRR, payback, and full scenario modeling.

Provides ROI/NPV/IRR computations and an orchestrator that combines subscriber
projections, ARPU estimation, and CAPEX modeling to produce a complete
financial analysis for a prospective ISP expansion.
"""

import logging
import math
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG
from python.ml.financial.arpu_model import estimate_arpu
from python.ml.financial.capex_estimator import estimate_capex, get_terrain_multiplier
from python.ml.financial.subscriber_curve import project_subscribers

logger = logging.getLogger(__name__)

# Default financial assumptions for Brazilian small/medium ISPs
DEFAULT_OPEX_RATIO = 0.45       # 45% of revenue goes to OPEX
DEFAULT_ANNUAL_DISCOUNT = 0.12  # 12% annual discount rate (CDI + risk premium)
DEFAULT_MONTHS = 36             # 3-year projection horizon


def compute_financial_metrics(
    capex_brl: float,
    monthly_subscribers: list,
    arpu_brl: float,
    opex_ratio: float = DEFAULT_OPEX_RATIO,
    discount_rate: float = DEFAULT_ANNUAL_DISCOUNT,
    months: int = DEFAULT_MONTHS,
) -> dict:
    """Compute NPV, IRR, payback and cash-flow projections.

    Args:
        capex_brl: Total upfront capital expenditure in BRL.
        monthly_subscribers: List of cumulative subscriber counts per month.
        arpu_brl: Blended average revenue per user per month (BRL).
        opex_ratio: Fraction of revenue consumed by operating expenses.
        discount_rate: Annual discount rate for NPV calculation.
        months: Number of months to evaluate (capped by length of
            monthly_subscribers).

    Returns:
        Dictionary with:
            npv_brl: Net Present Value in BRL
            irr_pct: Internal Rate of Return as a percentage, or None
            payback_months: Month when cumulative cash flow turns positive,
                or None if never
            monthly_cashflow: List of monthly net cash flows
            cumulative_cashflow: List of cumulative cash flows
            total_revenue_brl: Sum of all monthly revenues
            total_opex_brl: Sum of all monthly OPEX
    """
    if capex_brl <= 0 or not monthly_subscribers or arpu_brl <= 0:
        return {
            "npv_brl": 0.0,
            "irr_pct": None,
            "payback_months": None,
            "monthly_cashflow": [],
            "cumulative_cashflow": [],
            "total_revenue_brl": 0.0,
            "total_opex_brl": 0.0,
        }

    effective_months = min(months, len(monthly_subscribers))

    # Monthly discount rate from annual
    monthly_discount = (1.0 + discount_rate) ** (1.0 / 12.0) - 1.0

    # Cash flows: month 0 is the CAPEX outlay (negative)
    # Months 1..N are net operating cash flows
    monthly_cashflow = []
    cumulative_cashflow = []
    cumulative = -capex_brl
    total_revenue = 0.0
    total_opex = 0.0
    npv = -capex_brl  # discounted cash flow starts with CAPEX

    # Insert month-0 (investment)
    monthly_cashflow.append(round(-capex_brl, 2))
    cumulative_cashflow.append(round(cumulative, 2))

    payback_month = None

    for m in range(effective_months):
        subs = monthly_subscribers[m]
        revenue = subs * arpu_brl
        opex = revenue * opex_ratio
        net_cf = revenue - opex

        total_revenue += revenue
        total_opex += opex

        monthly_cashflow.append(round(net_cf, 2))
        cumulative += net_cf
        cumulative_cashflow.append(round(cumulative, 2))

        # NPV: discount this month's cash flow
        discount_factor = 1.0 / ((1.0 + monthly_discount) ** (m + 1))
        npv += net_cf * discount_factor

        # Payback: first month where cumulative becomes non-negative
        if payback_month is None and cumulative >= 0:
            payback_month = m + 1  # 1-indexed month

    # --- IRR calculation via binary search ---
    irr_pct = _compute_irr(monthly_cashflow)

    result = {
        "npv_brl": round(npv, 2),
        "irr_pct": round(irr_pct, 2) if irr_pct is not None else None,
        "payback_months": payback_month,
        "monthly_cashflow": monthly_cashflow,
        "cumulative_cashflow": cumulative_cashflow,
        "total_revenue_brl": round(total_revenue, 2),
        "total_opex_brl": round(total_opex, 2),
    }

    logger.info(
        "Financial metrics: NPV=R$%.0f, IRR=%s, Payback=%s months",
        npv,
        f"{irr_pct:.1f}%" if irr_pct is not None else "N/A",
        payback_month if payback_month else "never",
    )

    return result


def _compute_irr(cashflows: list, max_iterations: int = 200, tolerance: float = 1e-6) -> Optional[float]:
    """Compute IRR using binary search over monthly rates.

    The IRR is the monthly discount rate that makes NPV = 0.  We search
    in the range [-50% monthly, +200% monthly] which covers annual rates
    from deeply negative to extremely high.

    Args:
        cashflows: List of cash flows starting with month 0 (usually negative).
        max_iterations: Maximum binary search iterations.
        tolerance: Convergence threshold for NPV.

    Returns:
        Annualized IRR as a percentage, or None if no solution found.
    """
    if not cashflows or len(cashflows) < 2:
        return None

    # Check if there's at least one sign change
    has_negative = any(cf < 0 for cf in cashflows)
    has_positive = any(cf > 0 for cf in cashflows)
    if not (has_negative and has_positive):
        return None

    def npv_at_rate(monthly_rate: float) -> float:
        """Compute NPV at a given monthly discount rate."""
        total = 0.0
        for i, cf in enumerate(cashflows):
            try:
                total += cf / ((1.0 + monthly_rate) ** i)
            except (OverflowError, ZeroDivisionError):
                return float("inf")
        return total

    # Binary search bounds: monthly rates
    low = -0.5
    high = 2.0

    # Ensure bounds bracket a root
    npv_low = npv_at_rate(low)
    npv_high = npv_at_rate(high)

    # If both have the same sign, try wider bounds
    if npv_low * npv_high > 0:
        # Try expanding the high end
        for h in [5.0, 10.0, 50.0]:
            npv_h = npv_at_rate(h)
            if npv_low * npv_h <= 0:
                high = h
                npv_high = npv_h
                break
        else:
            # Still no bracket — IRR may not exist
            return None

    for _ in range(max_iterations):
        mid = (low + high) / 2.0
        npv_mid = npv_at_rate(mid)

        if abs(npv_mid) < tolerance:
            break

        if npv_at_rate(low) * npv_mid < 0:
            high = mid
        else:
            low = mid

    monthly_irr = (low + high) / 2.0

    # Convert monthly IRR to annual percentage
    annual_irr = ((1.0 + monthly_irr) ** 12 - 1.0) * 100.0
    return annual_irr


def _fetch_municipality_data(municipality_code: str, conn=None) -> Optional[dict]:
    """Fetch municipality data needed for financial analysis from the database.

    Args:
        municipality_code: IBGE municipality code (admin_level_2.code).
        conn: Optional database connection.

    Returns:
        Dictionary with municipality attributes, or None if not found.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return None

    try:
        with conn.cursor() as cur:
            # Fetch core municipality data
            cur.execute(
                """
                SELECT
                    a2.id,
                    a2.code,
                    a2.name,
                    a2.area_km2,
                    a1.abbrev AS state_code,
                    ST_X(a2.centroid) AS lon,
                    ST_Y(a2.centroid) AS lat
                FROM admin_level_2 a2
                JOIN admin_level_1 a1 ON a1.id = a2.l1_id
                WHERE a2.code = %s
                """,
                (municipality_code,),
            )
            row = cur.fetchone()
            if not row:
                logger.warning("Municipality %s not found", municipality_code)
                return None

            muni_id, code, name, area_km2, state_code, lon, lat = row

            # Fetch demographics
            cur.execute(
                """
                SELECT
                    SUM(cd.total_households) AS total_households,
                    SUM(cd.total_population) AS total_population,
                    AVG((cd.income_data->>'avg_per_capita_brl')::float) AS avg_income,
                    COUNT(CASE WHEN ct.situation = '1' THEN 1 END)::float /
                        NULLIF(COUNT(*)::float, 0) AS urbanization_rate
                FROM census_tracts ct
                JOIN census_demographics cd ON cd.tract_id = ct.id
                WHERE ct.l2_id = %s
                """,
                (muni_id,),
            )
            demo_row = cur.fetchone()
            total_households = int(demo_row[0]) if demo_row and demo_row[0] else 0
            total_population = int(demo_row[1]) if demo_row and demo_row[1] else 0
            avg_income = float(demo_row[2]) if demo_row and demo_row[2] else 1500.0
            urbanization_rate = float(demo_row[3]) if demo_row and demo_row[3] else 0.6

            # Fetch current broadband penetration
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(bs.subscribers), 0) AS total_subs,
                    COUNT(DISTINCT bs.provider_id) AS provider_count
                FROM broadband_subscribers bs
                WHERE bs.l2_id = %s
                  AND bs.year_month = (SELECT MAX(year_month) FROM broadband_subscribers)
                """,
                (muni_id,),
            )
            bb_row = cur.fetchone()
            current_subs = int(bb_row[0]) if bb_row and bb_row[0] else 0
            provider_count = int(bb_row[1]) if bb_row and bb_row[1] else 0
            current_penetration = (
                current_subs / total_households if total_households > 0 else 0.0
            )

            # Fetch road and terrain data near the municipality centroid
            cur.execute(
                """
                SELECT
                    COALESCE(SUM(rs.length_m), 0) / 1000.0 AS road_km
                FROM road_segments rs
                WHERE ST_DWithin(
                    rs.geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    30000
                )
                """,
                (lon, lat),
            )
            road_row = cur.fetchone()
            road_km = float(road_row[0]) if road_row and road_row[0] else 10.0

            return {
                "id": muni_id,
                "code": code,
                "name": name,
                "state_code": state_code,
                "area_km2": area_km2 or 700.0,
                "lat": lat,
                "lon": lon,
                "total_households": total_households,
                "total_population": total_population,
                "avg_income": avg_income,
                "urbanization_rate": urbanization_rate,
                "current_penetration": current_penetration,
                "current_subscribers": current_subs,
                "provider_count": provider_count,
                "road_km_nearby": road_km,
            }

    except Exception as exc:
        logger.error("Error fetching municipality data: %s", exc)
        return None
    finally:
        if own_conn:
            conn.close()


def _classify_competition(provider_count: int) -> str:
    """Map provider count to competition level string."""
    if provider_count <= 1:
        return "low"
    elif provider_count <= 3:
        return "moderate"
    else:
        return "high"


def run_full_analysis(
    municipality_code: str,
    from_lat: float,
    from_lon: float,
    monthly_price_brl: float,
    technology: str = "fiber",
    months: int = DEFAULT_MONTHS,
    opex_ratio: float = DEFAULT_OPEX_RATIO,
    discount_rate: float = DEFAULT_ANNUAL_DISCOUNT,
) -> dict:
    """Run a complete financial viability analysis for a municipality.

    Orchestrates subscriber projections, ARPU estimation, CAPEX modeling,
    and financial metric computation across pessimistic/base/optimistic
    scenarios.

    Args:
        municipality_code: IBGE municipality code.
        from_lat: Latitude of the proposed POP / starting point.
        from_lon: Longitude of the proposed POP / starting point.
        monthly_price_brl: Planned monthly subscription price in BRL.
        technology: Access technology ('fiber', 'fwa', 'dsl').
        months: Projection horizon in months.
        opex_ratio: OPEX as fraction of revenue.
        discount_rate: Annual discount rate for NPV.

    Returns:
        Complete financial analysis dictionary with scenario results.
    """
    # Fetch municipality data
    muni = _fetch_municipality_data(municipality_code)
    if not muni:
        return {
            "status": "error",
            "message": f"Municipality {municipality_code} not found or DB unavailable",
        }

    # --- Subscriber projections ---
    competition_level = _classify_competition(muni["provider_count"])

    # Estimate penetration ceiling based on current data
    # Use the demand model approach: affordability-adjusted ceiling
    from python.ml.opportunity.demand_model import estimate_addressable_market

    demand = estimate_addressable_market(
        households=muni["total_households"],
        avg_income=muni["avg_income"],
        current_penetration=muni["current_penetration"],
        urbanization_rate=muni["urbanization_rate"],
    )

    addressable_hh = demand["addressable_households"]
    pen_ceiling = demand["penetration_ceiling"]

    # Our target market share: assume ISP can capture a fraction of the
    # addressable market depending on competition
    if competition_level == "low":
        target_share = 0.40
    elif competition_level == "moderate":
        target_share = 0.25
    else:
        target_share = 0.15

    target_addressable = int(addressable_hh * target_share)
    target_addressable = max(target_addressable, 1)

    sub_projections = project_subscribers(
        addressable_households=target_addressable,
        penetration_ceiling=1.0,  # Already adjusted by target_share
        months=months,
        urbanization_rate=muni["urbanization_rate"],
        competition_level=competition_level,
    )

    # --- ARPU estimation ---
    arpu = estimate_arpu(
        state_code=muni["state_code"],
        municipality_population=muni["total_population"],
        avg_income=muni["avg_income"],
        technology=technology,
        provider_count=muni["provider_count"],
    )

    # Use the provided monthly_price as ARPU if specified, otherwise model
    effective_arpu = monthly_price_brl if monthly_price_brl > 0 else arpu["base_arpu"]

    # --- CAPEX estimation ---
    # Estimate cable length: a fraction of nearby roads (ISP won't build on all)
    # Rough heuristic: target ~2-5 km per 1000 subscribers for urban,
    # more for suburban/rural
    if muni["urbanization_rate"] >= 0.75:
        area_type = "urban"
        km_per_1k_subs = 3.0
    elif muni["urbanization_rate"] >= 0.40:
        area_type = "suburban"
        km_per_1k_subs = 6.0
    else:
        area_type = "rural"
        km_per_1k_subs = 12.0

    # Use base_case final subscriber count for cable sizing
    final_subs_base = sub_projections["base_case"][-1] if sub_projections["base_case"] else 0
    estimated_cable_km = max(1.0, (final_subs_base / 1000.0) * km_per_1k_subs)
    estimated_cable_km = min(estimated_cable_km, muni["road_km_nearby"] * 0.3)
    estimated_cable_km = max(estimated_cable_km, 1.0)

    capex = estimate_capex(
        cable_length_km=estimated_cable_km,
        target_subscribers=max(final_subs_base, 1),
        technology=technology,
        area_type=area_type,
    )

    # --- Financial metrics for each scenario ---
    scenarios = {}
    for scenario_name in ["pessimistic", "base_case", "optimistic"]:
        subs_curve = sub_projections[scenario_name]

        # Adjust ARPU by scenario
        if scenario_name == "pessimistic":
            scenario_arpu = effective_arpu * 0.90
        elif scenario_name == "optimistic":
            scenario_arpu = effective_arpu * 1.05
        else:
            scenario_arpu = effective_arpu

        metrics = compute_financial_metrics(
            capex_brl=capex["total_brl"],
            monthly_subscribers=subs_curve,
            arpu_brl=scenario_arpu,
            opex_ratio=opex_ratio,
            discount_rate=discount_rate,
            months=months,
        )

        scenarios[scenario_name] = {
            "subscribers_at_end": subs_curve[-1] if subs_curve else 0,
            "arpu_brl": round(scenario_arpu, 2),
            "npv_brl": metrics["npv_brl"],
            "irr_pct": metrics["irr_pct"],
            "payback_months": metrics["payback_months"],
            "total_revenue_brl": metrics["total_revenue_brl"],
            "total_opex_brl": metrics["total_opex_brl"],
            "monthly_cashflow": metrics["monthly_cashflow"],
            "cumulative_cashflow": metrics["cumulative_cashflow"],
        }

    # Determine viability verdict
    base = scenarios["base_case"]
    if base["irr_pct"] is not None and base["irr_pct"] >= 15.0:
        verdict = "viable"
    elif base["irr_pct"] is not None and base["irr_pct"] >= 8.0:
        verdict = "marginal"
    elif base["npv_brl"] > 0:
        verdict = "marginal"
    else:
        verdict = "not_viable"

    result = {
        "status": "success",
        "municipality": {
            "code": muni["code"],
            "name": muni["name"],
            "state": muni["state_code"],
            "total_households": muni["total_households"],
            "total_population": muni["total_population"],
            "avg_income_brl": round(muni["avg_income"], 2),
            "urbanization_rate": round(muni["urbanization_rate"], 4),
            "current_penetration": round(muni["current_penetration"], 4),
            "provider_count": muni["provider_count"],
        },
        "market_sizing": {
            "addressable_households": addressable_hh,
            "penetration_ceiling": round(pen_ceiling, 4),
            "target_market_share": round(target_share, 4),
            "target_subscribers": target_addressable,
            "competition_level": competition_level,
        },
        "capex": capex,
        "arpu": arpu,
        "subscriber_projections": {
            "parameters": sub_projections.get("parameters", {}),
            "pessimistic": sub_projections["pessimistic"],
            "base_case": sub_projections["base_case"],
            "optimistic": sub_projections["optimistic"],
        },
        "scenarios": scenarios,
        "verdict": verdict,
        "assumptions": {
            "technology": technology,
            "monthly_price_brl": round(effective_arpu, 2),
            "opex_ratio": opex_ratio,
            "discount_rate_annual": discount_rate,
            "projection_months": months,
            "cable_length_km": round(estimated_cable_km, 2),
        },
    }

    logger.info(
        "Full analysis for %s (%s): verdict=%s, base NPV=R$%.0f, IRR=%s",
        muni["name"],
        muni["code"],
        verdict,
        base["npv_brl"],
        f"{base['irr_pct']:.1f}%" if base["irr_pct"] is not None else "N/A",
    )

    return result
