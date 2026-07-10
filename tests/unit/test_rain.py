"""Tests for the ITU-R P.837 rain rate service (bundled data, no network)."""

from __future__ import annotations

import pytest

from python.api.services.rain import rain_rate_p837

itur = pytest.importorskip("itur")


def test_rain_rates_regional_variation():
    manaus = rain_rate_p837(-3.1, -60.0)
    sao_paulo = rain_rate_p837(-23.55, -46.63)
    assert manaus is not None and sao_paulo is not None
    # Amazônia is convective-tropical; SP is subtropical — must differ clearly
    assert manaus > sao_paulo + 20
    assert 60 <= manaus <= 140
    assert 40 <= sao_paulo <= 100


def test_rain_rate_cached_grid():
    # Same 0.1-degree cell -> identical (cached) value
    a = rain_rate_p837(-23.5501, -46.6299)
    b = rain_rate_p837(-23.5540, -46.6330)
    assert a == b
