"""ICMS tax rates by Brazilian state for telecom services.

Under SVA (Servico de Valor Adicionado) classification, broadband was EXEMPT
from ICMS in most states because it was treated as an information service
rather than a communications service.

Under SCM (Servico de Comunicacao Multimidia) classification mandated by
Norma no. 4, ICMS applies at state-specific rates.  The telecom-specific
rate is typically higher than the standard ICMS rate because states apply
a surcharge on communication services (Convênio ICMS 69/98 and state
legislation).

Sources:
    - CONFAZ Convênio ICMS 69/98 (original telecom ICMS framework)
    - Individual state tax legislation (RICMS)
    - Abrint (Associação Brasileira de Provedores de Internet) rate survey 2024

All rates are expressed as decimals (e.g. 0.25 = 25%).
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State code -> { "standard": float, "telecom": float, "notes": str }
#
# "standard" = general ICMS rate for the state
# "telecom"  = ICMS rate applied to communication services (SCM)
# ---------------------------------------------------------------------------
ICMS_RATES_SCM: dict[str, dict] = {
    "AC": {"standard": 0.19, "telecom": 0.25, "notes": "Acre"},
    "AL": {"standard": 0.19, "telecom": 0.25, "notes": "Alagoas"},
    "AM": {"standard": 0.20, "telecom": 0.25, "notes": "Amazonas"},
    "AP": {"standard": 0.18, "telecom": 0.25, "notes": "Amapá"},
    "BA": {"standard": 0.205, "telecom": 0.28, "notes": "Bahia — highest telecom ICMS"},
    "CE": {"standard": 0.20, "telecom": 0.28, "notes": "Ceará"},
    "DF": {"standard": 0.20, "telecom": 0.25, "notes": "Distrito Federal"},
    "ES": {"standard": 0.17, "telecom": 0.25, "notes": "Espírito Santo"},
    "GO": {"standard": 0.19, "telecom": 0.29, "notes": "Goiás"},
    "MA": {"standard": 0.22, "telecom": 0.27, "notes": "Maranhão"},
    "MG": {"standard": 0.18, "telecom": 0.25, "notes": "Minas Gerais"},
    "MS": {"standard": 0.17, "telecom": 0.27, "notes": "Mato Grosso do Sul"},
    "MT": {"standard": 0.17, "telecom": 0.25, "notes": "Mato Grosso"},
    "PA": {"standard": 0.19, "telecom": 0.25, "notes": "Pará"},
    "PB": {"standard": 0.20, "telecom": 0.28, "notes": "Paraíba"},
    "PE": {"standard": 0.205, "telecom": 0.28, "notes": "Pernambuco"},
    "PI": {"standard": 0.21, "telecom": 0.27, "notes": "Piauí"},
    "PR": {"standard": 0.195, "telecom": 0.29, "notes": "Paraná"},
    "RJ": {"standard": 0.22, "telecom": 0.25, "notes": "Rio de Janeiro"},
    "RN": {"standard": 0.20, "telecom": 0.28, "notes": "Rio Grande do Norte"},
    "RO": {"standard": 0.195, "telecom": 0.25, "notes": "Rondônia"},
    "RR": {"standard": 0.20, "telecom": 0.25, "notes": "Roraima"},
    "RS": {"standard": 0.17, "telecom": 0.25, "notes": "Rio Grande do Sul"},
    "SC": {"standard": 0.17, "telecom": 0.25, "notes": "Santa Catarina"},
    "SE": {"standard": 0.19, "telecom": 0.27, "notes": "Sergipe"},
    "SP": {"standard": 0.18, "telecom": 0.25, "notes": "São Paulo"},
    "TO": {"standard": 0.20, "telecom": 0.27, "notes": "Tocantins"},
}

# All 27 Brazilian UF codes (26 states + DF)
ALL_STATE_CODES = sorted(ICMS_RATES_SCM.keys())


def get_telecom_icms(state_code: str) -> float:
    """Get the telecom ICMS rate for a given state.

    Args:
        state_code: Two-letter UF code (e.g. 'SP', 'RJ', 'GO').

    Returns:
        Telecom ICMS rate as a decimal (e.g. 0.25 for 25%).

    Raises:
        ValueError: If the state code is not recognized.
    """
    code = state_code.strip().upper()
    if code not in ICMS_RATES_SCM:
        raise ValueError(
            f"Unknown state code '{state_code}'. "
            f"Valid codes: {', '.join(ALL_STATE_CODES)}"
        )
    rate = ICMS_RATES_SCM[code]["telecom"]
    logger.debug("Telecom ICMS for %s: %.1f%%", code, rate * 100)
    return rate


def get_standard_icms(state_code: str) -> float:
    """Get the standard (non-telecom) ICMS rate for a given state.

    Args:
        state_code: Two-letter UF code.

    Returns:
        Standard ICMS rate as a decimal.

    Raises:
        ValueError: If the state code is not recognized.
    """
    code = state_code.strip().upper()
    if code not in ICMS_RATES_SCM:
        raise ValueError(
            f"Unknown state code '{state_code}'. "
            f"Valid codes: {', '.join(ALL_STATE_CODES)}"
        )
    return ICMS_RATES_SCM[code]["standard"]


def get_all_rates() -> dict[str, dict]:
    """Get a copy of all ICMS rates by state.

    Returns:
        Dictionary mapping state codes to rate details.
    """
    return {code: dict(rates) for code, rates in ICMS_RATES_SCM.items()}


def get_highest_rate_states(n: int = 5) -> list[dict]:
    """Get states with the highest telecom ICMS rates.

    Args:
        n: Number of top states to return (default 5).

    Returns:
        List of dicts with 'state_code', 'telecom_rate', and 'notes',
        sorted descending by telecom rate.
    """
    if n <= 0:
        return []

    ranked = sorted(
        ICMS_RATES_SCM.items(),
        key=lambda item: item[1]["telecom"],
        reverse=True,
    )

    results = []
    for code, rates in ranked[:n]:
        results.append({
            "state_code": code,
            "telecom_rate": rates["telecom"],
            "standard_rate": rates["standard"],
            "notes": rates["notes"],
        })

    logger.info(
        "Top %d telecom ICMS states: %s",
        n,
        ", ".join(f"{r['state_code']} ({r['telecom_rate']:.0%})" for r in results),
    )
    return results


def get_lowest_rate_states(n: int = 5) -> list[dict]:
    """Get states with the lowest telecom ICMS rates.

    Args:
        n: Number of bottom states to return (default 5).

    Returns:
        List of dicts with 'state_code', 'telecom_rate', and 'notes',
        sorted ascending by telecom rate.
    """
    if n <= 0:
        return []

    ranked = sorted(
        ICMS_RATES_SCM.items(),
        key=lambda item: item[1]["telecom"],
    )

    return [
        {
            "state_code": code,
            "telecom_rate": rates["telecom"],
            "standard_rate": rates["standard"],
            "notes": rates["notes"],
        }
        for code, rates in ranked[:n]
    ]


def get_rate_for_states(state_codes: list[str]) -> dict[str, float]:
    """Get telecom ICMS rates for multiple states at once.

    Args:
        state_codes: List of two-letter UF codes.

    Returns:
        Dictionary mapping state code to telecom ICMS rate.
        Unknown states are omitted with a warning logged.
    """
    result = {}
    for code in state_codes:
        normalized = code.strip().upper()
        if normalized in ICMS_RATES_SCM:
            result[normalized] = ICMS_RATES_SCM[normalized]["telecom"]
        else:
            logger.warning("Skipping unknown state code: %s", code)
    return result


def compute_blended_rate(state_revenue: dict[str, float]) -> Optional[float]:
    """Compute a revenue-weighted blended telecom ICMS rate.

    Useful for ISPs operating across multiple states.

    Args:
        state_revenue: Dictionary mapping state code to monthly revenue in BRL.
            Example: {"SP": 500_000, "RJ": 200_000, "MG": 100_000}

    Returns:
        Weighted average ICMS rate, or None if no valid states are provided.
    """
    total_revenue = 0.0
    weighted_sum = 0.0

    for code, revenue in state_revenue.items():
        normalized = code.strip().upper()
        if normalized not in ICMS_RATES_SCM:
            logger.warning("Skipping unknown state code in blend: %s", code)
            continue
        if revenue <= 0:
            continue
        rate = ICMS_RATES_SCM[normalized]["telecom"]
        weighted_sum += rate * revenue
        total_revenue += revenue

    if total_revenue <= 0:
        return None

    blended = weighted_sum / total_revenue
    logger.info(
        "Blended ICMS rate across %d states: %.2f%% (total revenue R$%.2f)",
        len(state_revenue),
        blended * 100,
        total_revenue,
    )
    return round(blended, 4)
