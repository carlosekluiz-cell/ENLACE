"""
ENLACE Time-Series Analytics Router

Endpoints for subscriber time-series data, growth metrics, forecasting,
and backfill of the subscriber_timeseries table.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from python.api.auth.dependencies import require_auth
from python.api.database import get_db
from python.api.services.timeseries_service import (
    get_subscriber_timeseries,
    get_growth_metrics,
    backfill_timeseries,
)
from python.api.services.forecasting import forecast_subscribers

router = APIRouter(prefix="/api/v1/timeseries", tags=["timeseries"])


@router.get("/subscribers")
async def timeseries_subscribers(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    provider_id: Optional[int] = Query(None, description="Optional provider ID filter"),
    interval: str = Query(
        "month",
        description="Aggregation interval: 'month' or 'quarter'",
        pattern="^(month|quarter)$",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Subscriber time-series data aggregated by month or quarter.

    Returns chronologically ordered data points with total subscribers,
    fiber subscribers, provider count, and technology count for each period.
    """
    data = await get_subscriber_timeseries(
        db=db,
        municipality_id=municipality_id,
        provider_id=provider_id,
        interval=interval,
    )

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No subscriber data found for this municipality",
        )

    return {
        "municipality_id": municipality_id,
        "provider_id": provider_id,
        "interval": interval,
        "data_points": len(data),
        "series": data,
    }


@router.get("/growth")
async def timeseries_growth(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Growth metrics for a municipality: MoM, YoY, CAGR, 3-month, 6-month.

    Computes growth rates from the full broadband_subscribers history.
    Includes both total and fiber-specific growth rates.
    """
    metrics = await get_growth_metrics(db=db, municipality_id=municipality_id)

    if metrics["data_points"] == 0:
        raise HTTPException(
            status_code=404,
            detail="No subscriber data found for this municipality",
        )

    return metrics


@router.get("/forecast")
async def timeseries_forecast(
    municipality_id: int = Query(..., description="Municipality ID (admin_level_2.id)"),
    months_ahead: int = Query(
        12, ge=1, le=60, description="Number of months to forecast (1-60)"
    ),
    model: str = Query(
        "auto",
        description="Forecasting model: 'linear', 'exponential', or 'auto'",
        pattern="^(linear|exponential|auto)$",
    ),
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Subscriber forecast using trend extrapolation.

    Fits linear and/or exponential models to historical data and projects
    forward. Returns historical fitted values, forecast points with 95%
    confidence intervals, and model diagnostics (R-squared, slope, etc.).

    When model='auto', the service selects whichever model has a better
    R-squared fit (with a small bias toward linear for stability).
    """
    result = await forecast_subscribers(
        db=db,
        municipality_id=municipality_id,
        months_ahead=months_ahead,
        model=model,
    )

    if result["status"] == "insufficient_data":
        raise HTTPException(
            status_code=422,
            detail=result["message"],
        )

    return result


@router.post("/backfill/{municipality_id}")
async def timeseries_backfill(
    municipality_id: int,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(require_auth),
):
    """
    Trigger backfill computation for subscriber_timeseries.

    Computes and stores per-provider monthly aggregates with derived
    metrics (MoM growth, YoY growth, churn estimate, ARPU estimate)
    in the subscriber_timeseries table. Existing rows for the given
    municipality are replaced.
    """
    result = await backfill_timeseries(db=db, municipality_id=municipality_id)

    if result["rows_inserted"] == 0:
        raise HTTPException(
            status_code=404,
            detail=result.get("message", "No data to backfill"),
        )

    return result
