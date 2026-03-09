"""Integration tests for the ENLACE Satellite Router.

Uses ``httpx.AsyncClient`` with ``ASGITransport`` against the FastAPI
application.  The database session and auth dependencies are overridden
with mocks so no real DB or JWT is needed.

Tests cover:
- GET /{municipality_code}/indices — time series
- GET /{municipality_code}/growth — satellite vs IBGE comparison
- GET /ranking — municipality ranking by growth metric
- GET /{municipality_code}/composite/{year} — composite metadata
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from python.api.main import app
from python.api.database import get_db
from python.api.auth.dependencies import require_auth


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.anyio]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_user() -> dict:
    """Return a fake authenticated user dict."""
    return {
        "user_id": "test",
        "email": "test@test.com",
        "tenant_id": "default",
        "role": "admin",
        "anonymous": False,
    }


def _row_ns(**kwargs) -> SimpleNamespace:
    """Create a SimpleNamespace that mimics a SQLAlchemy Row with attribute access."""
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db():
    """Create a mock AsyncSession whose execute() can be programmed per test."""
    db = AsyncMock()
    return db


@pytest.fixture
def client(mock_db):
    """Async httpx client with DB and auth overridden."""

    async def _override_db():
        yield mock_db

    async def _override_auth():
        return _make_mock_user()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_auth] = _override_auth

    transport = httpx.ASGITransport(app=app)

    # We use a sync context manager that returns an AsyncClient
    # The tests themselves will await the client calls.
    yield transport

    # Clean up overrides
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(require_auth, None)


# ═══════════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/indices
# ═══════════════════════════════════════════════════════════════════════════


class TestGetIndices:
    """Tests for GET /api/v1/satellite/{municipality_code}/indices."""

    async def test_get_indices_returns_time_series(self, mock_db, client):
        """Mock DB returning 3 years of data for municipality 3550308."""
        mock_rows = [
            _row_ns(
                year=y,
                mean_ndvi=0.45 + y * 0.001,
                ndvi_std=0.05,
                mean_ndbi=-0.10,
                built_up_area_km2=100.0 + (y - 2022) * 5.0,
                built_up_pct=5.0 + (y - 2022) * 0.2,
                mean_mndwi=-0.20,
                water_area_km2=10.0,
                mean_bsi=0.05,
                bare_soil_area_km2=15.0,
                built_up_change_km2=5.0 if y > 2022 else None,
                built_up_change_pct=5.0 if y > 2022 else None,
                ndvi_change_pct=-2.0 if y > 2022 else None,
                scenes_used=12,
            )
            for y in [2022, 2023, 2024]
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/3550308/indices")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3

        # Verify structure of each row
        for item in body:
            assert "year" in item
            assert "mean_ndvi" in item
            assert "built_up_area_km2" in item
            assert "built_up_pct" in item
            assert "scenes_used" in item

        # Verify ordering
        years = [item["year"] for item in body]
        assert years == [2022, 2023, 2024]

    async def test_get_indices_404_unknown_municipality(self, mock_db, client):
        """When DB returns empty results, endpoint should return 404."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/0000000/indices")

        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert "0000000" in body["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/growth
# ═══════════════════════════════════════════════════════════════════════════


class TestGetGrowthComparison:
    """Tests for GET /api/v1/satellite/{municipality_code}/growth."""

    async def test_get_growth_comparison(self, mock_db, client):
        """Mock satellite data + municipality info. Verify response shape."""
        # The endpoint makes 3 sequential DB calls:
        # 1) satellite indices
        # 2) IBGE population projections
        # 3) municipality metadata summary

        sat_rows = [
            _row_ns(
                year=2023,
                built_up_area_km2=100.0,
                built_up_pct=5.0,
                built_up_change_pct=None,
                mean_ndvi=0.45,
            ),
            _row_ns(
                year=2024,
                built_up_area_km2=110.0,
                built_up_pct=5.5,
                built_up_change_pct=10.0,
                mean_ndvi=0.43,
            ),
        ]

        ibge_rows = [
            _row_ns(year=2023, population=500000),
            _row_ns(year=2024, population=510000),
        ]

        summary_row = _row_ns(population=500000, area_km2=1521.0)

        # Program execute to return different results for each call
        sat_result = MagicMock()
        sat_result.fetchall.return_value = sat_rows

        ibge_result = MagicMock()
        ibge_result.fetchall.return_value = ibge_rows

        summary_result = MagicMock()
        summary_result.fetchone.return_value = summary_row

        mock_db.execute.side_effect = [sat_result, ibge_result, summary_result]

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/3550308/growth")

        assert resp.status_code == 200
        body = resp.json()

        assert "satellite_growth" in body
        assert "ibge_growth" in body
        assert "correlation_summary" in body

        assert isinstance(body["satellite_growth"], list)
        assert len(body["satellite_growth"]) == 2

        assert isinstance(body["ibge_growth"], list)
        assert len(body["ibge_growth"]) == 2

        summary = body["correlation_summary"]
        assert "avg_annual_built_up_change_pct" in summary
        assert "ibge_population" in summary
        assert "area_km2" in summary


# ═══════════════════════════════════════════════════════════════════════════
# GET /ranking
# ═══════════════════════════════════════════════════════════════════════════


class TestGetRanking:
    """Tests for GET /api/v1/satellite/ranking."""

    async def test_get_ranking_default(self, mock_db, client):
        """Mock ranking query returning 3 municipalities sorted by avg_built_up_change_pct desc."""
        mock_rows = [
            _row_ns(
                municipality_code="1100205",
                municipality_name="Porto Velho",
                state_code="RO",
                population=550000,
                area_km2=34000.0,
                avg_metric=8.5,
                data_points=3,
            ),
            _row_ns(
                municipality_code="5103403",
                municipality_name="Cuiaba",
                state_code="MT",
                population=620000,
                area_km2=3300.0,
                avg_metric=6.2,
                data_points=3,
            ),
            _row_ns(
                municipality_code="1302603",
                municipality_name="Manaus",
                state_code="AM",
                population=2250000,
                area_km2=11400.0,
                avg_metric=4.1,
                data_points=3,
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/ranking")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 3

        # Verify sorted descending by avg_metric
        metrics = [item["avg_metric"] for item in body]
        assert metrics == sorted(metrics, reverse=True)

        # Verify structure
        for item in body:
            assert "municipality_code" in item
            assert "municipality_name" in item
            assert "state_code" in item
            assert "avg_metric" in item
            assert "metric" in item

    async def test_get_ranking_with_state_filter(self, mock_db, client):
        """Verify state filter param is passed to the query."""
        mock_rows = [
            _row_ns(
                municipality_code="3550308",
                municipality_name="Sao Paulo",
                state_code="SP",
                population=12300000,
                area_km2=1521.0,
                avg_metric=3.5,
                data_points=3,
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get(
                "/api/v1/satellite/ranking",
                params={"state": "SP"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["state_code"] == "SP"

        # Verify the DB was called and the state param was passed
        mock_db.execute.assert_called_once()
        call_args = mock_db.execute.call_args
        bound_params = call_args[0][1]  # second positional arg = params dict
        assert bound_params["state"] == "SP"

    async def test_get_ranking_empty(self, mock_db, client):
        """When no data exists, ranking returns empty list (not 404)."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/ranking")

        assert resp.status_code == 200
        assert resp.json() == []


# ═══════════════════════════════════════════════════════════════════════════
# GET /{municipality_code}/composite/{year}
# ═══════════════════════════════════════════════════════════════════════════


class TestGetCompositeMetadata:
    """Tests for GET /api/v1/satellite/{municipality_code}/composite/{year}."""

    async def test_get_composite_metadata(self, mock_db, client):
        """Mock composite query. Verify returns list with expected fields."""
        mock_rows = [
            _row_ns(
                composite_type="true_color",
                filepath="s3://sentinel-composites/rgb/3550308/2024.tif",
                resolution_m=10,
                bbox_north=-23.3,
                bbox_south=-23.8,
                bbox_east=-46.3,
                bbox_west=-46.9,
                file_size_mb=45.2,
                created_at=datetime(2024, 6, 15, 12, 0, 0),
            ),
            _row_ns(
                composite_type="ndvi",
                filepath="s3://sentinel-composites/ndvi/3550308/2024.tif",
                resolution_m=10,
                bbox_north=-23.3,
                bbox_south=-23.8,
                bbox_east=-46.3,
                bbox_west=-46.9,
                file_size_mb=12.8,
                created_at=datetime(2024, 6, 15, 12, 0, 0),
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/3550308/composite/2024")

        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) == 2

        # Verify first composite
        first = body[0]
        assert first["composite_type"] == "true_color"
        assert "filepath" in first
        assert "resolution_m" in first
        assert "tile_url" in first
        assert "3550308" in first["tile_url"]
        assert "2024" in first["tile_url"]

        # Verify bbox is present
        assert first["bbox"] is not None
        assert "north" in first["bbox"]
        assert "south" in first["bbox"]
        assert "east" in first["bbox"]
        assert "west" in first["bbox"]

    async def test_get_composite_404_not_found(self, mock_db, client):
        """When no composites exist for a municipality/year, return 404."""
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/9999999/composite/2020")

        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body

    async def test_get_composite_null_bbox(self, mock_db, client):
        """When bbox coordinates are None, bbox field should be None."""
        mock_rows = [
            _row_ns(
                composite_type="ndbi",
                filepath="s3://sentinel-composites/ndbi/3550308/2024.tif",
                resolution_m=10,
                bbox_north=None,
                bbox_south=None,
                bbox_east=None,
                bbox_west=None,
                file_size_mb=8.5,
                created_at=None,
            ),
        ]

        mock_result = MagicMock()
        mock_result.fetchall.return_value = mock_rows
        mock_db.execute.return_value = mock_result

        async with httpx.AsyncClient(transport=client, base_url="http://testserver") as ac:
            resp = await ac.get("/api/v1/satellite/3550308/composite/2024")

        assert resp.status_code == 200
        body = resp.json()
        assert body[0]["bbox"] is None
        assert body[0]["created_at"] is None
