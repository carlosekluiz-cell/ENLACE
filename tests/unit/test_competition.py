"""Tests for competition / market concentration analysis.

Covers:
- HHI calculation (pure Python, no DB)
- Monopoly, duopoly, fragmented market scenarios
- Edge cases: empty market, single provider, equal shares
"""

from __future__ import annotations

import pytest

from python.ml.opportunity.competition import compute_hhi


class TestComputeHHI:
    """Tests for compute_hhi (Herfindahl-Hirschman Index)."""

    def test_monopoly_returns_10000(self):
        """A single provider has 100% share -> HHI = 10000."""
        result = compute_hhi({1: 10_000})
        assert result == pytest.approx(10_000, rel=1e-3)

    def test_duopoly_equal_shares(self):
        """Two equal providers: each 50% -> HHI = 5000."""
        result = compute_hhi({1: 5_000, 2: 5_000})
        assert result == pytest.approx(5_000, rel=1e-3)

    def test_fragmented_market(self):
        """Many small providers -> low HHI."""
        providers = {i: 1_000 for i in range(10)}  # 10 equal providers
        result = compute_hhi(providers)
        # Each has 10% share -> HHI = 10 * (10^2) = 1000
        assert result == pytest.approx(1_000, rel=1e-3)

    def test_dominant_player_with_fringe(self):
        """One dominant + many small providers."""
        providers = {1: 8_000, 2: 500, 3: 500, 4: 500, 5: 500}
        result = compute_hhi(providers)
        # 80% -> 6400, 5% each -> 4*25 = 100 -> HHI ~ 6500
        assert result == pytest.approx(6_500, rel=1e-2)

    def test_empty_market_returns_zero(self):
        """No providers -> HHI = 0."""
        result = compute_hhi({})
        assert result == pytest.approx(0.0)

    def test_returns_float(self):
        result = compute_hhi({1: 7000, 2: 3000})
        assert isinstance(result, float)

    def test_hhi_range(self):
        """HHI should be between 0 and 10000."""
        result = compute_hhi({1: 6000, 2: 3000, 3: 1000})
        assert 0 <= result <= 10_000

    def test_asymmetric_duopoly(self):
        """70/30 split."""
        result = compute_hhi({1: 7_000, 2: 3_000})
        # 70^2 + 30^2 = 4900 + 900 = 5800
        assert result == pytest.approx(5_800, rel=1e-2)

    def test_three_equal_providers(self):
        """Three equal providers: HHI ~ 3333."""
        result = compute_hhi({1: 3333, 2: 3333, 3: 3334})
        assert result == pytest.approx(3_333, rel=5e-2)

    def test_zero_subscribers_ignored(self):
        """Providers with zero subscribers should not affect HHI."""
        with_zero = compute_hhi({1: 5000, 2: 5000, 3: 0})
        without_zero = compute_hhi({1: 5000, 2: 5000})
        assert with_zero == pytest.approx(without_zero, rel=1e-3)
