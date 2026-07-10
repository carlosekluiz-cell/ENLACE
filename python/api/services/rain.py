"""
ITU-R P.837-7 rainfall rate lookup (R0.01: rain rate exceeded 0.01% of an
average year), replacing the single national default of 145 mm/h with the
actual spatial grid — Manaus ~98 mm/h, São Paulo ~63, Recife ~87.

Uses the `itur` package's bundled P.837 data (no network). Values are
cached on a 0.1-degree grid; the heavy import happens lazily on first use.
"""

from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

DEFAULT_RAIN_MMH = 145.0  # conservative tropical fallback


def rain_rate_p837(lat: float, lon: float) -> float | None:
    """R0.01 rain rate (mm/h) at a coordinate, or None if lookup fails."""
    try:
        return _rain_rate_grid(round(lat * 10), round(lon * 10))
    except Exception as e:
        logger.warning("P.837 rain lookup failed at %.2f,%.2f: %s", lat, lon, e)
        return None


@lru_cache(maxsize=4096)
def _rain_rate_grid(lat_decideg: int, lon_decideg: int) -> float:
    import itur

    value = itur.models.itu837.rainfall_rate(
        lat_decideg / 10.0, lon_decideg / 10.0, 0.01
    )
    return round(float(value.value), 1)
