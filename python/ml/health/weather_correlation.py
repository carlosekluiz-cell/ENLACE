"""Weather-fault correlation model.

HYPOTHESIS: Network faults correlate with weather events:
- Heavy rainfall -> aerial fiber damage, splice enclosure water ingress
- High winds -> pole stress, cable sway, tree-on-line events
- Lightning -> equipment damage, power surge
- Temperature extremes -> cable expansion/contraction, equipment thermal failure

DATA: INMET weather observations + Anatel quality indicators per municipality per month

MODEL: For each municipality, compute monthly weather severity metrics
and correlate with quality degradation.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WeatherRisk:
    """Weather-related fault risk assessment for a municipality."""

    municipality_id: int
    municipality_name: str
    overall_risk_score: float  # 0-100
    precipitation_risk: str  # "low", "moderate", "high", "critical"
    wind_risk: str
    temperature_risk: str
    details: dict = field(default_factory=dict)


@dataclass
class MonthlyWeatherMetrics:
    """Aggregated weather severity metrics for a single month."""

    total_precipitation_mm: float
    max_daily_precipitation_mm: float
    max_wind_speed_ms: float
    temperature_range: float
    consecutive_rain_days: int
    avg_humidity_pct: float


# ---------------------------------------------------------------------------
# Brazilian regional weather risk patterns
# ---------------------------------------------------------------------------

REGIONAL_RISK_PATTERNS = {
    "north": {
        "description": "Year-round high precipitation",
        "peak_risk_months": [1, 2, 3, 4, 5, 12],
        "primary_risk": "precipitation",
    },
    "northeast": {
        "description": "Wind-related faults more common on coast",
        "peak_risk_months": [7, 8, 9],
        "primary_risk": "wind",
    },
    "southeast": {
        "description": "Rainy season October-March",
        "peak_risk_months": [10, 11, 12, 1, 2, 3],
        "primary_risk": "precipitation",
    },
    "south": {
        "description": "Winter temperature cycling affects buried infrastructure",
        "peak_risk_months": [5, 6, 7, 8],
        "primary_risk": "temperature",
    },
    "central-west": {
        "description": "Lightning corridor - equipment damage spikes",
        "peak_risk_months": [9, 10, 11, 12, 1, 2],
        "primary_risk": "lightning",
    },
}

# Thresholds for risk categorisation (calibrated against INMET records)
PRECIPITATION_THRESHOLDS = {
    "daily_heavy_mm": 50.0,       # > 50 mm/day = heavy rain event
    "monthly_high_mm": 300.0,     # > 300 mm/month = high-risk month
    "monthly_critical_mm": 500.0, # > 500 mm/month = critical
}

WIND_THRESHOLDS = {
    "high_ms": 15.0,       # > 15 m/s = high wind event
    "critical_ms": 25.0,   # > 25 m/s = severe
}

TEMPERATURE_THRESHOLDS = {
    "high_range_c": 20.0,   # > 20 C daily range = stress on cables
    "critical_range_c": 30.0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def get_risk_level(score: float) -> str:
    """Convert numeric score (0-100) to risk level label."""
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "moderate"
    return "low"


def _find_nearest_station(municipality_id: int, conn) -> Optional[int]:
    """Find the nearest active weather station to a municipality centroid.

    Uses PostGIS ST_Distance on geography casts for accurate distance
    ordering, limited to 200 km radius.

    Returns:
        weather_stations.id or None if no station found.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT ws.id
            FROM weather_stations ws
            JOIN admin_level_2 a2 ON TRUE
            WHERE a2.id = %s
              AND a2.centroid IS NOT NULL
              AND ws.active = TRUE
            ORDER BY ws.geom::geography <-> a2.centroid::geography
            LIMIT 1
            """,
            (municipality_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def _get_municipality_region(municipality_id: int, conn) -> tuple[str, str]:
    """Return (state_abbrev, region) for a municipality.

    Falls back to ('SP', 'southeast') when data is unavailable.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a1.abbrev
            FROM admin_level_2 a2
            JOIN admin_level_1 a1 ON a1.id = a2.l1_id
            WHERE a2.id = %s
            """,
            (municipality_id,),
        )
        row = cur.fetchone()

    if not row or not row[0]:
        return "SP", "southeast"

    from python.ml.health.seasonal_patterns import get_region_from_state

    state = row[0].strip()
    return state, get_region_from_state(state)


def _get_municipality_name(municipality_id: int, conn) -> str:
    """Return the municipality name for a given id."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT name FROM admin_level_2 WHERE id = %s",
            (municipality_id,),
        )
        row = cur.fetchone()
    return row[0] if row else f"Municipality {municipality_id}"


# ---------------------------------------------------------------------------
# Monthly metrics computation
# ---------------------------------------------------------------------------


def compute_monthly_metrics(
    station_id: int, year: int, month: int, conn=None,
) -> MonthlyWeatherMetrics:
    """Compute monthly weather severity metrics for a station.

    Queries weather_observations for the given year/month and aggregates
    into summary metrics relevant for fault risk assessment.

    If no data exists for the period, returns zero-valued metrics.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return MonthlyWeatherMetrics(
                total_precipitation_mm=0.0,
                max_daily_precipitation_mm=0.0,
                max_wind_speed_ms=0.0,
                temperature_range=0.0,
                consecutive_rain_days=0,
                avg_humidity_pct=0.0,
            )

    try:
        ym_start = f"{year}-{month:02d}-01"
        # Next month start
        if month == 12:
            ym_end = f"{year + 1}-01-01"
        else:
            ym_end = f"{year}-{month + 1:02d}-01"

        with conn.cursor() as cur:
            # Aggregate daily metrics from hourly observations
            cur.execute(
                """
                SELECT
                    observed_at::date AS obs_day,
                    COALESCE(SUM(precipitation_mm), 0) AS daily_precip,
                    COALESCE(MAX(wind_speed_ms), 0) AS max_wind,
                    COALESCE(MAX(temperature_c), 0) - COALESCE(MIN(temperature_c), 0)
                        AS temp_range,
                    COALESCE(AVG(humidity_pct), 0) AS avg_hum
                FROM weather_observations
                WHERE station_id = %s
                  AND observed_at >= %s
                  AND observed_at < %s
                GROUP BY observed_at::date
                ORDER BY obs_day
                """,
                (station_id, ym_start, ym_end),
            )
            rows = cur.fetchall()

        if not rows:
            logger.debug(
                "No weather data for station %d in %04d-%02d",
                station_id, year, month,
            )
            return MonthlyWeatherMetrics(
                total_precipitation_mm=0.0,
                max_daily_precipitation_mm=0.0,
                max_wind_speed_ms=0.0,
                temperature_range=0.0,
                consecutive_rain_days=0,
                avg_humidity_pct=0.0,
            )

        total_precip = 0.0
        max_daily_precip = 0.0
        max_wind = 0.0
        max_temp_range = 0.0
        total_humidity = 0.0
        consecutive_rain = 0
        current_rain_streak = 0

        for _day, daily_precip, wind, temp_range, avg_hum in rows:
            total_precip += daily_precip
            max_daily_precip = max(max_daily_precip, daily_precip)
            max_wind = max(max_wind, wind)
            max_temp_range = max(max_temp_range, temp_range)
            total_humidity += avg_hum

            if daily_precip > 1.0:  # > 1 mm counts as a rain day
                current_rain_streak += 1
                consecutive_rain = max(consecutive_rain, current_rain_streak)
            else:
                current_rain_streak = 0

        avg_humidity = total_humidity / len(rows) if rows else 0.0

        return MonthlyWeatherMetrics(
            total_precipitation_mm=round(total_precip, 2),
            max_daily_precipitation_mm=round(max_daily_precip, 2),
            max_wind_speed_ms=round(max_wind, 2),
            temperature_range=round(max_temp_range, 2),
            consecutive_rain_days=consecutive_rain,
            avg_humidity_pct=round(avg_humidity, 2),
        )
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Risk scoring
# ---------------------------------------------------------------------------


def _score_precipitation_risk(metrics: MonthlyWeatherMetrics) -> float:
    """Score precipitation risk 0-100 from monthly metrics."""
    score = 0.0

    # Total monthly precipitation
    if metrics.total_precipitation_mm >= PRECIPITATION_THRESHOLDS["monthly_critical_mm"]:
        score += 50
    elif metrics.total_precipitation_mm >= PRECIPITATION_THRESHOLDS["monthly_high_mm"]:
        score += 30
    elif metrics.total_precipitation_mm >= 150:
        score += 15

    # Max daily event intensity
    if metrics.max_daily_precipitation_mm >= PRECIPITATION_THRESHOLDS["daily_heavy_mm"]:
        score += 30
    elif metrics.max_daily_precipitation_mm >= 25:
        score += 15

    # Consecutive rain days (saturation increases fault probability)
    if metrics.consecutive_rain_days >= 7:
        score += 20
    elif metrics.consecutive_rain_days >= 4:
        score += 10

    return min(100.0, score)


def _score_wind_risk(metrics: MonthlyWeatherMetrics) -> float:
    """Score wind risk 0-100 from monthly metrics."""
    if metrics.max_wind_speed_ms >= WIND_THRESHOLDS["critical_ms"]:
        return 90.0
    if metrics.max_wind_speed_ms >= WIND_THRESHOLDS["high_ms"]:
        return 60.0
    if metrics.max_wind_speed_ms >= 10:
        return 30.0
    if metrics.max_wind_speed_ms >= 5:
        return 10.0
    return 0.0


def _score_temperature_risk(metrics: MonthlyWeatherMetrics) -> float:
    """Score temperature risk 0-100 from monthly metrics."""
    if metrics.temperature_range >= TEMPERATURE_THRESHOLDS["critical_range_c"]:
        return 80.0
    if metrics.temperature_range >= TEMPERATURE_THRESHOLDS["high_range_c"]:
        return 50.0
    if metrics.temperature_range >= 15:
        return 25.0
    if metrics.temperature_range >= 10:
        return 10.0
    return 0.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_weather_risk(municipality_id: int, conn=None) -> WeatherRisk:
    """Compute current weather risk score for a municipality.

    Queries weather_observations from the nearest weather station,
    computes severity metrics for the most recent 30-day period, and
    returns a risk assessment.  When no station data is available the
    function falls back to regional seasonal defaults.

    Args:
        municipality_id: admin_level_2.id
        conn: Optional database connection.

    Returns:
        WeatherRisk assessment.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return _fallback_weather_risk(municipality_id)

    try:
        muni_name = _get_municipality_name(municipality_id, conn)
        state, region = _get_municipality_region(municipality_id, conn)

        station_id = _find_nearest_station(municipality_id, conn)
        if station_id is None:
            logger.warning(
                "No weather station found near municipality %d; using regional default",
                municipality_id,
            )
            return _regional_default_risk(municipality_id, muni_name, region)

        # Compute metrics for the most recent complete month
        today = date.today()
        if today.month == 1:
            target_year, target_month = today.year - 1, 12
        else:
            target_year, target_month = today.year, today.month - 1

        metrics = compute_monthly_metrics(station_id, target_year, target_month, conn)

        # If no data for last month, try the month before
        if (
            metrics.total_precipitation_mm == 0
            and metrics.max_wind_speed_ms == 0
            and metrics.temperature_range == 0
        ):
            if target_month == 1:
                target_year -= 1
                target_month = 12
            else:
                target_month -= 1
            metrics = compute_monthly_metrics(
                station_id, target_year, target_month, conn,
            )

        # Still no data?  Fall back to regional defaults.
        if (
            metrics.total_precipitation_mm == 0
            and metrics.max_wind_speed_ms == 0
            and metrics.temperature_range == 0
        ):
            logger.info(
                "No recent weather data for municipality %d; using regional default",
                municipality_id,
            )
            return _regional_default_risk(municipality_id, muni_name, region)

        precip_score = _score_precipitation_risk(metrics)
        wind_score = _score_wind_risk(metrics)
        temp_score = _score_temperature_risk(metrics)

        # Composite: precipitation is the dominant cause of telecom faults
        # in Brazil, followed by wind, then temperature.
        overall = 0.50 * precip_score + 0.30 * wind_score + 0.20 * temp_score

        details = {
            "station_id": station_id,
            "period": f"{target_year}-{target_month:02d}",
            "region": region,
            "metrics": {
                "total_precipitation_mm": metrics.total_precipitation_mm,
                "max_daily_precipitation_mm": metrics.max_daily_precipitation_mm,
                "max_wind_speed_ms": metrics.max_wind_speed_ms,
                "temperature_range_c": metrics.temperature_range,
                "consecutive_rain_days": metrics.consecutive_rain_days,
                "avg_humidity_pct": metrics.avg_humidity_pct,
            },
            "scores": {
                "precipitation": round(precip_score, 1),
                "wind": round(wind_score, 1),
                "temperature": round(temp_score, 1),
            },
        }

        logger.info(
            "Weather risk for %s (id=%d): overall=%.1f  precip=%s wind=%s temp=%s",
            muni_name,
            municipality_id,
            overall,
            get_risk_level(precip_score),
            get_risk_level(wind_score),
            get_risk_level(temp_score),
        )

        return WeatherRisk(
            municipality_id=municipality_id,
            municipality_name=muni_name,
            overall_risk_score=round(overall, 2),
            precipitation_risk=get_risk_level(precip_score),
            wind_risk=get_risk_level(wind_score),
            temperature_risk=get_risk_level(temp_score),
            details=details,
        )
    except Exception as exc:
        logger.error(
            "Error computing weather risk for municipality %d: %s",
            municipality_id, exc,
        )
        return _fallback_weather_risk(municipality_id)
    finally:
        if own_conn:
            conn.close()


def correlate_weather_quality(
    municipality_id: int, months: int = 24, conn=None,
) -> dict:
    """Compute correlation between weather metrics and quality degradation.

    For each month in the look-back window:
    1. Compute weather severity metrics from the nearest station.
    2. Fetch the municipality's average quality indicator value.
    3. Compute quality_delta = quality_this_month - rolling_3month_avg.
    4. Pair weather severity with quality delta.

    Returns:
        Dictionary with:
        - monthly_data: list of {year_month, weather_score, quality_value,
          quality_delta} records
        - correlation: Pearson-r between weather_score and quality_delta
        - seasonal_pattern: which months show strongest correlation
        - data_completeness: fraction of months with both weather + quality data
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return _empty_correlation()

    try:
        station_id = _find_nearest_station(municipality_id, conn)
        if station_id is None:
            logger.warning(
                "No weather station near municipality %d for correlation",
                municipality_id,
            )
            return _empty_correlation()

        # Fetch quality indicator values for this municipality
        quality_by_month = _fetch_quality_series(municipality_id, months, conn)

        today = date.today()
        monthly_data = []

        for offset in range(months):
            # Walk backwards from the current month
            m = today.month - offset - 1
            y = today.year
            while m <= 0:
                m += 12
                y -= 1
            ym_label = f"{y}-{m:02d}"

            metrics = compute_monthly_metrics(station_id, y, m, conn)
            weather_score = (
                0.50 * _score_precipitation_risk(metrics)
                + 0.30 * _score_wind_risk(metrics)
                + 0.20 * _score_temperature_risk(metrics)
            )

            quality_value = quality_by_month.get(ym_label)

            monthly_data.append(
                {
                    "year_month": ym_label,
                    "weather_score": round(weather_score, 2),
                    "quality_value": quality_value,
                    "quality_delta": None,  # filled below
                }
            )

        # Reverse so chronological order
        monthly_data.reverse()

        # Compute rolling 3-month average and quality delta
        for i, entry in enumerate(monthly_data):
            if entry["quality_value"] is None:
                continue
            # Rolling average of previous 3 months (where available)
            lookback = [
                monthly_data[j]["quality_value"]
                for j in range(max(0, i - 3), i)
                if monthly_data[j]["quality_value"] is not None
            ]
            if lookback:
                rolling_avg = sum(lookback) / len(lookback)
                entry["quality_delta"] = round(
                    entry["quality_value"] - rolling_avg, 4,
                )

        # Compute Pearson-r between weather_score and quality_delta
        paired = [
            (e["weather_score"], e["quality_delta"])
            for e in monthly_data
            if e["quality_delta"] is not None and e["weather_score"] > 0
        ]
        correlation = _pearson_r(paired)

        # Identify peak-risk months from the data
        month_risk: dict[int, list[float]] = {}
        for entry in monthly_data:
            m_num = int(entry["year_month"].split("-")[1])
            month_risk.setdefault(m_num, []).append(entry["weather_score"])
        avg_by_month = {
            m: sum(scores) / len(scores) for m, scores in month_risk.items()
        }
        peak_months = sorted(avg_by_month, key=avg_by_month.get, reverse=True)[:3]

        total_entries = len(monthly_data)
        complete_entries = sum(
            1
            for e in monthly_data
            if e["quality_value"] is not None and e["weather_score"] > 0
        )
        data_completeness = (
            complete_entries / total_entries if total_entries > 0 else 0.0
        )

        result = {
            "monthly_data": monthly_data,
            "correlation": round(correlation, 4) if correlation is not None else None,
            "peak_risk_months": peak_months,
            "data_completeness": round(data_completeness, 4),
            "n_paired_observations": len(paired),
        }

        logger.info(
            "Weather-quality correlation for municipality %d: r=%.3f (%d obs, %.0f%% complete)",
            municipality_id,
            correlation if correlation is not None else 0.0,
            len(paired),
            data_completeness * 100,
        )
        return result

    except Exception as exc:
        logger.error(
            "Error computing weather-quality correlation for municipality %d: %s",
            municipality_id, exc,
        )
        return _empty_correlation()
    finally:
        if own_conn:
            conn.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_quality_series(
    municipality_id: int, months: int, conn,
) -> dict[str, float]:
    """Fetch average quality indicator value per year_month for a municipality.

    Returns dict mapping 'YYYY-MM' -> avg_value.

    The quality_indicators table stores individual metric types.  We use the
    average across all metric types as a composite quality signal.  If a
    specific metric_type such as 'ida' is available, we prefer that.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT year_month,
                   AVG(value) AS avg_val
            FROM quality_indicators
            WHERE l2_id = %s
            ORDER BY year_month DESC
            LIMIT %s
            """,
            (municipality_id, months),
        )
        rows = cur.fetchall()

    return {row[0]: float(row[1]) for row in rows if row[1] is not None}


def _pearson_r(pairs: list[tuple[float, float]]) -> Optional[float]:
    """Compute Pearson correlation coefficient from (x, y) pairs.

    Returns None if fewer than 3 pairs or zero variance.
    """
    n = len(pairs)
    if n < 3:
        return None

    sum_x = sum(p[0] for p in pairs)
    sum_y = sum(p[1] for p in pairs)
    sum_x2 = sum(p[0] ** 2 for p in pairs)
    sum_y2 = sum(p[1] ** 2 for p in pairs)
    sum_xy = sum(p[0] * p[1] for p in pairs)

    numerator = n * sum_xy - sum_x * sum_y
    denom_x = n * sum_x2 - sum_x ** 2
    denom_y = n * sum_y2 - sum_y ** 2

    if denom_x <= 0 or denom_y <= 0:
        return None

    return numerator / math.sqrt(denom_x * denom_y)


def _empty_correlation() -> dict:
    """Return an empty correlation result when data is unavailable."""
    return {
        "monthly_data": [],
        "correlation": None,
        "peak_risk_months": [],
        "data_completeness": 0.0,
        "n_paired_observations": 0,
    }


def _fallback_weather_risk(municipality_id: int) -> WeatherRisk:
    """Return a neutral weather risk when no data or DB is available."""
    return WeatherRisk(
        municipality_id=municipality_id,
        municipality_name=f"Municipality {municipality_id}",
        overall_risk_score=25.0,
        precipitation_risk="moderate",
        wind_risk="low",
        temperature_risk="low",
        details={"fallback": True, "reason": "No weather data available"},
    )


def _regional_default_risk(
    municipality_id: int, muni_name: str, region: str,
) -> WeatherRisk:
    """Generate a risk score from regional seasonal defaults.

    When no station data exists, we use the known regional patterns and
    the current month to estimate risk.
    """
    pattern = REGIONAL_RISK_PATTERNS.get(region, REGIONAL_RISK_PATTERNS["southeast"])
    current_month = date.today().month
    is_peak = current_month in pattern["peak_risk_months"]

    base_risk = 55.0 if is_peak else 20.0
    primary = pattern["primary_risk"]

    if primary == "precipitation":
        precip_risk = "high" if is_peak else "low"
        wind_risk = "moderate" if is_peak else "low"
        temp_risk = "low"
    elif primary == "wind":
        precip_risk = "moderate" if is_peak else "low"
        wind_risk = "high" if is_peak else "low"
        temp_risk = "low"
    elif primary == "temperature":
        precip_risk = "low"
        wind_risk = "low"
        temp_risk = "high" if is_peak else "low"
    elif primary == "lightning":
        precip_risk = "high" if is_peak else "moderate"
        wind_risk = "moderate" if is_peak else "low"
        temp_risk = "low"
    else:
        precip_risk = "moderate"
        wind_risk = "low"
        temp_risk = "low"

    return WeatherRisk(
        municipality_id=municipality_id,
        municipality_name=muni_name,
        overall_risk_score=base_risk,
        precipitation_risk=precip_risk,
        wind_risk=wind_risk,
        temperature_risk=temp_risk,
        details={
            "source": "regional_default",
            "region": region,
            "primary_risk": primary,
            "is_peak_month": is_peak,
            "pattern_description": pattern["description"],
        },
    )
