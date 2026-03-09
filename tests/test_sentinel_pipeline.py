"""Unit tests for the Sentinel Growth Pipeline helper functions and transform logic.

Tests cover:
- _safe_float: edge cases for None, empty strings, "None", valid floats
- _safe_int: valid ints, float-strings, None
- Year-over-year change computation via SentinelGrowthPipeline._compute_yoy_changes

Note: Several dependencies (google.cloud.storage, ee, boto3) are not available
in the test environment, so we mock them at the sys.modules level before importing.
"""

import sys
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock unavailable third-party modules before importing sentinel_growth
# ---------------------------------------------------------------------------

_MODULES_TO_MOCK = [
    "google.cloud.storage",
    "ee",
    "boto3",
    "psycopg2",
    "psycopg2.extras",
]

_original_modules = {}
for mod_name in _MODULES_TO_MOCK:
    if mod_name not in sys.modules:
        _original_modules[mod_name] = None
        sys.modules[mod_name] = MagicMock()
    else:
        _original_modules[mod_name] = sys.modules[mod_name]

# Also mock the GEE sentinel_compute module which depends on 'ee'
if "python.pipeline.gee.sentinel_compute" not in sys.modules:
    mock_sentinel_compute = MagicMock()
    mock_sentinel_compute.GEE_EXPORT_BUCKET = "enlace-sentinel"
    mock_sentinel_compute.MunicipalitySpec = MagicMock
    mock_sentinel_compute.TaskPair = MagicMock
    mock_sentinel_compute.batch_compute = MagicMock()
    mock_sentinel_compute.check_task_status = MagicMock()
    mock_sentinel_compute.initialize_gee = MagicMock()
    sys.modules["python.pipeline.gee.sentinel_compute"] = mock_sentinel_compute

# Now safe to import
from python.pipeline.flows.sentinel_growth import _safe_float, _safe_int


# ═══════════════════════════════════════════════════════════════════════════
# _safe_float tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSafeFloat:
    """Test the _safe_float helper used when parsing GEE CSV exports."""

    def test_safe_float_valid(self):
        assert _safe_float("1.5") == 1.5

    def test_safe_float_none(self):
        assert _safe_float(None) is None

    def test_safe_float_empty_string(self):
        assert _safe_float("") is None

    def test_safe_float_none_string(self):
        assert _safe_float("None") is None

    def test_safe_float_null_string(self):
        assert _safe_float("null") is None

    def test_safe_float_whitespace(self):
        assert _safe_float("   ") is None

    def test_safe_float_integer_string(self):
        assert _safe_float("42") == 42.0

    def test_safe_float_negative(self):
        assert _safe_float("-0.35") == -0.35

    def test_safe_float_already_float(self):
        assert _safe_float(3.14) == 3.14

    def test_safe_float_garbage(self):
        assert _safe_float("not_a_number") is None

    def test_safe_float_zero(self):
        assert _safe_float("0") == 0.0

    def test_safe_float_zero_decimal(self):
        assert _safe_float("0.0") == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# _safe_int tests
# ═══════════════════════════════════════════════════════════════════════════


class TestSafeInt:
    """Test the _safe_int helper used when parsing pixel counts from GEE CSV."""

    def test_safe_int_valid(self):
        assert _safe_int("42") == 42

    def test_safe_int_float_string(self):
        """Float strings are truncated to int (int(42.7) == 42)."""
        assert _safe_int("42.7") == 42

    def test_safe_int_none(self):
        assert _safe_int(None) is None

    def test_safe_int_empty_string(self):
        assert _safe_int("") is None

    def test_safe_int_none_string(self):
        assert _safe_int("None") is None

    def test_safe_int_negative(self):
        assert _safe_int("-5") == -5

    def test_safe_int_zero(self):
        assert _safe_int("0") == 0

    def test_safe_int_garbage(self):
        assert _safe_int("abc") is None


# ═══════════════════════════════════════════════════════════════════════════
# Year-over-year change computation
# ═══════════════════════════════════════════════════════════════════════════


class TestYearOverYearChange:
    """Test _compute_yoy_changes via the SentinelGrowthPipeline class.

    We instantiate the pipeline but only exercise the pure-logic
    _compute_yoy_changes method, which does not touch the database.
    """

    @pytest.fixture
    def pipeline(self):
        """Create pipeline instance with external dependencies bypassed."""
        from unittest.mock import patch

        with patch("python.pipeline.flows.sentinel_growth.MinIOConfig"):
            with patch(
                "python.pipeline.flows.sentinel_growth.BasePipeline.__init__",
                return_value=None,
            ):
                from python.pipeline.flows.sentinel_growth import (
                    SentinelGrowthPipeline,
                )

                p = SentinelGrowthPipeline.__new__(SentinelGrowthPipeline)
                p.name = "sentinel_growth"
                return p

    def test_year_over_year_change(self, pipeline):
        """Two rows for the same municipality (2023, 2024) with known values.

        built_up_area_km2: 100.0 -> 110.0
        Expected change_km2 = 10.0
        Expected change_pct = (110 - 100) / 100 * 100 = 10.0%

        ndvi_mean: 0.50 -> 0.45
        Expected ndvi_change_pct = (0.45 - 0.50) / |0.50| * 100 = -10.0%
        """
        rows = [
            {
                "l2_id": 1,
                "year": 2023,
                "municipality_code": "3550308",
                "ndvi_mean": 0.50,
                "ndbi_mean": -0.10,
                "mndwi_mean": -0.20,
                "bsi_mean": 0.05,
                "built_up_area_km2": 100.0,
                "built_up_pct": 5.0,
                "pixel_count": 10000,
                "cloud_free_pct": None,
            },
            {
                "l2_id": 1,
                "year": 2024,
                "municipality_code": "3550308",
                "ndvi_mean": 0.45,
                "ndbi_mean": -0.08,
                "mndwi_mean": -0.18,
                "bsi_mean": 0.06,
                "built_up_area_km2": 110.0,
                "built_up_pct": 5.5,
                "pixel_count": 10000,
                "cloud_free_pct": None,
            },
        ]

        result = pipeline._compute_yoy_changes(rows)

        assert len(result) == 2

        # First year has no previous data
        first = result[0]
        assert first["year"] == 2023
        assert first["built_up_change_km2"] is None
        assert first["built_up_change_pct"] is None
        assert first["ndvi_change_pct"] is None

        # Second year has computed changes
        second = result[1]
        assert second["year"] == 2024
        assert second["built_up_change_km2"] == pytest.approx(10.0)
        assert second["built_up_change_pct"] == pytest.approx(10.0)
        assert second["ndvi_change_pct"] == pytest.approx(-10.0)

    def test_yoy_with_none_areas(self, pipeline):
        """When built_up_area_km2 is None, change fields should be None."""
        rows = [
            {
                "l2_id": 2,
                "year": 2022,
                "municipality_code": "1234567",
                "ndvi_mean": 0.60,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": None,
                "built_up_pct": None,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
            {
                "l2_id": 2,
                "year": 2023,
                "municipality_code": "1234567",
                "ndvi_mean": 0.55,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 50.0,
                "built_up_pct": 3.0,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
        ]

        result = pipeline._compute_yoy_changes(rows)
        second = result[1]
        assert second["built_up_change_km2"] is None
        assert second["built_up_change_pct"] is None

    def test_yoy_zero_previous_area(self, pipeline):
        """When previous built_up_area_km2 is 0, change_pct should be None (div-by-zero guard)."""
        rows = [
            {
                "l2_id": 3,
                "year": 2020,
                "municipality_code": "9999999",
                "ndvi_mean": 0.70,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 0.0,
                "built_up_pct": 0.0,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
            {
                "l2_id": 3,
                "year": 2021,
                "municipality_code": "9999999",
                "ndvi_mean": 0.65,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 5.0,
                "built_up_pct": 0.5,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
        ]

        result = pipeline._compute_yoy_changes(rows)
        second = result[1]
        assert second["built_up_change_km2"] == pytest.approx(5.0)
        assert second["built_up_change_pct"] is None  # div by zero guarded

    def test_yoy_multiple_municipalities(self, pipeline):
        """Changes are computed independently per municipality (grouped by l2_id)."""
        rows = [
            # Municipality A
            {
                "l2_id": 10,
                "year": 2023,
                "municipality_code": "AAA",
                "ndvi_mean": 0.50,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 200.0,
                "built_up_pct": None,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
            {
                "l2_id": 10,
                "year": 2024,
                "municipality_code": "AAA",
                "ndvi_mean": 0.48,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 210.0,
                "built_up_pct": None,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
            # Municipality B
            {
                "l2_id": 20,
                "year": 2023,
                "municipality_code": "BBB",
                "ndvi_mean": 0.60,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 50.0,
                "built_up_pct": None,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
            {
                "l2_id": 20,
                "year": 2024,
                "municipality_code": "BBB",
                "ndvi_mean": 0.58,
                "ndbi_mean": None,
                "mndwi_mean": None,
                "bsi_mean": None,
                "built_up_area_km2": 55.0,
                "built_up_pct": None,
                "pixel_count": None,
                "cloud_free_pct": None,
            },
        ]

        result = pipeline._compute_yoy_changes(rows)

        assert len(result) == 4

        # Find the 2024 row for municipality A (l2_id=10)
        muni_a_2024 = [
            r for r in result if r["l2_id"] == 10 and r["year"] == 2024
        ][0]
        assert muni_a_2024["built_up_change_km2"] == pytest.approx(10.0)
        assert muni_a_2024["built_up_change_pct"] == pytest.approx(5.0)

        # Find the 2024 row for municipality B (l2_id=20)
        muni_b_2024 = [
            r for r in result if r["l2_id"] == 20 and r["year"] == 2024
        ][0]
        assert muni_b_2024["built_up_change_km2"] == pytest.approx(5.0)
        assert muni_b_2024["built_up_change_pct"] == pytest.approx(10.0)
