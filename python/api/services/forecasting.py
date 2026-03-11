"""
ENLACE Forecasting Service

Provides subscriber forecasting using numpy polyfit for trend extrapolation.
Supports linear and exponential models with confidence intervals.

Avoids heavy dependencies (statsmodels, prophet) — uses only numpy,
which is already a project dependency.
"""

import logging
import math
from typing import Any, Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def forecast_subscribers(
    db: AsyncSession,
    municipality_id: int,
    months_ahead: int = 12,
    model: str = "auto",
) -> dict[str, Any]:
    """Forecast future subscriber counts using trend extrapolation.

    Fetches historical monthly subscriber totals, fits both linear and
    exponential trend models via numpy polyfit, selects the better fit
    (or uses the one specified), and projects forward.

    Args:
        db: Async SQLAlchemy session.
        municipality_id: admin_level_2.id (l2_id in broadband_subscribers).
        months_ahead: Number of months to forecast (1-60).
        model: Forecasting model — 'linear', 'exponential', or 'auto'
               (picks the better R-squared).

    Returns:
        Dictionary with historical data, forecast points, model info,
        and confidence intervals.
    """
    months_ahead = max(1, min(months_ahead, 60))

    # Fetch historical monthly totals
    sql = text("""
        SELECT
            TRIM(bs.year_month) AS year_month,
            SUM(bs.subscribers) AS total_subscribers,
            SUM(CASE WHEN LOWER(bs.technology) = 'fiber' THEN bs.subscribers ELSE 0 END)
                AS fiber_subscribers
        FROM broadband_subscribers bs
        WHERE bs.l2_id = :municipality_id
        GROUP BY TRIM(bs.year_month)
        ORDER BY TRIM(bs.year_month) ASC
    """)

    result = await db.execute(sql, {"municipality_id": municipality_id})
    rows = result.fetchall()

    if len(rows) < 3:
        return {
            "municipality_id": municipality_id,
            "status": "insufficient_data",
            "message": f"Need at least 3 months of data, found {len(rows)}",
            "data_points": len(rows),
            "forecast": [],
        }

    # Parse historical data
    months = []
    totals = []
    fibers = []
    for row in rows:
        ym = row.year_month.strip() if isinstance(row.year_month, str) else row.year_month
        months.append(ym)
        totals.append(int(row.total_subscribers or 0))
        fibers.append(int(row.fiber_subscribers or 0))

    n = len(totals)
    x = np.arange(n, dtype=np.float64)
    y = np.array(totals, dtype=np.float64)
    y_fiber = np.array(fibers, dtype=np.float64)

    # Fit linear model: y = a*x + b
    linear_coeffs = np.polyfit(x, y, 1)
    linear_pred = np.polyval(linear_coeffs, x)
    linear_r2 = _r_squared(y, linear_pred)

    # Fit exponential model: log(y) = a*x + b  =>  y = exp(b) * exp(a*x)
    # Only works if all y > 0
    exp_r2 = -1.0
    exp_coeffs = None
    if np.all(y > 0):
        log_y = np.log(y)
        exp_coeffs = np.polyfit(x, log_y, 1)
        exp_pred = np.exp(np.polyval(exp_coeffs, x))
        exp_r2 = _r_squared(y, exp_pred)

    # Also fit fiber separately (linear only for simplicity)
    fiber_coeffs = np.polyfit(x, y_fiber, 1) if n >= 3 else np.array([0.0, 0.0])

    # Select model
    if model == "linear":
        chosen_model = "linear"
    elif model == "exponential" and exp_coeffs is not None:
        chosen_model = "exponential"
    elif model == "auto":
        if exp_coeffs is not None and exp_r2 > linear_r2 + 0.02:
            chosen_model = "exponential"
        else:
            chosen_model = "linear"
    else:
        chosen_model = "linear"

    # Compute residuals for confidence intervals
    if chosen_model == "linear":
        fitted = linear_pred
        r2 = linear_r2
    else:
        fitted = np.exp(np.polyval(exp_coeffs, x))
        r2 = exp_r2

    residuals = y - fitted
    residual_std = float(np.std(residuals)) if n > 2 else 0.0

    # Generate forecast points
    forecast_points = []
    last_ym = months[-1]

    for i in range(1, months_ahead + 1):
        future_x = float(n - 1 + i)
        future_ym = _advance_year_month(last_ym, i)

        if chosen_model == "linear":
            predicted = float(np.polyval(linear_coeffs, future_x))
        else:
            predicted = float(np.exp(np.polyval(exp_coeffs, future_x)))

        # Confidence interval widens with forecast horizon
        # Using a simple fan-out: std * sqrt(horizon)
        ci_width = residual_std * math.sqrt(i) * 1.96
        predicted = max(0, predicted)

        # Fiber forecast (linear)
        fiber_predicted = max(0, float(np.polyval(fiber_coeffs, future_x)))

        forecast_points.append({
            "year_month": future_ym,
            "predicted_subscribers": round(predicted),
            "predicted_fiber": round(fiber_predicted),
            "confidence_lower": round(max(0, predicted - ci_width)),
            "confidence_upper": round(predicted + ci_width),
            "confidence_level": 0.95,
        })

    # Build historical series for context
    historical = []
    for i in range(n):
        historical.append({
            "year_month": months[i],
            "actual_subscribers": totals[i],
            "actual_fiber": fibers[i],
            "fitted_value": round(float(fitted[i])),
        })

    # Model diagnostics
    slope_per_month = float(linear_coeffs[0])
    if totals[-1] > 0:
        monthly_growth_rate = slope_per_month / totals[-1] * 100
    else:
        monthly_growth_rate = 0.0

    return {
        "municipality_id": municipality_id,
        "status": "success",
        "model": {
            "type": chosen_model,
            "r_squared": round(r2, 4),
            "residual_std": round(residual_std, 2),
            "data_points": n,
            "slope_per_month": round(slope_per_month, 2),
            "monthly_growth_rate_pct": round(monthly_growth_rate, 2),
        },
        "historical": historical,
        "forecast": forecast_points,
        "summary": {
            "current_subscribers": totals[-1],
            "current_fiber": fibers[-1],
            "forecast_end_subscribers": forecast_points[-1]["predicted_subscribers"] if forecast_points else None,
            "forecast_end_fiber": forecast_points[-1]["predicted_fiber"] if forecast_points else None,
            "total_growth_pct": round(
                ((forecast_points[-1]["predicted_subscribers"] - totals[-1]) / totals[-1]) * 100, 2
            ) if forecast_points and totals[-1] > 0 else None,
            "months_ahead": months_ahead,
        },
    }


def _r_squared(y_actual: np.ndarray, y_predicted: np.ndarray) -> float:
    """Compute R-squared (coefficient of determination)."""
    ss_res = float(np.sum((y_actual - y_predicted) ** 2))
    ss_tot = float(np.sum((y_actual - np.mean(y_actual)) ** 2))
    if ss_tot == 0:
        return 0.0
    return 1.0 - (ss_res / ss_tot)


def _advance_year_month(ym: str, months: int) -> str:
    """Advance a 'YYYY-MM' string by N months.

    Examples:
        _advance_year_month('2025-11', 2) -> '2026-01'
        _advance_year_month('2025-01', 12) -> '2026-01'
    """
    parts = ym.split("-")
    year = int(parts[0])
    month = int(parts[1])

    total_months = year * 12 + (month - 1) + months
    new_year = total_months // 12
    new_month = (total_months % 12) + 1

    return f"{new_year:04d}-{new_month:02d}"
