"""
ENLACE Network Health Router

Fault intelligence endpoints: weather risk, quality benchmarking,
maintenance priorities, and seasonal risk calendar. These are distinct
from the system health endpoints in health.py which check DB/Redis status.
"""

import asyncio
import dataclasses
import functools
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from python.ml.health.weather_correlation import (
    WeatherRisk,
    compute_weather_risk,
)
from python.ml.health.quality_benchmark import (
    QualityBenchmark,
    benchmark_quality,
)
from python.ml.health.maintenance_scorer import (
    MaintenancePriority,
    compute_maintenance_priorities,
)
from python.ml.health.seasonal_patterns import (
    SeasonalCalendar,
    generate_seasonal_calendar,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/health", tags=["network-health"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_value(value):
    """Recursively serialize a value for JSON response."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return _serialize_dataclass(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: _serialize_value(v) for k, v in value.items()}
    if hasattr(value, "value") and not isinstance(value, (int, float, str, bool)):
        # Handle enums
        return value.value
    return value


def _serialize_dataclass(obj):
    """Convert a dataclass to a dict, handling nested dataclasses and dates."""
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        result = {}
        for f in dataclasses.fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = _serialize_value(value)
        return result
    raise TypeError(f"Expected a dataclass instance, got {type(obj)}")


async def _run_sync(func, *args, **kwargs):
    """Run a synchronous function in a thread executor."""
    loop = asyncio.get_event_loop()
    bound = functools.partial(func, *args, **kwargs)
    return await loop.run_in_executor(None, bound)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/weather-risk")
async def weather_risk(
    municipality_id: int = Query(..., ge=1, description="Municipality ID (admin_level_2.id)"),
):
    """
    Current and 7-day weather risk forecast for a municipality.

    Returns overall risk score (0-100), precipitation, wind, and temperature
    risk levels, and detailed metrics from the nearest weather station.
    """
    try:
        result: WeatherRisk = await _run_sync(compute_weather_risk, municipality_id)
        return _serialize_dataclass(result)
    except Exception as exc:
        logger.error("Error computing weather risk for municipality %d: %s", municipality_id, exc)
        # Return a graceful default instead of 500
        return {
            "municipality_id": municipality_id,
            "municipality_name": f"Municipality {municipality_id}",
            "overall_risk_score": 25.0,
            "precipitation_risk": "moderate",
            "wind_risk": "low",
            "temperature_risk": "low",
            "details": {"fallback": True, "reason": str(exc)},
        }


@router.get("/quality/{municipality_id}")
async def quality_benchmark(
    municipality_id: int,
    provider_id: int = Query(..., ge=1, description="Provider ID"),
):
    """
    Quality metrics with benchmarks and trends for a provider in a municipality.

    Returns the provider's current IDA score compared to national, state,
    and peer averages, with trend direction and churn risk assessment.
    """
    try:
        results: list[QualityBenchmark] = await _run_sync(
            benchmark_quality,
            provider_id=provider_id,
            municipality_id=municipality_id,
        )
        if not results:
            return {
                "municipality_id": municipality_id,
                "provider_id": provider_id,
                "current_ida": 0.0,
                "national_avg": 0.0,
                "state_avg": 0.0,
                "peer_avg": 0.0,
                "percentile": 50.0,
                "trend": "stable",
                "trend_pct": 0.0,
                "is_outlier": False,
                "churn_risk": "low",
                "message": "No quality data available for this provider/municipality combination.",
            }
        return _serialize_dataclass(results[0])
    except Exception as exc:
        logger.error(
            "Error benchmarking quality for provider %d in municipality %d: %s",
            provider_id, municipality_id, exc,
        )
        return {
            "municipality_id": municipality_id,
            "provider_id": provider_id,
            "current_ida": 0.0,
            "national_avg": 0.0,
            "state_avg": 0.0,
            "peer_avg": 0.0,
            "percentile": 50.0,
            "trend": "stable",
            "trend_pct": 0.0,
            "is_outlier": False,
            "churn_risk": "low",
            "message": f"Error: {exc}",
        }


@router.get("/quality/{municipality_id}/peers")
async def quality_peers(
    municipality_id: int,
    provider_id: int = Query(..., ge=1, description="Provider ID for peer comparison"),
):
    """
    Peer comparison for quality metrics within a municipality.

    Returns quality benchmarks for all providers in the specified municipality.
    """
    try:
        results: list[QualityBenchmark] = await _run_sync(
            benchmark_quality,
            provider_id=provider_id,
            municipality_id=municipality_id,
        )
        return [_serialize_dataclass(r) for r in results]
    except Exception as exc:
        logger.error(
            "Error fetching peer quality for municipality %d: %s",
            municipality_id, exc,
        )
        return []


@router.get("/maintenance/priorities")
async def maintenance_priorities(
    provider_id: int = Query(..., ge=1, description="Provider ID"),
):
    """
    Ranked list of municipalities by maintenance priority.

    Returns municipalities sorted by priority score (highest first), with
    sub-scores for weather risk, infrastructure age, quality trend, revenue
    at risk, and competitive pressure.
    """
    try:
        results: list[MaintenancePriority] = await _run_sync(
            compute_maintenance_priorities,
            provider_id=provider_id,
        )
        return [_serialize_dataclass(r) for r in results]
    except Exception as exc:
        logger.error(
            "Error computing maintenance priorities for provider %d: %s",
            provider_id, exc,
        )
        return []


@router.get("/seasonal/{municipality_id}")
async def seasonal_calendar(
    municipality_id: int,
):
    """
    Historical seasonal risk calendar for a municipality.

    Returns a 12-month risk calendar showing when network faults are most
    likely, based on regional climate patterns and local weather data.
    """
    try:
        result: SeasonalCalendar = await _run_sync(
            generate_seasonal_calendar, municipality_id,
        )
        return _serialize_dataclass(result)
    except Exception as exc:
        logger.error(
            "Error generating seasonal calendar for municipality %d: %s",
            municipality_id, exc,
        )
        # Return default calendar
        from python.ml.health.seasonal_patterns import _default_calendar
        default = _default_calendar(municipality_id)
        return _serialize_dataclass(default)
