"""Tests for authentication and multi-tenant modules.

Covers:
- JWT token creation, verification, and decode
- Multi-tenant management (create, get, delete, list)
- Plan rate limits and validation
"""

from __future__ import annotations

import time
from datetime import timedelta

import pytest

from python.api.auth.jwt_handler import (
    create_access_token,
    verify_token,
    decode_token,
)
from python.api.auth.tenant import (
    Tenant,
    PLAN_RATE_LIMITS,
    create_tenant,
    get_tenant,
    list_tenants,
    delete_tenant,
)


# ---------------------------------------------------------------------------
# JWT handler tests
# ---------------------------------------------------------------------------


class TestCreateAccessToken:
    """Tests for create_access_token."""

    def test_returns_string(self):
        token = create_access_token({"sub": "user@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_contains_three_parts(self):
        """JWT tokens are three base64url segments separated by dots."""
        token = create_access_token({"sub": "user@example.com"})
        parts = token.split(".")
        assert len(parts) == 3

    def test_payload_preserved(self):
        """Custom payload fields should survive encode/decode round-trip."""
        data = {"sub": "admin@isp.com.br", "role": "admin", "tenant_id": "abc123"}
        token = create_access_token(data)
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin@isp.com.br"
        assert payload["role"] == "admin"
        assert payload["tenant_id"] == "abc123"

    def test_default_expiration_set(self):
        """Token should contain an 'exp' claim."""
        token = create_access_token({"sub": "u1"})
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload

    def test_custom_expiration(self):
        """Passing expires_delta should override the default."""
        token = create_access_token(
            {"sub": "u2"},
            expires_delta=timedelta(minutes=5),
        )
        payload = decode_token(token)
        # exp should be about 5 minutes from iat
        diff = payload["exp"] - payload["iat"]
        assert 280 <= diff <= 320  # ~5 minutes with tolerance


class TestVerifyToken:
    """Tests for verify_token."""

    def test_valid_token_returns_payload(self):
        token = create_access_token({"sub": "verify@test.com"})
        result = verify_token(token)
        assert result is not None
        assert result["sub"] == "verify@test.com"

    def test_tampered_token_returns_none(self):
        """Modifying the token should invalidate verification."""
        token = create_access_token({"sub": "tamper@test.com"})
        tampered = token[:-5] + "XXXXX"
        result = verify_token(tampered)
        assert result is None

    def test_garbage_token_returns_none(self):
        result = verify_token("not.a.valid.token.at.all")
        assert result is None

    def test_empty_string_returns_none(self):
        result = verify_token("")
        assert result is None

    def test_expired_token_returns_none(self):
        """A token that expired in the past should fail verification."""
        token = create_access_token(
            {"sub": "expired@test.com"},
            expires_delta=timedelta(seconds=-10),
        )
        result = verify_token(token)
        assert result is None


class TestDecodeToken:
    """Tests for decode_token (no verification)."""

    def test_decode_returns_payload(self):
        token = create_access_token({"sub": "decode@test.com"})
        payload = decode_token(token)
        assert payload["sub"] == "decode@test.com"

    def test_decode_invalid_raises(self):
        with pytest.raises(ValueError):
            decode_token("garbage")


# ---------------------------------------------------------------------------
# Tenant management tests
# ---------------------------------------------------------------------------


class TestCreateTenant:
    """Tests for create_tenant."""

    def test_create_returns_tenant(self):
        t = create_tenant("ISP Teste")
        assert isinstance(t, Tenant)
        assert t.name == "ISP Teste"
        assert t.plan == "free"

    def test_tenant_id_is_8_chars(self):
        t = create_tenant("ISP ID Length")
        assert len(t.id) == 8

    def test_free_plan_rate_limit(self):
        t = create_tenant("Free ISP", plan="free")
        assert t.rate_limit == PLAN_RATE_LIMITS["free"]
        assert t.rate_limit == 30

    def test_pro_plan_rate_limit(self):
        t = create_tenant("Pro ISP", plan="pro")
        assert t.rate_limit == PLAN_RATE_LIMITS["pro"]
        assert t.rate_limit == 120

    def test_enterprise_plan_rate_limit(self):
        t = create_tenant("Enterprise ISP", plan="enterprise")
        assert t.rate_limit == PLAN_RATE_LIMITS["enterprise"]
        assert t.rate_limit == 600

    def test_invalid_plan_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid plan"):
            create_tenant("Bad Plan ISP", plan="starter")

    def test_country_code_default(self):
        t = create_tenant("BR ISP")
        assert t.country_code == "BR"

    def test_primary_state(self):
        t = create_tenant("SP ISP", primary_state="SP")
        assert t.primary_state == "SP"


class TestGetTenant:
    """Tests for get_tenant."""

    def test_get_default_tenant(self):
        t = get_tenant("default")
        assert t is not None
        assert t.name == "ENLACE Development"
        assert t.plan == "enterprise"

    def test_get_nonexistent_returns_none(self):
        result = get_tenant("does-not-exist-99999")
        assert result is None

    def test_get_created_tenant(self):
        created = create_tenant("Retrievable ISP")
        fetched = get_tenant(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.name == "Retrievable ISP"


class TestDeleteTenant:
    """Tests for delete_tenant."""

    def test_cannot_delete_default(self):
        result = delete_tenant("default")
        assert result is False
        assert get_tenant("default") is not None

    def test_delete_existing(self):
        t = create_tenant("Deletable ISP")
        result = delete_tenant(t.id)
        assert result is True
        assert get_tenant(t.id) is None

    def test_delete_nonexistent_returns_false(self):
        result = delete_tenant("never-existed-99")
        assert result is False


class TestListTenants:
    """Tests for list_tenants."""

    def test_returns_list(self):
        tenants = list_tenants()
        assert isinstance(tenants, list)
        assert len(tenants) >= 1  # at least the default tenant

    def test_default_always_present(self):
        tenants = list_tenants()
        ids = [t.id for t in tenants]
        assert "default" in ids
