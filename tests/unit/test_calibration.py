"""Tests for the calibration residual aggregation (pure math, no DB)."""

from __future__ import annotations

import math

from python.api.services.calibration import summarize_residuals


def _rows(residuals, **common):
    return [{"residual_db": r, **common} for r in residuals]


def test_summarize_empty():
    s = summarize_residuals([])
    assert s["overall"] == {"n": 0}


def test_summarize_overall_stats():
    # Residuals with known stats: mean 1.0, values symmetric around it
    rows = _rows([-1.0, 1.0, 3.0], environment="urban", clutter="urban", model="hata")
    s = summarize_residuals(rows)
    o = s["overall"]
    assert o["n"] == 3
    assert o["bias_db"] == 1.0
    # std = sqrt(((−2)² + 0 + 2²)/3) = sqrt(8/3)
    assert abs(o["std_db"] - math.sqrt(8 / 3)) < 0.01
    # rmse = sqrt((1+1+9)/3)
    assert abs(o["rmse_db"] - math.sqrt(11 / 3)) < 0.01


def test_summarize_groups_by_dimension():
    rows = _rows([2.0, 2.0], environment="urban", clutter="urban", model="hata") + _rows(
        [-4.0], environment="rural", clutter="forest", model="tr38901"
    )
    s = summarize_residuals(rows)
    assert s["by_environment"]["urban"]["n"] == 2
    assert s["by_environment"]["urban"]["bias_db"] == 2.0
    assert s["by_environment"]["rural"]["bias_db"] == -4.0
    assert s["by_clutter"]["forest"]["n"] == 1
    assert s["by_model"]["hata"]["n"] == 2


def test_summarize_unknown_dimension_bucket():
    rows = [{"residual_db": 5.0}]  # no env/clutter/model keys
    s = summarize_residuals(rows)
    assert s["by_environment"]["unknown"]["n"] == 1


def test_bias_zero_perfect_model():
    rows = _rows([0.0, 0.0, 0.0], environment="open", clutter="open", model="fspl")
    s = summarize_residuals(rows)
    assert s["overall"]["bias_db"] == 0.0
    assert s["overall"]["rmse_db"] == 0.0


# ---------------------------------------------------------------------------
# Correction table derivation
# ---------------------------------------------------------------------------


def test_corrections_require_valid_benchmark():
    from python.api.services.calibration import corrections_from_summary

    summary = {
        "benchmark_valid": False,
        "by_environment": {"urban": {"n": 500, "bias_db": 3.0}},
    }
    assert corrections_from_summary(summary) == {}


def test_corrections_require_group_sample_size():
    from python.api.services.calibration import corrections_from_summary

    summary = {
        "benchmark_valid": True,
        "by_environment": {
            "urban": {"n": 120, "bias_db": 2.5, "std_db": 5.0, "rmse_db": 5.6},
            "rural": {"n": 12, "bias_db": -8.0},  # too thin -> excluded
            "unknown": {"n": 400, "bias_db": 1.0},  # never corrected
        },
    }
    assert corrections_from_summary(summary) == {"urban": 2.5}


# ---------------------------------------------------------------------------
# E-field -> dBm conversion (Anatel EMF loader physics)
# ---------------------------------------------------------------------------


def test_efield_to_dbm_known_value():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from calibration_ingest import efield_to_dbm

    # E=1 V/m at 900 MHz: S = 1/377 W/m2; Aeff = (0.333)^2/(4pi) = 8.83e-3 m2
    # Pr = 2.34e-5 W = -16.3 dBm
    dbm = efield_to_dbm(1.0, 900.0)
    assert abs(dbm - (-16.3)) < 0.3

    # 6 dB less field (0.5 V/m) -> 6 dB less power
    assert abs((efield_to_dbm(0.5, 900.0) - dbm) - (-6.02)) < 0.05
    # Double frequency -> quarter aperture -> -6.02 dB
    assert abs((efield_to_dbm(1.0, 1800.0) - dbm) - (-6.02)) < 0.05


def test_efield_to_dbm_rejects_invalid():
    import sys
    from pathlib import Path

    import pytest

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from calibration_ingest import efield_to_dbm

    with pytest.raises(ValueError):
        efield_to_dbm(0.0, 900.0)
    with pytest.raises(ValueError):
        efield_to_dbm(1.0, -1.0)
