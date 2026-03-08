"""Seasonal fault pattern analysis.

Generates monthly risk calendars showing when faults are most likely,
based on historical weather-quality correlation data and known regional
climate patterns for Brazil.
"""

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class MonthlyRisk:
    """Risk assessment for a single calendar month."""

    month: int  # 1-12
    month_name: str
    risk_score: float  # 0-100
    primary_risk_type: str  # "precipitation", "wind", "temperature", "lightning"
    description: str


@dataclass
class SeasonalCalendar:
    """Full-year seasonal risk calendar for a municipality."""

    municipality_id: int
    municipality_name: str
    region: str
    months: list[MonthlyRisk] = field(default_factory=list)
    peak_risk_month: int = 1
    lowest_risk_month: int = 7
    annual_pattern: str = "rainy_season"  # "rainy_season", "year_round", "winter_cycling"


# ---------------------------------------------------------------------------
# Region mapping
# ---------------------------------------------------------------------------

# Maps all 27 Brazilian state abbreviations to their geographic region
REGION_MAP = {
    "AC": "north", "AM": "north", "AP": "north", "PA": "north",
    "RO": "north", "RR": "north", "TO": "north",
    "AL": "northeast", "BA": "northeast", "CE": "northeast",
    "MA": "northeast", "PB": "northeast", "PE": "northeast",
    "PI": "northeast", "RN": "northeast", "SE": "northeast",
    "DF": "central-west", "GO": "central-west",
    "MT": "central-west", "MS": "central-west",
    "ES": "southeast", "MG": "southeast",
    "RJ": "southeast", "SP": "southeast",
    "PR": "south", "RS": "south", "SC": "south",
}


def get_region_from_state(state_code: str) -> str:
    """Map a Brazilian state abbreviation to its geographic region.

    Args:
        state_code: Two-letter state abbreviation (e.g., 'SP', 'BA').

    Returns:
        Region name: 'north', 'northeast', 'southeast', 'south',
        or 'central-west'.  Defaults to 'southeast' for unknown codes.
    """
    return REGION_MAP.get(state_code.strip().upper(), "southeast")


# ---------------------------------------------------------------------------
# Regional risk profile generation
# ---------------------------------------------------------------------------

# Realistic monthly risk profiles per region, derived from INMET climatology.
# Each region has 12 values representing relative risk 0-100 for each month.
# These encode the well-known seasonal precipitation, wind, and temperature
# patterns across Brazil.

_REGIONAL_PROFILES = {
    "north": {
        # Equatorial: heavy rain Dec-May, drier Jun-Nov but still wet
        "scores": [85, 90, 92, 88, 80, 55, 40, 35, 40, 50, 60, 75],
        "risk_types": [
            "precipitation", "precipitation", "precipitation", "precipitation",
            "precipitation", "precipitation", "wind", "wind",
            "wind", "precipitation", "precipitation", "precipitation",
        ],
        "pattern": "year_round",
    },
    "northeast": {
        # Coastal: trade winds Jun-Sep; interior: rainy Jan-May
        "scores": [50, 55, 60, 55, 50, 60, 70, 75, 65, 45, 35, 40],
        "risk_types": [
            "precipitation", "precipitation", "precipitation", "precipitation",
            "precipitation", "wind", "wind", "wind",
            "wind", "wind", "precipitation", "precipitation",
        ],
        "pattern": "rainy_season",
    },
    "southeast": {
        # Strong rainy season Oct-Mar with convective storms
        "scores": [80, 75, 70, 40, 25, 20, 18, 20, 30, 55, 70, 85],
        "risk_types": [
            "precipitation", "precipitation", "precipitation", "wind",
            "temperature", "temperature", "temperature", "temperature",
            "precipitation", "precipitation", "precipitation", "precipitation",
        ],
        "pattern": "rainy_season",
    },
    "south": {
        # Winter temperature cycling May-Aug; storms year-round
        "scores": [55, 50, 45, 40, 65, 70, 72, 68, 55, 50, 55, 55],
        "risk_types": [
            "precipitation", "precipitation", "precipitation", "temperature",
            "temperature", "temperature", "temperature", "temperature",
            "wind", "precipitation", "precipitation", "precipitation",
        ],
        "pattern": "winter_cycling",
    },
    "central-west": {
        # Lightning corridor Sep-Feb; dry May-Aug
        "scores": [80, 75, 65, 40, 20, 15, 12, 18, 50, 70, 80, 85],
        "risk_types": [
            "lightning", "lightning", "precipitation", "precipitation",
            "wind", "wind", "wind", "wind",
            "lightning", "lightning", "lightning", "lightning",
        ],
        "pattern": "rainy_season",
    },
}

# Month name lookup (Portuguese)
_MONTH_NAMES_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Marco", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}

# Risk type descriptions per region/month
_RISK_DESCRIPTIONS = {
    "precipitation": {
        "high": "Heavy rainfall expected. Risk of aerial cable damage and splice enclosure water ingress.",
        "moderate": "Moderate rainfall. Standard maintenance vigilance advised.",
        "low": "Dry period. Low precipitation-related fault risk.",
    },
    "wind": {
        "high": "Strong winds expected. Risk of pole stress, cable sway, and tree-on-line events.",
        "moderate": "Moderate wind conditions. Monitor aerial plant exposure.",
        "low": "Calm conditions. Low wind-related fault risk.",
    },
    "temperature": {
        "high": "Temperature cycling stress. Risk of cable expansion/contraction and thermal equipment failure.",
        "moderate": "Moderate temperature variation. Monitor outdoor equipment enclosures.",
        "low": "Stable temperatures. Low thermal stress risk.",
    },
    "lightning": {
        "high": "Active lightning corridor. Risk of equipment damage and power surges. Check surge protection.",
        "moderate": "Occasional storms possible. Verify UPS and grounding systems.",
        "low": "Low storm activity. Routine lightning protection maintenance.",
    },
}


def _risk_intensity(score: float) -> str:
    """Map score to intensity label for description lookup."""
    if score >= 60:
        return "high"
    if score >= 30:
        return "moderate"
    return "low"


def generate_risk_pattern(region: str) -> list[MonthlyRisk]:
    """Generate monthly risk pattern based on region.

    Uses the pre-computed regional profiles to create a 12-month risk
    calendar with appropriate risk types and descriptions.

    Args:
        region: Brazilian geographic region (e.g., 'southeast').

    Returns:
        List of 12 MonthlyRisk entries, one per calendar month.
    """
    profile = _REGIONAL_PROFILES.get(region, _REGIONAL_PROFILES["southeast"])
    scores = profile["scores"]
    risk_types = profile["risk_types"]

    monthly_risks = []
    for i in range(12):
        month_num = i + 1
        score = scores[i]
        rtype = risk_types[i]
        intensity = _risk_intensity(score)
        description = _RISK_DESCRIPTIONS.get(rtype, {}).get(
            intensity,
            f"Risk score {score}/100 for {rtype}.",
        )

        monthly_risks.append(
            MonthlyRisk(
                month=month_num,
                month_name=_MONTH_NAMES_PT.get(month_num, calendar.month_name[month_num]),
                risk_score=float(score),
                primary_risk_type=rtype,
                description=description,
            )
        )

    return monthly_risks


# ---------------------------------------------------------------------------
# Data-driven profile adjustment
# ---------------------------------------------------------------------------


def _adjust_profile_with_data(
    base_risks: list[MonthlyRisk],
    municipality_id: int,
    conn,
) -> list[MonthlyRisk]:
    """Adjust regional risk profile using actual weather observation data.

    If historical weather data exists for the nearest station, we blend the
    regional default with station-specific severity to produce a more
    accurate local profile.

    Falls back to the unmodified base_risks if data is sparse.
    """
    from python.ml.health.weather_correlation import (
        _find_nearest_station,
        _score_precipitation_risk,
        _score_wind_risk,
        _score_temperature_risk,
        compute_monthly_metrics,
    )

    station_id = _find_nearest_station(municipality_id, conn)
    if station_id is None:
        return base_risks

    today = date.today()
    # Collect per-month average scores from the last 2 years of observations
    month_scores: dict[int, list[float]] = {m: [] for m in range(1, 13)}

    for year_offset in range(2):
        year = today.year - year_offset - 1  # -1 and -2 years
        for month in range(1, 13):
            metrics = compute_monthly_metrics(station_id, year, month, conn)
            # Only use if there is actual data
            if (
                metrics.total_precipitation_mm == 0
                and metrics.max_wind_speed_ms == 0
                and metrics.temperature_range == 0
            ):
                continue

            composite = (
                0.50 * _score_precipitation_risk(metrics)
                + 0.30 * _score_wind_risk(metrics)
                + 0.20 * _score_temperature_risk(metrics)
            )
            month_scores[month].append(composite)

    # Blend observed data with regional defaults (70/30 when data exists)
    adjusted = []
    for risk in base_risks:
        observed = month_scores.get(risk.month, [])
        if observed:
            obs_avg = sum(observed) / len(observed)
            blended = 0.7 * obs_avg + 0.3 * risk.risk_score
            adjusted.append(
                MonthlyRisk(
                    month=risk.month,
                    month_name=risk.month_name,
                    risk_score=round(blended, 1),
                    primary_risk_type=risk.primary_risk_type,
                    description=risk.description,
                )
            )
        else:
            adjusted.append(risk)

    return adjusted


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_seasonal_calendar(
    municipality_id: int, conn=None,
) -> SeasonalCalendar:
    """Generate seasonal risk calendar for a municipality.

    Determines the municipality's geographic region, generates a base
    risk profile from regional climatology, then adjusts with local
    weather observation data if available.

    Args:
        municipality_id: admin_level_2.id
        conn: Optional database connection.

    Returns:
        SeasonalCalendar with 12-month risk profile.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return _default_calendar(municipality_id)

    try:
        # Fetch municipality metadata
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a2.name, a1.abbrev
                FROM admin_level_2 a2
                JOIN admin_level_1 a1 ON a1.id = a2.l1_id
                WHERE a2.id = %s
                """,
                (municipality_id,),
            )
            row = cur.fetchone()

        if not row:
            logger.warning("Municipality %d not found", municipality_id)
            return _default_calendar(municipality_id)

        muni_name = row[0]
        state_code = row[1].strip() if row[1] else "SP"
        region = get_region_from_state(state_code)

        # Generate base profile from regional patterns
        base_risks = generate_risk_pattern(region)

        # Adjust with local weather data
        adjusted_risks = _adjust_profile_with_data(base_risks, municipality_id, conn)

        # Find peak and lowest risk months
        peak_month = max(adjusted_risks, key=lambda r: r.risk_score).month
        lowest_month = min(adjusted_risks, key=lambda r: r.risk_score).month

        profile = _REGIONAL_PROFILES.get(region, _REGIONAL_PROFILES["southeast"])
        annual_pattern = profile.get("pattern", "rainy_season")

        cal = SeasonalCalendar(
            municipality_id=municipality_id,
            municipality_name=muni_name,
            region=region,
            months=adjusted_risks,
            peak_risk_month=peak_month,
            lowest_risk_month=lowest_month,
            annual_pattern=annual_pattern,
        )

        logger.info(
            "Seasonal calendar for %s (region=%s): peak=%s (month %d), "
            "lowest=%s (month %d), pattern=%s",
            muni_name,
            region,
            _MONTH_NAMES_PT.get(peak_month, str(peak_month)),
            peak_month,
            _MONTH_NAMES_PT.get(lowest_month, str(lowest_month)),
            lowest_month,
            annual_pattern,
        )

        return cal

    except Exception as exc:
        logger.error(
            "Error generating seasonal calendar for municipality %d: %s",
            municipality_id, exc,
        )
        return _default_calendar(municipality_id)
    finally:
        if own_conn:
            conn.close()


def _default_calendar(municipality_id: int) -> SeasonalCalendar:
    """Return a default southeast-region calendar when DB is unavailable."""
    risks = generate_risk_pattern("southeast")
    peak = max(risks, key=lambda r: r.risk_score).month
    lowest = min(risks, key=lambda r: r.risk_score).month

    return SeasonalCalendar(
        municipality_id=municipality_id,
        municipality_name=f"Municipality {municipality_id}",
        region="southeast",
        months=risks,
        peak_risk_month=peak,
        lowest_risk_month=lowest,
        annual_pattern="rainy_season",
    )
