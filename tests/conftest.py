"""Shared fixtures for the ENLACE test suite.

These fixtures provide reusable sample data that mirrors real-world
Brazilian ISP / municipality parameters so tests stay DRY and readable.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Municipality fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_municipality() -> dict:
    """Representative municipality in Sao Paulo state."""
    return {
        "municipality_code": "3550308",
        "municipality_name": "Sao Paulo",
        "state_code": "SP",
        "population": 50_000,
        "households": 16_000,
        "avg_income_brl": 3_200.0,
        "urbanization_rate": 0.85,
        "current_penetration": 0.45,
        "household_growth_rate": 0.01,
        "latitude": -23.55,
        "longitude": -46.63,
    }


# ---------------------------------------------------------------------------
# ISP fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_isp() -> dict:
    """Mid-size fiber-heavy ISP operating in Sao Paulo."""
    return {
        "provider_name": "TestNet Telecom",
        "provider_id": 9999,
        "state_codes": ["SP"],
        "subscriber_count": 8_000,
        "fiber_pct": 0.75,
        "monthly_revenue_brl": 640_000.0,
        "ebitda_margin_pct": 32.0,
        "monthly_churn_pct": 1.8,
        "growth_rate_12m": 0.10,
        "net_debt_brl": 0.0,
        "arpu_brl": 80.0,
    }


# ---------------------------------------------------------------------------
# Rural community fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_community() -> dict:
    """Small rural community in the Amazon region."""
    return {
        "population": 800,
        "avg_income_brl": 1_200.0,
        "has_school": True,
        "has_health_unit": True,
        "agricultural": True,
        "state_code": "PA",
        "municipality_code": "1500800",
        "latitude": -2.50,
        "longitude": -44.28,
        "nearest_fiber_km": 45.0,
        "has_grid_power": False,
        "terrain": "amazon_riverine",
        "area_km2": 25.0,
    }
