"""Solar power system sizing for off-grid telecom sites.

Uses regional solar irradiance data for Brazil to size panel arrays,
battery banks, charge controllers, and inverters for autonomous
off-grid operation.

Design methodology follows CRESESB (Centro de Referencia para Energia
Solar e Eolica Sergio Brito) guidelines and common Brazilian off-grid
telecom practices.

Sources:
    - CRESESB Solar Atlas of Brazil
    - INPE solar irradiance data
    - BNDES off-grid telecom financing guidelines
"""

import logging
import math
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Solar irradiance by Brazilian region (kWh/m^2/day)
# Values represent typical horizontal surface irradiance.
# ---------------------------------------------------------------------------
SOLAR_IRRADIANCE = {
    "north": {"worst_month": 3.5, "best_month": 5.5, "annual_avg": 4.5},
    "northeast": {"worst_month": 4.5, "best_month": 6.5, "annual_avg": 5.5},
    "central-west": {"worst_month": 4.0, "best_month": 6.0, "annual_avg": 5.0},
    "southeast": {"worst_month": 3.5, "best_month": 5.5, "annual_avg": 4.5},
    "south": {"worst_month": 3.0, "best_month": 5.0, "annual_avg": 4.0},
}

# ---------------------------------------------------------------------------
# Equipment parameters
# ---------------------------------------------------------------------------
# Standard panel sizes commonly available in Brazil
PANEL_OPTIONS_WATTS = [330, 400, 450, 550]

# Battery parameters
BATTERY_PARAMS = {
    "lithium": {
        "depth_of_discharge": 0.80,  # 80% DoD for LiFePO4
        "round_trip_efficiency": 0.95,
        "unit_kwh": 5.12,  # Typical 48V 100Ah LiFePO4 module
        "cost_per_kwh_brl": 2_500,
        "lifespan_years": 10,
        "lifespan_cycles": 4000,
    },
    "lead_acid": {
        "depth_of_discharge": 0.50,  # 50% DoD for deep cycle lead-acid
        "round_trip_efficiency": 0.85,
        "unit_kwh": 2.4,  # Typical 12V 200Ah deep cycle
        "cost_per_kwh_brl": 800,
        "lifespan_years": 3,
        "lifespan_cycles": 1200,
    },
}

# System loss factors
SYSTEM_LOSSES = {
    "inverter_efficiency": 0.93,
    "cable_losses": 0.03,
    "controller_losses": 0.02,
    "dust_degradation": 0.05,
    "temperature_derating": 0.10,  # Tropical climate derating
    "total_derating_factor": 0.85,  # Combined panel derating
}

# Cost benchmarks (BRL)
COMPONENT_COSTS = {
    "panel_per_watt_brl": 2.50,
    "charge_controller_per_amp_brl": 35.0,
    "inverter_per_watt_brl": 1.80,
    "mounting_structure_per_panel_brl": 350,
    "cabling_and_protection_brl": 3_000,
    "installation_labor_brl": 5_000,
    "annual_maintenance_per_kw_brl": 500,
}


@dataclass
class SolarDesign:
    """Complete solar power system design.

    Attributes:
        panel_array_kwp: Total panel array capacity in kWp.
        panel_count: Number of panels.
        panel_watts: Wattage of each panel.
        battery_kwh: Total battery bank capacity in kWh.
        battery_count: Number of battery modules.
        battery_type: Battery chemistry type.
        charge_controller_amps: Charge controller rating in amps.
        inverter_watts: Inverter rating in watts.
        estimated_capex_brl: Total estimated capital cost in BRL.
        annual_maintenance_brl: Estimated annual maintenance cost.
        system_lifespan_years: Expected system lifespan.
        notes: Design notes and warnings.
    """

    panel_array_kwp: float
    panel_count: int
    panel_watts: int
    battery_kwh: float
    battery_count: int
    battery_type: str  # "lithium" or "lead_acid"
    charge_controller_amps: int
    inverter_watts: int
    estimated_capex_brl: float
    annual_maintenance_brl: float
    system_lifespan_years: int
    notes: list[str]


def _get_region_from_latitude(latitude: float) -> str:
    """Infer Brazilian region from latitude for irradiance lookup.

    Uses simplified latitude bands:
        North:        lat > -5
        Northeast:    -5 >= lat > -12 (east side, approximated)
        Central-West: -5 >= lat > -18 (west side, approximated)
        Southeast:    -18 >= lat > -24
        South:        lat <= -24
    """
    if latitude > -5.0:
        return "north"
    if latitude > -12.0:
        return "northeast"
    if latitude > -18.0:
        return "central-west"
    if latitude > -24.0:
        return "southeast"
    return "south"


def _select_panel_size(required_kwp: float) -> int:
    """Select the most appropriate panel wattage.

    Prefers larger panels for bigger systems to reduce panel count
    and mounting hardware.
    """
    if required_kwp <= 1.0:
        return 330
    if required_kwp <= 3.0:
        return 400
    if required_kwp <= 6.0:
        return 450
    return 550


def size_solar_system(
    latitude: float,
    longitude: float,
    power_consumption_watts: float,
    autonomy_days: int = 3,
    battery_type: str = "lithium",
) -> SolarDesign:
    """Size a complete solar power system for an off-grid telecom site.

    Calculation methodology:
    1. Daily energy = power_watts * 24 / 1000 (kWh/day)
    2. Adjusted daily energy = daily * 1.25 (inverter + cable + controller losses)
    3. Panel array kWp = adjusted / worst_month_irradiance / derating_factor
    4. Battery capacity = daily * autonomy_days / DoD

    All costs are in BRL and based on current Brazilian market pricing.

    Args:
        latitude: Site latitude (decimal degrees).
        longitude: Site longitude (decimal degrees).
        power_consumption_watts: Continuous power draw of equipment in watts.
        autonomy_days: Number of days of battery autonomy (no sun). Default 3.
        battery_type: Battery chemistry ("lithium" or "lead_acid"). Default "lithium".

    Returns:
        Complete SolarDesign with all component sizes and costs.

    Raises:
        ValueError: If power_consumption_watts is negative or battery_type is unknown.
    """
    if power_consumption_watts < 0:
        raise ValueError("Power consumption cannot be negative.")

    if battery_type not in BATTERY_PARAMS:
        raise ValueError(
            f"Unknown battery type '{battery_type}'. "
            f"Supported: {list(BATTERY_PARAMS.keys())}"
        )

    if autonomy_days < 1:
        autonomy_days = 1
        logger.warning("Autonomy days < 1, defaulting to 1.")

    notes: list[str] = []

    # Handle edge case: zero power consumption
    if power_consumption_watts == 0:
        logger.warning("Power consumption is 0 W. Returning minimal design.")
        return SolarDesign(
            panel_array_kwp=0.0,
            panel_count=0,
            panel_watts=0,
            battery_kwh=0.0,
            battery_count=0,
            battery_type=battery_type,
            charge_controller_amps=0,
            inverter_watts=0,
            estimated_capex_brl=0.0,
            annual_maintenance_brl=0.0,
            system_lifespan_years=0,
            notes=["No power consumption specified. No system needed."],
        )

    # Step 1: Determine region and irradiance
    region = _get_region_from_latitude(latitude)
    irradiance = SOLAR_IRRADIANCE.get(region, SOLAR_IRRADIANCE["southeast"])
    worst_month_irradiance = irradiance["worst_month"]

    logger.info(
        "Solar sizing at (%.4f, %.4f): region=%s, worst-month irradiance=%.1f kWh/m^2/day",
        latitude,
        longitude,
        region,
        worst_month_irradiance,
    )

    # Step 2: Calculate daily energy requirement
    daily_energy_kwh = power_consumption_watts * 24 / 1000.0

    # Step 3: Adjust for system losses
    loss_factor = (
        1.0
        / SYSTEM_LOSSES["inverter_efficiency"]
        * (1.0 + SYSTEM_LOSSES["cable_losses"])
        * (1.0 + SYSTEM_LOSSES["controller_losses"])
    )
    adjusted_daily_kwh = daily_energy_kwh * loss_factor

    # Step 4: Size panel array
    derating = SYSTEM_LOSSES["total_derating_factor"]
    required_kwp = adjusted_daily_kwh / (worst_month_irradiance * derating)

    # Select panel size and calculate count
    panel_watts = _select_panel_size(required_kwp)
    panel_count = max(1, math.ceil(required_kwp * 1000 / panel_watts))
    actual_kwp = panel_count * panel_watts / 1000.0

    # Step 5: Size battery bank
    battery_params = BATTERY_PARAMS[battery_type]
    dod = battery_params["depth_of_discharge"]
    efficiency = battery_params["round_trip_efficiency"]

    # Usable capacity needed = daily_energy * autonomy_days
    usable_kwh_needed = adjusted_daily_kwh * autonomy_days
    # Total capacity = usable / DoD / round-trip efficiency
    total_battery_kwh = usable_kwh_needed / dod / efficiency

    unit_kwh = battery_params["unit_kwh"]
    battery_count = max(1, math.ceil(total_battery_kwh / unit_kwh))
    actual_battery_kwh = battery_count * unit_kwh

    # Step 6: Size charge controller
    # Controller amps = panel array watts / system voltage (48V typical)
    system_voltage = 48
    controller_amps = math.ceil(actual_kwp * 1000 / system_voltage * 1.25)  # 25% margin
    # Round up to nearest standard size (30, 40, 60, 80, 100 A)
    standard_sizes = [30, 40, 60, 80, 100, 150, 200]
    controller_amps = next(
        (s for s in standard_sizes if s >= controller_amps),
        standard_sizes[-1],
    )

    # Step 7: Size inverter
    # Inverter should handle peak load + 30% margin
    inverter_watts = math.ceil(power_consumption_watts * 1.3)
    # Round up to nearest standard size
    standard_inverter_sizes = [500, 1000, 1500, 2000, 3000, 5000, 8000, 10000]
    inverter_watts = next(
        (s for s in standard_inverter_sizes if s >= inverter_watts),
        standard_inverter_sizes[-1],
    )

    # Step 8: Calculate costs
    panel_cost = actual_kwp * 1000 * COMPONENT_COSTS["panel_per_watt_brl"]
    mounting_cost = panel_count * COMPONENT_COSTS["mounting_structure_per_panel_brl"]
    battery_cost = actual_battery_kwh * battery_params["cost_per_kwh_brl"]
    controller_cost = controller_amps * COMPONENT_COSTS["charge_controller_per_amp_brl"]
    inverter_cost = inverter_watts * COMPONENT_COSTS["inverter_per_watt_brl"]
    cabling_cost = COMPONENT_COSTS["cabling_and_protection_brl"]
    labor_cost = COMPONENT_COSTS["installation_labor_brl"]

    total_capex = (
        panel_cost
        + mounting_cost
        + battery_cost
        + controller_cost
        + inverter_cost
        + cabling_cost
        + labor_cost
    )

    annual_maintenance = actual_kwp * COMPONENT_COSTS["annual_maintenance_per_kw_brl"]
    system_lifespan = battery_params["lifespan_years"]

    # Step 9: Generate notes
    notes.append(
        f"Region: {region}, worst-month irradiance: {worst_month_irradiance} kWh/m^2/day."
    )
    notes.append(
        f"Daily energy: {daily_energy_kwh:.2f} kWh, adjusted: {adjusted_daily_kwh:.2f} kWh."
    )

    if battery_type == "lead_acid":
        notes.append(
            "Lead-acid batteries have shorter lifespan (3-4 years) and lower DoD (50%). "
            "Consider lithium (LiFePO4) for lower total cost of ownership."
        )

    if actual_kwp > 5.0:
        notes.append(
            f"Large system ({actual_kwp:.1f} kWp). Consider split installation "
            "or multiple charge controllers for redundancy."
        )

    if region == "south":
        notes.append(
            "Southern Brazil has lower irradiance. Consider increasing panel array "
            "by 10-15% for margin."
        )

    if autonomy_days > 5:
        notes.append(
            f"High autonomy ({autonomy_days} days) results in large battery bank. "
            "Consider reducing autonomy if generator backup is available."
        )

    design = SolarDesign(
        panel_array_kwp=round(actual_kwp, 2),
        panel_count=panel_count,
        panel_watts=panel_watts,
        battery_kwh=round(actual_battery_kwh, 2),
        battery_count=battery_count,
        battery_type=battery_type,
        charge_controller_amps=controller_amps,
        inverter_watts=inverter_watts,
        estimated_capex_brl=round(total_capex, 2),
        annual_maintenance_brl=round(annual_maintenance, 2),
        system_lifespan_years=system_lifespan,
        notes=notes,
    )

    logger.info(
        "Solar design: %.2f kWp (%d x %dW), %.1f kWh battery (%d x %.1f kWh %s), "
        "%dA controller, %dW inverter — CAPEX R$%,.0f",
        actual_kwp,
        panel_count,
        panel_watts,
        actual_battery_kwh,
        battery_count,
        unit_kwh,
        battery_type,
        controller_amps,
        inverter_watts,
        total_capex,
    )

    return design
