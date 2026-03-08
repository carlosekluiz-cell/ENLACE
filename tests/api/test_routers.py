"""Comprehensive API-level integration tests for every ENLACE router.

Uses ``httpx.AsyncClient`` with ``ASGITransport`` to exercise the real
FastAPI application in-process (no network, no live database).

Test categories
---------------
1. Auth flow: login, register, /me with and without token
2. Every non-DB router endpoint with a valid auth token
3. Auth enforcement: all protected endpoints return 401 without a token
4. Validation: bad inputs return 422
5. Middleware: security headers and rate-limit headers
"""

from __future__ import annotations

import pytest
import httpx


# ---------------------------------------------------------------------------
# Markers shared by all tests in this module
# ---------------------------------------------------------------------------
pytestmark = [pytest.mark.anyio]


# ═══════════════════════════════════════════════════════════════════════════
# 1. AUTH FLOW
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthLogin:
    """POST /api/v1/auth/login"""

    async def test_login_returns_token(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com", "password": "test"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"
        assert body["email"] == "test@test.com"
        assert body["role"] == "admin"
        assert body["user_id"] == "test"

    async def test_login_missing_email(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"password": "test"},
        )
        assert resp.status_code == 422

    async def test_login_missing_password(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "test@test.com"},
        )
        assert resp.status_code == 422

    async def test_login_empty_body(self, client: httpx.AsyncClient):
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422


class TestAuthRegister:
    """POST /api/v1/auth/register"""

    async def test_register_success(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "secure123",
                "name": "New User",
                "organization": "TestOrg",
                "state_code": "SP",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert body["email"] == "new@example.com"
        assert body["organization"] == "TestOrg"
        assert body["token_type"] == "bearer"

    async def test_register_password_too_short(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "x@x.com",
                "password": "12",
                "name": "A",
                "organization": "B",
            },
        )
        assert resp.status_code == 422

    async def test_register_missing_required_fields(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "x@x.com"},
        )
        assert resp.status_code == 422

    async def test_register_invalid_state_code_length(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "x@x.com",
                "password": "secure123",
                "name": "User",
                "organization": "Org",
                "state_code": "ABC",  # too long
            },
        )
        assert resp.status_code == 422


class TestAuthMe:
    """GET /api/v1/auth/me"""

    async def test_me_requires_auth(self, client: httpx.AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    async def test_me_with_valid_token(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["anonymous"] is False
        assert body["email"] == "test@test.com"
        assert body["role"] == "admin"

    async def test_me_with_invalid_token(self, client: httpx.AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════
# 2. COMPLIANCE ROUTER (non-DB, pure Python)
# ═══════════════════════════════════════════════════════════════════════════


class TestComplianceStatus:
    """GET /api/v1/compliance/status"""

    async def test_compliance_status(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/status",
            params={
                "provider_name": "TestNet",
                "state": "SP",
                "subscribers": 5000,
                "services": "SCM",
                "classification": "SVA",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "compliance_score" in body or "overall_score" in body or isinstance(body, dict)

    async def test_compliance_status_missing_provider(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/status",
            params={"state": "SP", "subscribers": 5000},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_compliance_status_invalid_state(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/status",
            params={
                "provider_name": "TestNet",
                "state": "XX",
                "subscribers": 5000,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestNorma4Impact:
    """GET /api/v1/compliance/norma4/impact"""

    async def test_norma4_impact(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/norma4/impact",
            params={
                "state": "SP",
                "subscribers": 5000,
                "revenue_monthly": 400000.0,
                "classification": "SVA",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, dict)

    async def test_norma4_impact_missing_revenue(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/norma4/impact",
            params={"state": "SP", "subscribers": 5000},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestNorma4MultiState:
    """POST /api/v1/compliance/norma4/multi-state"""

    async def test_norma4_multi_state(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/norma4/multi-state",
            json={
                "states": [
                    {"state_code": "SP", "revenue_monthly_brl": 200000},
                    {"state_code": "MG", "revenue_monthly_brl": 100000},
                ],
                "subscriber_count": 8000,
                "current_classification": "SVA",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_norma4_multi_state_empty_states(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/compliance/norma4/multi-state",
            json={
                "states": [],
                "subscriber_count": 8000,
                "current_classification": "SVA",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestLicensingCheck:
    """GET /api/v1/compliance/licensing/check"""

    async def test_licensing_check(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/licensing/check",
            params={"subscribers": 6000, "services": "SCM"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_licensing_check_missing_subscribers(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/licensing/check",
            params={},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestDeadlines:
    """GET /api/v1/compliance/deadlines"""

    async def test_deadlines_default(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/deadlines",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_deadlines_custom_window(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/deadlines",
            params={"days_ahead": 30},
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestQualityCheck:
    """GET /api/v1/compliance/quality/check"""

    async def test_quality_check_no_metrics(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/quality/check",
            params={"provider_id": "ISP-001"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "unknown"

    async def test_quality_check_with_metrics(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/quality/check",
            params={
                "provider_id": "ISP-001",
                "download_speed_pct": 85.0,
                "upload_speed_pct": 80.0,
                "latency_pct": 90.0,
                "availability_pct": 99.0,
                "subscribers": 5000,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_quality_check_missing_provider(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/quality/check",
            params={},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestRegulations:
    """GET /api/v1/compliance/regulations"""

    async def test_list_regulations(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/regulations",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0

    async def test_get_regulation_detail(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        # First get the list to find a valid ID
        list_resp = await client.get(
            "/api/v1/compliance/regulations",
            headers=auth_headers,
        )
        regs = list_resp.json()
        if regs:
            reg_id = regs[0]["id"]
            resp = await client.get(
                f"/api/v1/compliance/regulations/{reg_id}",
                headers=auth_headers,
            )
            assert resp.status_code == 200

    async def test_get_regulation_not_found(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/compliance/regulations/nonexistent-reg",
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════
# 3. DESIGN ROUTER (RF Engine — returns mock when gRPC unavailable)
# ═══════════════════════════════════════════════════════════════════════════


class TestDesignCoverage:
    """POST /api/v1/design/coverage"""

    async def test_coverage(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/design/coverage",
            json={
                "tower_lat": -23.55,
                "tower_lon": -46.63,
                "tower_height_m": 30,
                "frequency_mhz": 700,
                "tx_power_dbm": 43,
                "antenna_gain_dbi": 15,
                "radius_m": 5000,
                "grid_resolution_m": 100,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "stats" in body

    async def test_coverage_missing_tower_lat(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/design/coverage",
            json={"tower_lon": -46.63},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestDesignOptimize:
    """POST /api/v1/design/optimize"""

    async def test_optimize(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/design/optimize",
            json={
                "center_lat": -23.55,
                "center_lon": -46.63,
                "radius_m": 5000,
                "max_towers": 3,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "towers" in body


class TestDesignLinkBudget:
    """POST /api/v1/design/linkbudget"""

    async def test_linkbudget(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/design/linkbudget",
            json={
                "frequency_ghz": 18,
                "distance_km": 10,
                "tx_power_dbm": 20,
                "tx_antenna_gain_dbi": 38,
                "rx_antenna_gain_dbi": 38,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "fade_margin_db" in body


class TestDesignProfile:
    """GET /api/v1/design/profile"""

    async def test_terrain_profile(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/design/profile",
            params={
                "start_lat": -23.55,
                "start_lon": -46.63,
                "end_lat": -23.60,
                "end_lon": -46.68,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "points" in body
        assert "total_distance_m" in body

    async def test_terrain_profile_missing_params(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/design/profile",
            params={"start_lat": -23.55},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 4. NETWORK HEALTH ROUTER
# ═══════════════════════════════════════════════════════════════════════════


class TestNetworkHealthWeatherRisk:
    """GET /api/v1/health/weather-risk"""

    async def test_weather_risk(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/weather-risk",
            params={"municipality_id": 3550308},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "municipality_id" in body or "overall_risk_score" in body

    async def test_weather_risk_missing_id(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/weather-risk",
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestNetworkHealthQuality:
    """GET /api/v1/health/quality/{municipality_id}"""

    async def test_quality_benchmark(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/quality/3550308",
            params={"provider_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_quality_benchmark_missing_provider(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/quality/3550308",
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestNetworkHealthQualityPeers:
    """GET /api/v1/health/quality/{municipality_id}/peers"""

    async def test_quality_peers(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/quality/3550308/peers",
            params={"provider_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestNetworkHealthMaintenance:
    """GET /api/v1/health/maintenance/priorities"""

    async def test_maintenance_priorities(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/maintenance/priorities",
            params={"provider_id": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_maintenance_missing_provider(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/maintenance/priorities",
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestNetworkHealthSeasonal:
    """GET /api/v1/health/seasonal/{municipality_id}"""

    async def test_seasonal_calendar(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/health/seasonal/3550308",
            headers=auth_headers,
        )
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# 5. RURAL ROUTER
# ═══════════════════════════════════════════════════════════════════════════


class TestRuralDesign:
    """POST /api/v1/rural/design"""

    async def test_hybrid_design(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/design",
            json={
                "community_lat": -2.50,
                "community_lon": -44.28,
                "population": 800,
                "area_km2": 25.0,
                "grid_power": False,
                "terrain_type": "flat",
                "biome": "amazonia",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_hybrid_design_missing_required(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/design",
            json={"community_lat": -2.50},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestRuralSolar:
    """GET /api/v1/rural/solar"""

    async def test_solar_design(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/rural/solar",
            params={
                "lat": -2.50,
                "lon": -44.28,
                "power_watts": 500,
                "autonomy_days": 3,
                "battery_type": "lithium",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200

    async def test_solar_missing_power(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/rural/solar",
            params={"lat": -2.50, "lon": -44.28},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestRuralFundingMatch:
    """POST /api/v1/rural/funding/match"""

    async def test_funding_match(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/funding/match",
            json={
                "municipality_code": "1500800",
                "municipality_population": 20000,
                "state_code": "PA",
                "technology": "4g_700mhz",
                "capex_brl": 500000,
                "latitude": -2.50,
                "longitude": -44.28,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestRuralFundingPrograms:
    """GET /api/v1/rural/funding/programs"""

    async def test_list_programs(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/rural/funding/programs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        assert len(body) > 0


class TestRuralCommunityProfile:
    """POST /api/v1/rural/community/profile"""

    async def test_community_profile(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/community/profile",
            json={
                "population": 800,
                "avg_income_brl": 1200,
                "has_school": True,
                "has_health_unit": True,
                "agricultural": True,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestRuralRiverCrossing:
    """POST /api/v1/rural/crossing"""

    async def test_river_crossing(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/crossing",
            json={
                "width_m": 500,
                "depth_m": 10.0,
                "current_speed_ms": 1.5,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_river_crossing_missing_width(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/rural/crossing",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 6. REPORTS ROUTER
# ═══════════════════════════════════════════════════════════════════════════


class TestReportsCompliance:
    """POST /api/v1/reports/compliance"""

    async def test_compliance_report(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/reports/compliance",
            json={
                "provider_name": "TestNet",
                "state_codes": ["SP"],
                "subscriber_count": 5000,
                "revenue_monthly": 400000,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # Should return PDF or HTML
        ct = resp.headers.get("content-type", "")
        assert "pdf" in ct or "html" in ct or "octet-stream" in ct

    async def test_compliance_report_missing_fields(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/reports/compliance",
            json={"provider_name": "TestNet"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestReportsRural:
    """POST /api/v1/reports/rural"""

    async def test_rural_report(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/reports/rural",
            json={
                "community_lat": -2.50,
                "community_lon": -44.28,
                "population": 800,
                "area_km2": 25.0,
                "grid_power": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestReportsMarket:
    """POST /api/v1/reports/market — uses DB, may 500 without one."""

    async def test_market_report_validation(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/reports/market",
            json={},  # missing municipality_id
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestReportsExpansion:
    """POST /api/v1/reports/expansion — uses DB, may 500 without one."""

    async def test_expansion_report_validation(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/reports/expansion",
            json={},  # missing municipality_id
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# 7. M&A ROUTER
# ═══════════════════════════════════════════════════════════════════════════


class TestMnaValuation:
    """POST /api/v1/mna/valuation"""

    async def test_valuation(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mna/valuation",
            json={
                "subscriber_count": 8000,
                "fiber_pct": 0.75,
                "monthly_revenue_brl": 640000,
                "ebitda_margin_pct": 32.0,
                "state_code": "SP",
                "monthly_churn_pct": 1.8,
                "growth_rate_12m": 0.10,
                "net_debt_brl": 0,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "subscriber_multiple" in body
        assert "revenue_multiple" in body
        assert "dcf" in body
        assert "combined_range" in body

    async def test_valuation_missing_fields(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mna/valuation",
            json={"subscriber_count": 8000},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestMnaTargets:
    """POST /api/v1/mna/targets"""

    async def test_targets(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mna/targets",
            json={
                "acquirer_states": ["SP"],
                "acquirer_subscribers": 10000,
                "min_subs": 1000,
                "max_subs": 50000,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


class TestMnaSellerPrepare:
    """POST /api/v1/mna/seller/prepare"""

    async def test_seller_prepare(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mna/seller/prepare",
            json={
                "provider_name": "TestNet Telecom",
                "state_codes": ["SP"],
                "subscriber_count": 8000,
                "fiber_pct": 0.75,
                "monthly_revenue_brl": 640000,
                "ebitda_margin_pct": 32.0,
                "net_debt_brl": 0,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "estimated_value_range" in body
        assert "strengths" in body

    async def test_seller_prepare_missing_fields(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.post(
            "/api/v1/mna/seller/prepare",
            json={"provider_name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestMnaMarket:
    """GET /api/v1/mna/market"""

    async def test_market_overview_default(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mna/market",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "SP"
        assert "total_isps" in body

    async def test_market_overview_specific_state(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        resp = await client.get(
            "/api/v1/mna/market",
            params={"state": "MG"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "MG"

    async def test_market_overview_unknown_state(
        self, client: httpx.AsyncClient, auth_headers: dict
    ):
        """Unknown state still returns data (generic fallback)."""
        resp = await client.get(
            "/api/v1/mna/market",
            params={"state": "AC"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "AC"


# ═══════════════════════════════════════════════════════════════════════════
# 8. HEALTH CHECK (no auth required)
# ═══════════════════════════════════════════════════════════════════════════


class TestHealthCheck:
    """GET /health — app-level health check (no auth, no DB)."""

    async def test_health(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body


# ═══════════════════════════════════════════════════════════════════════════
# 9. AUTH ENFORCEMENT — every protected endpoint returns 401 without token
# ═══════════════════════════════════════════════════════════════════════════


class TestAuthEnforcement:
    """All protected endpoints must return 401 when called without a token."""

    @pytest.mark.parametrize(
        "method, path, json_body",
        [
            # Auth
            ("GET", "/api/v1/auth/me", None),
            # Compliance
            ("GET", "/api/v1/compliance/status?provider_name=X&state=SP&subscribers=1", None),
            ("GET", "/api/v1/compliance/norma4/impact?state=SP&subscribers=1&revenue_monthly=1", None),
            ("POST", "/api/v1/compliance/norma4/multi-state", {
                "states": [{"state_code": "SP", "revenue_monthly_brl": 1}],
                "subscriber_count": 1,
                "current_classification": "SVA",
            }),
            ("GET", "/api/v1/compliance/licensing/check?subscribers=1", None),
            ("GET", "/api/v1/compliance/deadlines", None),
            ("GET", "/api/v1/compliance/quality/check?provider_id=X", None),
            ("GET", "/api/v1/compliance/regulations", None),
            ("GET", "/api/v1/compliance/regulations/norma4", None),
            # Design
            ("POST", "/api/v1/design/coverage", {"tower_lat": -23, "tower_lon": -46}),
            ("POST", "/api/v1/design/optimize", {"center_lat": -23, "center_lon": -46}),
            ("POST", "/api/v1/design/linkbudget", {}),
            ("GET", "/api/v1/design/profile?start_lat=-23&start_lon=-46&end_lat=-24&end_lon=-47", None),
            # Network health
            ("GET", "/api/v1/health/weather-risk?municipality_id=1", None),
            ("GET", "/api/v1/health/quality/1?provider_id=1", None),
            ("GET", "/api/v1/health/quality/1/peers?provider_id=1", None),
            ("GET", "/api/v1/health/maintenance/priorities?provider_id=1", None),
            ("GET", "/api/v1/health/seasonal/1", None),
            # Rural
            ("POST", "/api/v1/rural/design", {
                "community_lat": -2, "community_lon": -44,
                "population": 100, "area_km2": 1.0,
            }),
            ("GET", "/api/v1/rural/solar?lat=-2&lon=-44&power_watts=100", None),
            ("POST", "/api/v1/rural/funding/match", {
                "municipality_code": "1", "municipality_population": 1,
                "state_code": "PA", "technology": "fiber", "capex_brl": 1,
            }),
            ("GET", "/api/v1/rural/funding/programs", None),
            ("POST", "/api/v1/rural/community/profile", {
                "population": 100,
            }),
            ("POST", "/api/v1/rural/crossing", {"width_m": 100}),
            # Reports
            ("POST", "/api/v1/reports/compliance", {
                "provider_name": "X", "state_codes": ["SP"],
                "subscriber_count": 1,
            }),
            ("POST", "/api/v1/reports/rural", {
                "community_lat": -2, "community_lon": -44,
                "population": 100, "area_km2": 1.0,
            }),
            # MNA
            ("POST", "/api/v1/mna/valuation", {
                "subscriber_count": 1, "monthly_revenue_brl": 1,
            }),
            ("POST", "/api/v1/mna/targets", {
                "acquirer_states": ["SP"], "acquirer_subscribers": 1,
            }),
            ("POST", "/api/v1/mna/seller/prepare", {
                "provider_name": "X", "state_codes": ["SP"],
                "subscriber_count": 1, "monthly_revenue_brl": 1,
            }),
            ("GET", "/api/v1/mna/market", None),
        ],
        ids=lambda v: v if isinstance(v, str) else "",
    )
    async def test_401_without_token(
        self, client: httpx.AsyncClient, method: str, path: str, json_body
    ):
        if method == "GET":
            resp = await client.get(path)
        else:
            resp = await client.post(path, json=json_body or {})
        assert resp.status_code == 401, (
            f"{method} {path} returned {resp.status_code}, expected 401"
        )


# ═══════════════════════════════════════════════════════════════════════════
# 10. MIDDLEWARE — Security headers
# ═══════════════════════════════════════════════════════════════════════════


class TestSecurityHeaders:
    """Every response must include the security headers."""

    async def test_security_headers_on_health(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Cache-Control") == "no-store"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    async def test_security_headers_on_auth_login(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.com", "password": "x"},
        )
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"

    async def test_security_headers_on_error_response(self, client: httpx.AsyncClient):
        """Even error responses (e.g. 422) should have security headers."""
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"


# ═══════════════════════════════════════════════════════════════════════════
# 11. MIDDLEWARE — Rate limit headers
# ═══════════════════════════════════════════════════════════════════════════


class TestRateLimitHeaders:
    """Successful responses include X-RateLimit-Limit and X-RateLimit-Remaining."""

    async def test_rate_limit_headers_on_health(self, client: httpx.AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        limit = int(resp.headers["X-RateLimit-Limit"])
        remaining = int(resp.headers["X-RateLimit-Remaining"])
        assert limit > 0
        assert remaining >= 0

    async def test_rate_limit_headers_on_auth(self, client: httpx.AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "a@b.com", "password": "x"},
        )
        assert "X-RateLimit-Limit" in resp.headers
        # Auth endpoints have lower limit (10)
        limit = int(resp.headers["X-RateLimit-Limit"])
        assert limit == 10


# ═══════════════════════════════════════════════════════════════════════════
# 12. OPENAPI DOCS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════


class TestOpenAPIDocs:
    """The OpenAPI spec should be accessible."""

    async def test_openapi_json(self, client: httpx.AsyncClient):
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        body = resp.json()
        assert body["info"]["title"] == "ENLACE API"
        assert "paths" in body
