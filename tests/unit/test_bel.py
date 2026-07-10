"""Tests for ITU-R P.2109-2 building entry loss (values from the Rec.)."""

from __future__ import annotations

import pytest

from python.api.services.bel import building_entry_loss_db


def test_median_traditional_1ghz():
    # Lh=12.64, mu2=9.1, C=-3 -> 10log10(18.37+8.13+0.5) = 14.3 dB
    assert building_entry_loss_db(1.0) == pytest.approx(14.3, abs=0.1)


def test_median_thermally_efficient_1ghz():
    # Lh=28.19, mu2=27.8 -> ~31.0 dB
    assert building_entry_loss_db(1.0, building_class="thermally_efficient") == pytest.approx(
        31.0, abs=0.2
    )


def test_bel_increases_with_frequency_traditional():
    assert building_entry_loss_db(28.0) > building_entry_loss_db(3.5) > building_entry_loss_db(0.7)


def test_probability_tail_ordering():
    # Higher probability (loss not exceeded) -> larger loss value
    p10 = building_entry_loss_db(3.5, probability=0.1)
    p50 = building_entry_loss_db(3.5, probability=0.5)
    p90 = building_entry_loss_db(3.5, probability=0.9)
    assert p10 < p50 < p90


def test_elevation_adds_loss():
    flat = building_entry_loss_db(3.5, elevation_deg=0)
    steep = building_entry_loss_db(3.5, elevation_deg=45)
    assert steep > flat


def test_input_validation():
    with pytest.raises(ValueError):
        building_entry_loss_db(3.5, probability=0.0)
    with pytest.raises(ValueError):
        building_entry_loss_db(0.01)
    with pytest.raises(ValueError):
        building_entry_loss_db(3.5, building_class="wooden")
