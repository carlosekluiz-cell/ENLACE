"""Amazon river crossing solutions.

For fiber/wireless crossings over rivers (Amazon basin has many wide rivers).
Brazil's Amazon region has over 1,100 rivers, many of which are kilometers
wide. River crossings are one of the most challenging and expensive aspects
of deploying telecom infrastructure in the region.

Crossing options:
- Aerial cable: poles/towers on each bank, cable strung across
- Submarine cable: armored fiber laid along the river bottom
- Microwave link: point-to-point radio link across the river

Design considerations:
- River width, depth, and current speed
- Navigation clearance requirements (ANTAQ regulations)
- Seasonal water level variation (Amazon rivers rise 10-15m in flood season)
- Aquatic traffic (commercial shipping, ferry routes)
- Environmental permits (IBAMA)

Sources:
    - ANTAQ inland waterway regulations
    - Norte Conectado program engineering standards
    - Telebras Amazon deployment experience
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# River crossing cost parameters (BRL)
# ---------------------------------------------------------------------------
AERIAL_CABLE_COSTS = {
    "pole_cost_brl": 15_000,      # Tall utility pole (15-20m)
    "tower_cost_brl": 120_000,    # Steel tower (30-50m, for wide crossings)
    "cable_per_meter_brl": 80,    # ADSS (All-Dielectric Self-Supporting) fiber
    "installation_per_crossing_brl": 30_000,
    "max_span_m": 400,            # Maximum single span without mid-river support
    "min_clearance_m": 15,        # Navigation clearance (ANTAQ requirement)
}

SUBMARINE_CABLE_COSTS = {
    "cable_per_meter_brl": 350,     # Armored submarine fiber optic cable
    "burial_per_meter_brl": 200,    # River-bottom trenching/burial
    "landing_station_brl": 45_000,  # Cable landing and splice housing (each bank)
    "survey_cost_brl": 25_000,      # River bottom survey (bathymetry)
    "installation_base_brl": 80_000,  # Vessel and diving team mobilization
    "max_practical_width_m": 5_000,  # Beyond this, cost becomes prohibitive
}

MICROWAVE_LINK_COSTS = {
    "radio_pair_brl": 45_000,      # Licensed microwave radio pair
    "tower_per_unit_brl": 120_000,  # Tower at each end (30-50m)
    "installation_brl": 25_000,
    "max_range_m": 30_000,          # Practical max range over water
    "min_clearance_m": 10,          # Fresnel zone clearance over water
}

# Seasonal water level variation by region
WATER_LEVEL_VARIATION_M = {
    "amazon_main": 15.0,    # Amazon River mainstem
    "negro": 12.0,          # Rio Negro
    "solimoes": 14.0,       # Rio Solimoes
    "madeira": 13.0,        # Rio Madeira
    "tapajos": 8.0,         # Rio Tapajos
    "tocantins": 10.0,      # Rio Tocantins
    "other": 8.0,           # Default for smaller rivers
}

# Environmental permit timeline
ENVIRONMENTAL_TIMELINE_MONTHS = {
    "aerial": 3,         # Simplest — poles on banks
    "submarine": 6,      # Requires IBAMA + ANTAQ permits
    "microwave": 2,      # Anatel spectrum + structure permits
}


@dataclass
class RiverCrossing:
    """A river crossing design option.

    Attributes:
        crossing_type: Type of crossing solution.
        width_m: River width at crossing point.
        estimated_cost_brl: Total estimated cost.
        installation_time_days: Estimated installation time in days.
        maintenance_risk: Risk level for ongoing maintenance.
        notes: Design-specific notes and warnings.
    """

    crossing_type: str  # "submarine_cable", "aerial_cable", "microwave_link"
    width_m: float
    estimated_cost_brl: float
    installation_time_days: int
    maintenance_risk: str
    notes: str


def _design_aerial_crossing(
    width_m: float,
    depth_m: float,
    current_speed_ms: float,
) -> RiverCrossing | None:
    """Design an aerial cable crossing if feasible.

    Aerial crossings use ADSS (All-Dielectric Self-Supporting) fiber cable
    strung between tall poles or towers on each bank.

    Feasibility: width < 400m (single span) or up to ~800m with mid-river support.
    """
    max_span = AERIAL_CABLE_COSTS["max_span_m"]

    # Only feasible for narrower rivers
    if width_m > max_span * 2:
        return None  # Too wide for aerial crossing

    # Single span or multi-span
    num_spans = math.ceil(width_m / max_span)

    if num_spans == 1:
        # Single span: two poles/towers on each bank
        if width_m > 200:
            support_cost = AERIAL_CABLE_COSTS["tower_cost_brl"] * 2
            support_type = "towers"
        else:
            support_cost = AERIAL_CABLE_COSTS["pole_cost_brl"] * 2
            support_type = "poles"
        mid_river_supports = 0
    else:
        # Multi-span: towers on banks + mid-river platform
        support_cost = AERIAL_CABLE_COSTS["tower_cost_brl"] * 2
        # Mid-river support is extremely expensive (artificial island or platform)
        mid_river_cost = 200_000 * (num_spans - 1)
        support_cost += mid_river_cost
        support_type = f"towers + {num_spans - 1} mid-river platform(s)"
        mid_river_supports = num_spans - 1

    cable_cost = width_m * 1.15 * AERIAL_CABLE_COSTS["cable_per_meter_brl"]  # 15% sag allowance
    installation = AERIAL_CABLE_COSTS["installation_per_crossing_brl"]

    total_cost = support_cost + cable_cost + installation

    # Installation time
    if num_spans == 1:
        install_days = 7 if width_m <= 200 else 14
    else:
        install_days = 14 + (mid_river_supports * 30)  # Mid-river platforms take weeks

    # Risk assessment
    if width_m <= 200:
        risk = "low"
    elif width_m <= 400:
        risk = "medium"
    else:
        risk = "high"

    notes_parts = [
        f"Aerial crossing: {width_m:.0f}m span using {support_type}.",
        f"Navigation clearance: {AERIAL_CABLE_COSTS['min_clearance_m']}m above high water.",
    ]
    if mid_river_supports > 0:
        notes_parts.append(
            f"WARNING: {mid_river_supports} mid-river support(s) required. "
            "Very expensive and complex. Consider microwave alternative."
        )
    if current_speed_ms > 2.0:
        notes_parts.append(
            f"Strong current ({current_speed_ms} m/s) may complicate installation."
        )

    return RiverCrossing(
        crossing_type="aerial_cable",
        width_m=width_m,
        estimated_cost_brl=round(total_cost, 2),
        installation_time_days=install_days,
        maintenance_risk=risk,
        notes=" ".join(notes_parts),
    )


def _design_submarine_crossing(
    width_m: float,
    depth_m: float,
    current_speed_ms: float,
) -> RiverCrossing | None:
    """Design a submarine cable crossing if feasible.

    Submarine crossings use armored fiber optic cable laid along the river
    bottom, ideally buried 1-2m below the riverbed.
    """
    max_width = SUBMARINE_CABLE_COSTS["max_practical_width_m"]

    if width_m > max_width:
        return None  # Too wide for submarine cable

    # Cable length includes 20% extra for routing, depth changes, and slack
    cable_length = width_m * 1.20

    cable_cost = cable_length * SUBMARINE_CABLE_COSTS["cable_per_meter_brl"]
    burial_cost = cable_length * SUBMARINE_CABLE_COSTS["burial_per_meter_brl"]
    landing_cost = SUBMARINE_CABLE_COSTS["landing_station_brl"] * 2  # Both banks
    survey_cost = SUBMARINE_CABLE_COSTS["survey_cost_brl"]
    installation_cost = SUBMARINE_CABLE_COSTS["installation_base_brl"]

    # Depth and current adjustments
    depth_mult = 1.0
    if depth_m > 20:
        depth_mult = 1.3  # Deep river requires specialized diving
    if depth_m > 50:
        depth_mult = 1.8  # Very deep — ROV needed

    current_mult = 1.0
    if current_speed_ms > 2.0:
        current_mult = 1.2  # Strong current complicates installation
    if current_speed_ms > 3.0:
        current_mult = 1.5  # Very strong current — specialized vessels needed

    total_cost = (
        (cable_cost + burial_cost) * depth_mult * current_mult
        + landing_cost
        + survey_cost
        + installation_cost
    )

    # Installation time
    base_days = max(14, math.ceil(width_m / 100))  # Roughly 100m per day
    install_days = int(base_days * depth_mult * current_mult)

    # Risk assessment
    if width_m <= 500 and depth_m <= 20 and current_speed_ms <= 1.5:
        risk = "low"
    elif width_m <= 2000 and depth_m <= 50:
        risk = "medium"
    else:
        risk = "high"

    notes_parts = [
        f"Submarine cable: {width_m:.0f}m crossing, {depth_m:.0f}m depth.",
        f"Cable length: {cable_length:.0f}m (incl. 20% slack/routing).",
    ]
    if depth_m > 20:
        notes_parts.append(
            f"Deep water ({depth_m}m) requires specialized diving equipment."
        )
    if current_speed_ms > 2.0:
        notes_parts.append(
            f"Strong current ({current_speed_ms} m/s) increases installation difficulty."
        )
    notes_parts.append(
        "Requires IBAMA environmental permit and ANTAQ navigation clearance."
    )
    notes_parts.append(
        f"Estimated environmental permit timeline: {ENVIRONMENTAL_TIMELINE_MONTHS['submarine']} months."
    )

    return RiverCrossing(
        crossing_type="submarine_cable",
        width_m=width_m,
        estimated_cost_brl=round(total_cost, 2),
        installation_time_days=install_days,
        maintenance_risk=risk,
        notes=" ".join(notes_parts),
    )


def _design_microwave_crossing(
    width_m: float,
    depth_m: float,
    current_speed_ms: float,
) -> RiverCrossing | None:
    """Design a microwave link crossing.

    Microwave links are the simplest solution for wide rivers. Two towers
    with point-to-point radios, no physical crossing of the river.
    """
    max_range = MICROWAVE_LINK_COSTS["max_range_m"]

    if width_m > max_range:
        return None  # Beyond practical microwave range

    radio_cost = MICROWAVE_LINK_COSTS["radio_pair_brl"]
    tower_cost = MICROWAVE_LINK_COSTS["tower_per_unit_brl"] * 2  # Both banks
    installation_cost = MICROWAVE_LINK_COSTS["installation_brl"]

    total_cost = radio_cost + tower_cost + installation_cost

    # For wider crossings, need taller towers for Fresnel zone clearance
    if width_m > 5_000:
        # Need 40-50m towers instead of 30m
        tower_upgrade = 40_000 * 2
        total_cost += tower_upgrade

    if width_m > 10_000:
        # May need higher-power radios for longer links
        total_cost += 20_000

    # Installation time: relatively quick
    install_days = 7

    # Risk assessment (microwave is generally reliable)
    if width_m <= 5_000:
        risk = "low"
    elif width_m <= 15_000:
        risk = "medium"
    else:
        risk = "medium"  # Rain fade at long distances

    notes_parts = [
        f"Microwave link: {width_m:.0f}m ({width_m/1000:.1f} km) crossing.",
        f"Towers on each bank (no physical river crossing needed).",
    ]

    if width_m > 5_000:
        notes_parts.append(
            "Long link — consider rain fade margin for tropical climate. "
            "May need licensed spectrum for reliability."
        )

    if width_m > 10_000:
        notes_parts.append(
            f"Very long link ({width_m/1000:.1f} km). "
            "Consider E-band (70/80 GHz) or licensed 18/23 GHz for higher capacity. "
            "Rain fade will reduce availability during heavy storms."
        )

    notes_parts.append(
        f"Estimated permit timeline: {ENVIRONMENTAL_TIMELINE_MONTHS['microwave']} months "
        "(Anatel spectrum authorization + structure permit)."
    )

    return RiverCrossing(
        crossing_type="microwave_link",
        width_m=width_m,
        estimated_cost_brl=round(total_cost, 2),
        installation_time_days=install_days,
        maintenance_risk=risk,
        notes=" ".join(notes_parts),
    )


def design_crossing(
    width_m: float,
    depth_m: float = 10,
    current_speed_ms: float = 1.5,
) -> list[RiverCrossing]:
    """Design river crossing options.

    Generates all feasible crossing options for a given river profile,
    sorted by estimated cost (cheapest first).

    Rules:
    - < 200m: aerial cable on tall poles (cheapest)
    - 200m - 2km: submarine cable or microwave link
    - > 2km: microwave link (submarine too expensive)

    Args:
        width_m: River width at crossing point in meters.
        depth_m: Average depth in meters (affects submarine cable costs).
        current_speed_ms: Average current speed in m/s.

    Returns:
        List of RiverCrossing options sorted by cost (cheapest first).
        May be empty if no crossing is feasible.

    Raises:
        ValueError: If width_m is negative.
    """
    if width_m < 0:
        raise ValueError("River width cannot be negative.")

    if width_m == 0:
        logger.warning("River width is 0 — no crossing needed.")
        return []

    if depth_m < 0:
        depth_m = 0

    if current_speed_ms < 0:
        current_speed_ms = 0

    logger.info(
        "Designing river crossing: %.0f m wide, %.0f m deep, %.1f m/s current",
        width_m,
        depth_m,
        current_speed_ms,
    )

    options: list[RiverCrossing] = []

    # Try all crossing types
    aerial = _design_aerial_crossing(width_m, depth_m, current_speed_ms)
    if aerial is not None:
        options.append(aerial)

    submarine = _design_submarine_crossing(width_m, depth_m, current_speed_ms)
    if submarine is not None:
        options.append(submarine)

    microwave = _design_microwave_crossing(width_m, depth_m, current_speed_ms)
    if microwave is not None:
        options.append(microwave)

    # Sort by cost
    options.sort(key=lambda x: x.estimated_cost_brl)

    if options:
        logger.info(
            "River crossing options (%d feasible): cheapest = %s at R$%.0f",
            len(options),
            options[0].crossing_type,
            options[0].estimated_cost_brl,
        )
    else:
        logger.warning(
            "No feasible crossing options for %.0f m river crossing.",
            width_m,
        )

    return options
