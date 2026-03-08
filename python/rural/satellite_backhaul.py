"""Satellite backhaul calculator.

Compares satellite options available in Brazil:
- Telebras SGDC (GEO, Ka-band) -- government satellite, free for eligible communities
- HughesNet (GEO) -- commercial, 25-50 Mbps, high latency
- Starlink (LEO) -- commercial, 50-200 Mbps, low latency ~30ms
- Viasat (GEO) -- commercial, 12-100 Mbps

Includes link budget estimation to verify that a satellite option can support
the aggregate demand of a given community.

Sources:
    - Telebras SGDC coverage maps and eligibility criteria
    - Starlink Brazil pricing (as of 2024)
    - HughesNet Brazil plans
    - Viasat Brazil plans
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SatelliteOption:
    """Describes a satellite backhaul service available in Brazil.

    Attributes:
        provider: Service provider name.
        orbit_type: GEO or LEO.
        latency_ms: Typical round-trip latency in milliseconds.
        download_mbps: Maximum download speed in Mbps.
        upload_mbps: Maximum upload speed in Mbps.
        data_cap_gb: Monthly data cap in GB, or None for unlimited.
        monthly_cost_brl: Monthly service cost in BRL.
        equipment_cost_brl: One-time equipment/terminal cost in BRL.
        availability_pct: Service availability target (percent).
        coverage_brazil: Coverage extent in Brazil.
        notes: Additional notes about the service.
    """

    provider: str
    orbit_type: str  # GEO, LEO
    latency_ms: float
    download_mbps: float
    upload_mbps: float
    data_cap_gb: float | None  # None = unlimited
    monthly_cost_brl: float
    equipment_cost_brl: float
    availability_pct: float
    coverage_brazil: str  # "full", "partial", "urban_only"
    notes: str


# ---------------------------------------------------------------------------
# Available satellite options in Brazil
# ---------------------------------------------------------------------------
SATELLITE_OPTIONS: list[SatelliteOption] = [
    SatelliteOption(
        provider="Telebras SGDC",
        orbit_type="GEO",
        latency_ms=600,
        download_mbps=10,
        upload_mbps=2,
        data_cap_gb=None,
        monthly_cost_brl=0,
        equipment_cost_brl=15_000,
        availability_pct=99.5,
        coverage_brazil="full",
        notes="Government program, free for eligible communities (GESAC/Wi-Fi Brasil)",
    ),
    SatelliteOption(
        provider="HughesNet",
        orbit_type="GEO",
        latency_ms=600,
        download_mbps=25,
        upload_mbps=3,
        data_cap_gb=50,
        monthly_cost_brl=399,
        equipment_cost_brl=2_500,
        availability_pct=99.5,
        coverage_brazil="full",
        notes="Commercial Ka-band, data cap with bonus overnight data",
    ),
    SatelliteOption(
        provider="Starlink",
        orbit_type="LEO",
        latency_ms=35,
        download_mbps=100,
        upload_mbps=20,
        data_cap_gb=None,
        monthly_cost_brl=250,
        equipment_cost_brl=2_800,
        availability_pct=99.0,
        coverage_brazil="partial",
        notes="Low latency but coverage expanding; priority data available for business plans",
    ),
    SatelliteOption(
        provider="Viasat",
        orbit_type="GEO",
        latency_ms=600,
        download_mbps=50,
        upload_mbps=5,
        data_cap_gb=100,
        monthly_cost_brl=499,
        equipment_cost_brl=3_000,
        availability_pct=99.5,
        coverage_brazil="full",
        notes="High bandwidth GEO, data cap applies",
    ),
]

# Starlink coverage zones in Brazil (approximate latitude bounds)
# As of 2024, Starlink covers most of Brazil but some deep Amazon areas
# have limited ground station support.
_STARLINK_COVERAGE_LAT_BOUNDS = (-33.0, 5.0)
_STARLINK_LIMITED_ZONES = {
    # Deep Amazon areas where ground station connectivity is limited
    "deep_amazon": {"lat_min": -3.0, "lat_max": 3.0, "lon_min": -70.0, "lon_max": -60.0},
}


def _is_starlink_available(latitude: float, longitude: float) -> bool:
    """Check if Starlink is likely available at a given location.

    This is an approximation based on known coverage patterns.
    """
    if not (_STARLINK_COVERAGE_LAT_BOUNDS[0] <= latitude <= _STARLINK_COVERAGE_LAT_BOUNDS[1]):
        return False

    for zone in _STARLINK_LIMITED_ZONES.values():
        if (
            zone["lat_min"] <= latitude <= zone["lat_max"]
            and zone["lon_min"] <= longitude <= zone["lon_max"]
        ):
            logger.info(
                "Starlink may have limited availability at (%.4f, %.4f) — deep Amazon zone",
                latitude,
                longitude,
            )
            return False

    return True


def recommend_satellite(
    latitude: float,
    longitude: float,
    required_mbps: float = 10,
    budget_monthly_brl: float = 500,
) -> list[SatelliteOption]:
    """Rank satellite options for a location.

    Filters options by coverage availability and budget, then ranks by
    a score that balances bandwidth, latency, and cost.

    Args:
        latitude: Location latitude (decimal degrees).
        longitude: Location longitude (decimal degrees).
        required_mbps: Minimum required download speed in Mbps.
        budget_monthly_brl: Maximum monthly budget in BRL.

    Returns:
        List of SatelliteOption sorted best-to-worst. May be empty if
        no options meet the requirements.
    """
    if required_mbps <= 0:
        logger.warning("required_mbps is <= 0, defaulting to 10 Mbps.")
        required_mbps = 10

    if budget_monthly_brl < 0:
        logger.warning("budget_monthly_brl is negative, defaulting to 500 BRL.")
        budget_monthly_brl = 500

    candidates: list[tuple[float, SatelliteOption]] = []

    for option in SATELLITE_OPTIONS:
        # Check coverage
        if option.provider == "Starlink" and not _is_starlink_available(latitude, longitude):
            logger.debug("Starlink not available at (%.4f, %.4f)", latitude, longitude)
            continue

        # Check bandwidth requirement
        if option.download_mbps < required_mbps:
            logger.debug(
                "%s excluded: %.0f Mbps < required %.0f Mbps",
                option.provider,
                option.download_mbps,
                required_mbps,
            )
            continue

        # Check budget (Telebras is free, always passes)
        if option.monthly_cost_brl > budget_monthly_brl:
            logger.debug(
                "%s excluded: R$%.0f/mo > budget R$%.0f/mo",
                option.provider,
                option.monthly_cost_brl,
                budget_monthly_brl,
            )
            continue

        # Score: higher is better
        # Factors: bandwidth (40%), latency (30%), cost efficiency (20%), availability (10%)
        bw_score = min(option.download_mbps / 100.0, 1.0) * 40
        latency_score = max(0, (1.0 - option.latency_ms / 1000.0)) * 30
        cost_score = max(0, (1.0 - option.monthly_cost_brl / 1000.0)) * 20
        avail_score = (option.availability_pct / 100.0) * 10

        total_score = bw_score + latency_score + cost_score + avail_score

        # Bonus for unlimited data
        if option.data_cap_gb is None:
            total_score += 5

        candidates.append((total_score, option))

    # Sort by score descending
    candidates.sort(key=lambda x: x[0], reverse=True)

    result = [option for _, option in candidates]

    logger.info(
        "Satellite recommendation at (%.4f, %.4f): %d options (required %.0f Mbps, budget R$%.0f/mo)",
        latitude,
        longitude,
        len(result),
        required_mbps,
        budget_monthly_brl,
    )
    for i, opt in enumerate(result):
        logger.info(
            "  #%d: %s (%s) — %.0f Mbps, %s ms latency, R$%.0f/mo",
            i + 1,
            opt.provider,
            opt.orbit_type,
            opt.download_mbps,
            opt.latency_ms,
            opt.monthly_cost_brl,
        )

    return result


def estimate_link_budget_satellite(
    option: SatelliteOption,
    users: int,
    avg_usage_gb: float = 5.0,
) -> dict:
    """Estimate if satellite capacity meets community needs.

    Performs a simplified link budget analysis considering:
    - Aggregate bandwidth demand vs. available capacity
    - Data cap feasibility (if applicable)
    - Contention ratio analysis

    Args:
        option: The satellite option to evaluate.
        users: Number of concurrent users/subscribers.
        avg_usage_gb: Average monthly data usage per user in GB.

    Returns:
        Dictionary with:
            feasible: Whether the option can support the community.
            aggregate_demand_mbps: Peak aggregate demand estimate.
            available_mbps: Available download bandwidth.
            contention_ratio: Demand / capacity ratio.
            monthly_data_total_gb: Total monthly data consumption.
            data_cap_sufficient: Whether data cap (if any) is sufficient.
            bottleneck: Description of the main limitation.
            recommendations: List of recommendations.
    """
    if users <= 0:
        return {
            "feasible": False,
            "aggregate_demand_mbps": 0,
            "available_mbps": option.download_mbps,
            "contention_ratio": 0,
            "monthly_data_total_gb": 0,
            "data_cap_sufficient": True,
            "bottleneck": "No users specified.",
            "recommendations": ["Provide a positive user count."],
        }

    if avg_usage_gb <= 0:
        avg_usage_gb = 5.0

    # Estimate peak aggregate demand
    # Assume 10% of users are active simultaneously at peak
    # Each active user needs ~2 Mbps for basic browsing/streaming
    simultaneous_pct = 0.10
    per_user_peak_mbps = 2.0
    active_users = max(1, math.ceil(users * simultaneous_pct))
    aggregate_demand = active_users * per_user_peak_mbps

    # Contention ratio
    contention = aggregate_demand / option.download_mbps if option.download_mbps > 0 else float("inf")

    # Data cap check
    monthly_total_gb = users * avg_usage_gb
    if option.data_cap_gb is not None:
        data_cap_ok = monthly_total_gb <= option.data_cap_gb
    else:
        data_cap_ok = True

    # Determine feasibility
    bandwidth_ok = contention <= 2.0  # Up to 2:1 contention is acceptable
    feasible = bandwidth_ok and data_cap_ok

    # Identify bottleneck
    if not bandwidth_ok and not data_cap_ok:
        bottleneck = "Both bandwidth and data cap exceeded."
    elif not bandwidth_ok:
        bottleneck = (
            f"Bandwidth contention too high: {aggregate_demand:.1f} Mbps demand "
            f"vs. {option.download_mbps:.0f} Mbps available ({contention:.1f}:1)."
        )
    elif not data_cap_ok:
        bottleneck = (
            f"Data cap exceeded: {monthly_total_gb:.0f} GB needed "
            f"vs. {option.data_cap_gb:.0f} GB cap."
        )
    else:
        bottleneck = "None — capacity is sufficient."

    # Recommendations
    recommendations: list[str] = []
    if not bandwidth_ok:
        max_users_bw = int(option.download_mbps / per_user_peak_mbps / simultaneous_pct)
        recommendations.append(
            f"Reduce user count to ~{max_users_bw} or implement traffic shaping."
        )
        if option.orbit_type == "GEO":
            recommendations.append(
                "Consider Starlink (LEO) for higher bandwidth and lower latency."
            )

    if not data_cap_ok and option.data_cap_gb is not None:
        max_users_cap = int(option.data_cap_gb / avg_usage_gb) if avg_usage_gb > 0 else 0
        recommendations.append(
            f"Reduce user count to ~{max_users_cap} or reduce avg usage to "
            f"{option.data_cap_gb / users:.1f} GB/user."
        )
        recommendations.append(
            "Consider an unlimited data plan (Telebras SGDC or Starlink)."
        )

    if feasible and contention > 1.0:
        recommendations.append(
            "Contention ratio is moderate. Consider QoS/traffic shaping to "
            "ensure fair bandwidth distribution."
        )

    if option.orbit_type == "GEO":
        recommendations.append(
            "GEO latency (~600 ms) will impact video calls, gaming, and "
            "real-time applications. Inform users of limitations."
        )

    result = {
        "feasible": feasible,
        "aggregate_demand_mbps": round(aggregate_demand, 2),
        "available_mbps": option.download_mbps,
        "contention_ratio": round(contention, 2),
        "monthly_data_total_gb": round(monthly_total_gb, 1),
        "data_cap_sufficient": data_cap_ok,
        "data_cap_gb": option.data_cap_gb,
        "bottleneck": bottleneck,
        "recommendations": recommendations,
        "details": {
            "active_users_at_peak": active_users,
            "per_user_peak_mbps": per_user_peak_mbps,
            "simultaneous_pct": simultaneous_pct,
            "avg_usage_gb_per_user": avg_usage_gb,
        },
    }

    logger.info(
        "Link budget for %s: %d users, %.1f Mbps demand / %.0f Mbps available "
        "(%.1f:1 contention) — %s",
        option.provider,
        users,
        aggregate_demand,
        option.download_mbps,
        contention,
        "FEASIBLE" if feasible else "NOT FEASIBLE",
    )

    return result
