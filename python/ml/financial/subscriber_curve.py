"""Bass diffusion subscriber uptake model for broadband market projections.

Models cumulative subscriber growth using a modified Bass diffusion curve:

    S(t) = M * [1 - e^(-k*(t-t0))] / [1 + q*e^(-k*(t-t0))]

Where:
    S(t) = cumulative subscribers at month t
    M    = market ceiling (addressable households * maximum penetration rate)
    k    = growth rate parameter
    t0   = inflection point (month of fastest growth)
    q    = imitation coefficient (word-of-mouth effect)

Parameter calibration is based on empirical data from Brazilian ISP launches,
with adjustments for urbanization level and competitive intensity.
"""

import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Growth rate (k) ranges by area type
# ---------------------------------------------------------------------------
K_RANGES = {
    "urban":    (0.15, 0.25),
    "suburban": (0.10, 0.15),
    "rural":    (0.05, 0.10),
}

# ---------------------------------------------------------------------------
# Inflection point (t0) ranges in months by area type
# ---------------------------------------------------------------------------
T0_RANGES = {
    "urban":    (8, 12),
    "suburban": (12, 18),
    "rural":    (18, 24),
}

# ---------------------------------------------------------------------------
# Imitation coefficient (q) ranges by competition level
# ---------------------------------------------------------------------------
Q_RANGES = {
    "low":      (1.0, 1.5),   # Little competition -> strong word-of-mouth
    "moderate": (0.7, 1.2),
    "high":     (0.5, 0.8),   # Heavy competition -> slower viral adoption
}


def bass_diffusion(t: float, M: float, k: float, t0: float, q: float) -> float:
    """Compute cumulative subscribers at month *t* using Bass diffusion.

    Args:
        t:  Month number (0-indexed).
        M:  Market ceiling (maximum subscribers).
        k:  Growth rate parameter.
        t0: Inflection point month.
        q:  Imitation / word-of-mouth coefficient.

    Returns:
        Predicted cumulative subscriber count (float, non-negative).
    """
    if M <= 0:
        return 0.0
    if k <= 0:
        return 0.0

    exponent = -k * (t - t0)
    # Clamp to avoid overflow in math.exp
    exponent = max(-500.0, min(500.0, exponent))

    exp_val = math.exp(exponent)
    numerator = 1.0 - exp_val
    denominator = 1.0 + q * exp_val

    if denominator <= 0:
        return 0.0

    result = M * numerator / denominator
    # Subscriber count cannot be negative (early months before inflection)
    return max(0.0, result)


def _classify_area(urbanization_rate: float) -> str:
    """Classify an area as urban/suburban/rural based on urbanization rate."""
    if urbanization_rate >= 0.75:
        return "urban"
    elif urbanization_rate >= 0.40:
        return "suburban"
    else:
        return "rural"


def _percentile_param(low: float, high: float, percentile: float) -> float:
    """Linearly interpolate between low and high at the given percentile.

    Args:
        low:  Lower bound of the range.
        high: Upper bound of the range.
        percentile: Value in [0, 1] where 0.25 = pessimistic, 0.5 = base,
                     0.75 = optimistic.
    """
    return low + (high - low) * percentile


def project_subscribers(
    addressable_households: int,
    penetration_ceiling: float,
    months: int = 36,
    urbanization_rate: float = 0.6,
    competition_level: str = "moderate",
) -> dict:
    """Project subscriber uptake over time for three scenarios.

    Args:
        addressable_households: Number of households in the target area that
            could potentially subscribe.
        penetration_ceiling: Maximum achievable penetration rate (0-1).
        months: Projection horizon in months (default 36).
        urbanization_rate: Fraction of the area classified as urban (0-1).
        competition_level: One of 'low', 'moderate', 'high'.

    Returns:
        Dictionary with keys:
            pessimistic: list[int] of monthly cumulative subscribers (25th pctl)
            base_case:   list[int] of monthly cumulative subscribers (median)
            optimistic:  list[int] of monthly cumulative subscribers (75th pctl)
            parameters:  dict with the calibrated parameters per scenario
    """
    if addressable_households <= 0 or penetration_ceiling <= 0:
        empty = [0] * months
        return {
            "pessimistic": list(empty),
            "base_case": list(empty),
            "optimistic": list(empty),
            "parameters": {},
        }

    # Market ceiling
    M = int(addressable_households * min(penetration_ceiling, 1.0))
    if M <= 0:
        empty = [0] * months
        return {
            "pessimistic": list(empty),
            "base_case": list(empty),
            "optimistic": list(empty),
            "parameters": {},
        }

    area_type = _classify_area(urbanization_rate)
    comp = competition_level.lower() if competition_level else "moderate"
    if comp not in Q_RANGES:
        logger.warning("Unknown competition_level '%s', defaulting to 'moderate'", comp)
        comp = "moderate"

    k_lo, k_hi = K_RANGES[area_type]
    t0_lo, t0_hi = T0_RANGES[area_type]
    q_lo, q_hi = Q_RANGES[comp]

    scenarios = {}
    params_out = {}

    for label, pctl in [("pessimistic", 0.25), ("base_case", 0.50), ("optimistic", 0.75)]:
        k = _percentile_param(k_lo, k_hi, pctl)
        # For t0, pessimistic means *later* inflection (slower ramp), so invert
        t0 = _percentile_param(t0_hi, t0_lo, pctl)
        q = _percentile_param(q_lo, q_hi, pctl)

        # For pessimistic scenario, use a lower effective ceiling
        if label == "pessimistic":
            effective_M = int(M * 0.75)
        elif label == "optimistic":
            effective_M = int(M * 1.10)  # slight over-performance possible
        else:
            effective_M = M

        curve = []
        for t in range(months):
            subs = bass_diffusion(t, effective_M, k, t0, q)
            curve.append(int(round(subs)))

        scenarios[label] = curve
        params_out[label] = {
            "M": effective_M,
            "k": round(k, 4),
            "t0": round(t0, 2),
            "q": round(q, 4),
        }

    logger.info(
        "Projected subscribers for %d addressable HH, area=%s, competition=%s: "
        "pessimistic=%d, base=%d, optimistic=%d at month %d",
        addressable_households,
        area_type,
        comp,
        scenarios["pessimistic"][-1],
        scenarios["base_case"][-1],
        scenarios["optimistic"][-1],
        months,
    )

    return {
        "pessimistic": scenarios["pessimistic"],
        "base_case": scenarios["base_case"],
        "optimistic": scenarios["optimistic"],
        "parameters": params_out,
    }
