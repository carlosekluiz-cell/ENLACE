"""Quality benchmarking: compare ISP quality metrics against peers.

For each municipality where an ISP operates:
1. Extract Anatel quality metrics (IDA score / composite quality indicator)
2. Compare against national, state, and peer (same-size ISP) averages
3. Track trend: improving, stable, or degrading over 12 months
4. Flag outliers (> 2 standard deviations below peer average)
"""

import logging
import math
from dataclasses import dataclass
from typing import Optional

import psycopg2

from python.ml.config import DB_CONFIG

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class QualityBenchmark:
    """Quality benchmark result for a provider in a municipality."""

    municipality_id: int
    municipality_name: str
    provider_id: int
    provider_name: str
    current_ida: float
    national_avg: float
    state_avg: float
    peer_avg: float
    percentile: float  # 0-100 (provider's rank among peers)
    trend: str  # "improving", "stable", "degrading"
    trend_pct: float  # % change over 12 months
    is_outlier: bool
    churn_risk: str  # "low", "moderate", "high"


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------


def compute_trend(values: list[float]) -> tuple[str, float]:
    """Compute trend from monthly quality values using linear regression.

    The slope of a simple OLS regression on the time series is used to
    determine direction.  The percentage change is calculated as
    (predicted_last - predicted_first) / predicted_first * 100.

    Args:
        values: Monthly quality values in chronological order.

    Returns:
        (trend_direction, pct_change) where trend_direction is one of
        "improving", "stable", or "degrading".
    """
    n = len(values)
    if n < 2:
        return "stable", 0.0

    # Simple OLS: y = a + b*x  where x = 0..n-1
    sum_x = sum(range(n))
    sum_y = sum(values)
    sum_x2 = sum(i * i for i in range(n))
    sum_xy = sum(i * v for i, v in enumerate(values))

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return "stable", 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # Predicted first and last values
    pred_first = intercept
    pred_last = intercept + slope * (n - 1)

    if pred_first == 0:
        pct_change = 0.0
    else:
        pct_change = (pred_last - pred_first) / abs(pred_first) * 100.0

    # Classify: > 3% improvement, < -3% degradation, otherwise stable
    if pct_change > 3.0:
        direction = "improving"
    elif pct_change < -3.0:
        direction = "degrading"
    else:
        direction = "stable"

    return direction, round(pct_change, 2)


def estimate_churn_risk(quality_delta_pct: float) -> str:
    """Estimate subscriber churn risk from quality degradation.

    Based on historical pattern: > 10% quality drop in 3 months
    correlates with 3-5% subscriber loss in the next quarter.
    """
    if quality_delta_pct < -10:
        return "high"
    if quality_delta_pct < -5:
        return "moderate"
    return "low"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_provider_quality(
    provider_id: int,
    municipality_id: int,
    months: int,
    conn,
) -> list[tuple[str, float]]:
    """Fetch monthly quality values for a provider+municipality.

    Returns list of (year_month, avg_value) in chronological order,
    capped at *months* entries.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT year_month, AVG(value) AS avg_val
            FROM quality_indicators
            WHERE provider_id = %s
              AND l2_id = %s
            GROUP BY year_month
            ORDER BY year_month DESC
            LIMIT %s
            """,
            (provider_id, municipality_id, months),
        )
        rows = cur.fetchall()

    # Reverse to chronological order
    return [(r[0], float(r[1])) for r in reversed(rows)]


def _compute_national_avg(conn) -> float:
    """Compute the national average quality value for the latest month."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT AVG(value)
            FROM quality_indicators
            WHERE year_month = (
                SELECT MAX(year_month) FROM quality_indicators
            )
            """
        )
        row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _compute_state_avg(municipality_id: int, conn) -> float:
    """Compute the state average quality value for the latest month.

    Uses the admin_level_1 relationship to identify peer municipalities
    in the same state.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT AVG(qi.value)
            FROM quality_indicators qi
            JOIN admin_level_2 a2 ON a2.id = qi.l2_id
            WHERE a2.l1_id = (
                SELECT l1_id FROM admin_level_2 WHERE id = %s
            )
              AND qi.year_month = (
                SELECT MAX(year_month) FROM quality_indicators
            )
            """,
            (municipality_id,),
        )
        row = cur.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _compute_peer_stats(
    provider_id: int, conn,
) -> tuple[float, float, list[float]]:
    """Compute peer average, standard deviation, and all peer values.

    Peers are providers with the same classification (e.g., PPP / small /
    medium / large) in the latest month.  If classification is unavailable,
    all providers are treated as peers.

    Returns:
        (peer_avg, peer_stddev, list_of_peer_values)
    """
    with conn.cursor() as cur:
        # Get provider classification
        cur.execute(
            "SELECT classification FROM providers WHERE id = %s",
            (provider_id,),
        )
        row = cur.fetchone()
        classification = row[0] if row and row[0] else None

        if classification:
            cur.execute(
                """
                SELECT qi.provider_id, AVG(qi.value) AS avg_val
                FROM quality_indicators qi
                JOIN providers p ON p.id = qi.provider_id
                WHERE p.classification = %s
                  AND qi.year_month = (
                    SELECT MAX(year_month) FROM quality_indicators
                  )
                GROUP BY qi.provider_id
                """,
                (classification,),
            )
        else:
            cur.execute(
                """
                SELECT qi.provider_id, AVG(qi.value) AS avg_val
                FROM quality_indicators qi
                WHERE qi.year_month = (
                    SELECT MAX(year_month) FROM quality_indicators
                )
                GROUP BY qi.provider_id
                """,
            )
        rows = cur.fetchall()

    values = [float(r[1]) for r in rows if r[1] is not None]
    if not values:
        return 0.0, 0.0, []

    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    stddev = math.sqrt(variance)

    return avg, stddev, values


def _compute_percentile(value: float, all_values: list[float]) -> float:
    """Compute the percentile rank of *value* within *all_values*.

    Returns 0-100 where 100 means the value is >= all peers.
    """
    if not all_values:
        return 50.0
    count_below = sum(1 for v in all_values if v < value)
    return round(count_below / len(all_values) * 100, 2)


def _get_provider_name(provider_id: int, conn) -> str:
    """Return the provider name for a given id."""
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM providers WHERE id = %s", (provider_id,))
        row = cur.fetchone()
    return row[0] if row else f"Provider {provider_id}"


def _get_municipality_name(municipality_id: int, conn) -> str:
    """Return the municipality name for a given id."""
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM admin_level_2 WHERE id = %s", (municipality_id,))
        row = cur.fetchone()
    return row[0] if row else f"Municipality {municipality_id}"


def _get_provider_municipalities(provider_id: int, conn) -> list[int]:
    """Return all municipality ids where a provider has quality data."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT l2_id
            FROM quality_indicators
            WHERE provider_id = %s
              AND l2_id IS NOT NULL
            """,
            (provider_id,),
        )
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def benchmark_quality(
    provider_id: int,
    municipality_id: int = None,
    months: int = 12,
    conn=None,
) -> list[QualityBenchmark]:
    """Benchmark quality metrics for a provider across their municipalities.

    If *municipality_id* is provided, only that municipality is benchmarked.
    Otherwise, all municipalities where the provider reports quality data
    are included.

    Args:
        provider_id: providers.id
        municipality_id: Optional admin_level_2.id to restrict to one municipality.
        months: Number of months of history used for trend calculation.
        conn: Optional database connection.

    Returns:
        List of QualityBenchmark results, sorted by current IDA ascending
        (worst quality first) so the caller can prioritise action.
    """
    own_conn = conn is None
    if own_conn:
        try:
            conn = psycopg2.connect(**DB_CONFIG)
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            return []

    try:
        provider_name = _get_provider_name(provider_id, conn)

        if municipality_id is not None:
            muni_ids = [municipality_id]
        else:
            muni_ids = _get_provider_municipalities(provider_id, conn)

        if not muni_ids:
            logger.info(
                "No quality data found for provider %d", provider_id,
            )
            return []

        national_avg = _compute_national_avg(conn)
        peer_avg, peer_stddev, peer_values = _compute_peer_stats(provider_id, conn)

        results: list[QualityBenchmark] = []

        for m_id in muni_ids:
            muni_name = _get_municipality_name(m_id, conn)
            state_avg = _compute_state_avg(m_id, conn)

            series = _fetch_provider_quality(provider_id, m_id, months, conn)
            if not series:
                logger.debug(
                    "No quality data for provider %d in municipality %d",
                    provider_id, m_id,
                )
                continue

            current_ida = series[-1][1]  # most recent value
            quality_values = [v for _, v in series]
            trend_dir, trend_pct = compute_trend(quality_values)

            # Outlier detection: current value > 2 stddev below peer avg
            if peer_stddev > 0:
                is_outlier = current_ida < (peer_avg - 2 * peer_stddev)
            else:
                is_outlier = False

            percentile = _compute_percentile(current_ida, peer_values)
            churn = estimate_churn_risk(trend_pct)

            results.append(
                QualityBenchmark(
                    municipality_id=m_id,
                    municipality_name=muni_name,
                    provider_id=provider_id,
                    provider_name=provider_name,
                    current_ida=round(current_ida, 4),
                    national_avg=round(national_avg, 4),
                    state_avg=round(state_avg, 4),
                    peer_avg=round(peer_avg, 4),
                    percentile=percentile,
                    trend=trend_dir,
                    trend_pct=trend_pct,
                    is_outlier=is_outlier,
                    churn_risk=churn,
                )
            )

        # Sort worst quality first
        results.sort(key=lambda b: b.current_ida)

        logger.info(
            "Benchmarked %d municipalities for provider %d (%s): "
            "%d outliers, %d degrading",
            len(results),
            provider_id,
            provider_name,
            sum(1 for r in results if r.is_outlier),
            sum(1 for r in results if r.trend == "degrading"),
        )

        return results

    except Exception as exc:
        logger.error(
            "Error benchmarking quality for provider %d: %s",
            provider_id, exc,
        )
        return []
    finally:
        if own_conn:
            conn.close()
