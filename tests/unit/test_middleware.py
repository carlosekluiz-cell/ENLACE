"""Tests for ENLACE API middleware components.

Covers:
- SecurityHeadersMiddleware: security headers injection, HSTS localhost logic
- RateLimiterMiddleware: per-IP sliding window, rate-limit headers, auth path limits

The rate limiter tests force in-memory mode (no Redis) to keep tests fast and
deterministic. Redis integration is tested implicitly by the API-level tests.
"""

from __future__ import annotations

import time
from unittest.mock import patch

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from python.api.middleware.security_headers import SecurityHeadersMiddleware
from python.api.middleware.rate_limiter import RateLimiterMiddleware


# ---------------------------------------------------------------------------
# Helpers – tiny Starlette apps for each middleware under test
# ---------------------------------------------------------------------------


def _ok_endpoint(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


def _make_security_app() -> Starlette:
    """Create a minimal Starlette app with SecurityHeadersMiddleware."""
    app = Starlette(routes=[Route("/test", _ok_endpoint)])
    app.add_middleware(SecurityHeadersMiddleware)
    return app


def _make_rate_limiter_app(
    default_limit: int = 60,
    auth_limit: int = 10,
    window_seconds: int = 60,
) -> tuple[Starlette, RateLimiterMiddleware]:
    """Create a minimal Starlette app with RateLimiterMiddleware.

    Returns (app, middleware_instance) so tests can force in-memory mode.
    """
    app = Starlette(
        routes=[
            Route("/test", _ok_endpoint),
            Route("/api/v1/auth/login", _ok_endpoint),
            Route("/api/v1/auth/register", _ok_endpoint),
        ],
    )
    app.add_middleware(
        RateLimiterMiddleware,
        default_limit=default_limit,
        auth_limit=auth_limit,
        window_seconds=window_seconds,
    )
    return app


def _make_client(
    default_limit: int = 60,
    auth_limit: int = 10,
    window_seconds: int = 60,
) -> TestClient:
    """Create a TestClient with rate limiter forced to in-memory mode."""
    app = _make_rate_limiter_app(default_limit, auth_limit, window_seconds)
    client = TestClient(app)

    # Force a request to build the middleware stack, then force in-memory mode
    client.get("/test")

    # Walk the middleware stack to find our RateLimiterMiddleware
    mw = getattr(app, "middleware_stack", None)
    seen: set[int] = set()
    while mw is not None and id(mw) not in seen:
        seen.add(id(mw))
        if isinstance(mw, RateLimiterMiddleware):
            mw._redis_available = False
            mw._redis_last_failure = float("inf")
            mw._memory_backend._requests.clear()
            break
        mw = getattr(mw, "app", None)

    return client


# ===========================================================================
# SecurityHeadersMiddleware
# ===========================================================================


class TestSecurityHeadersMiddleware:
    """Tests for SecurityHeadersMiddleware."""

    def test_all_security_headers_present(self):
        """Every response must include the five core security headers."""
        client = TestClient(_make_security_app())
        resp = client.get("/test")

        assert resp.status_code == 200
        assert resp.headers["X-Content-Type-Options"] == "nosniff"
        assert resp.headers["X-Frame-Options"] == "DENY"
        assert resp.headers["X-XSS-Protection"] == "1; mode=block"
        assert resp.headers["Cache-Control"] == "no-store"
        assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_hsts_not_set_for_localhost(self):
        """HSTS must NOT be added when Host starts with 'localhost'."""
        client = TestClient(_make_security_app())
        resp = client.get("/test", headers={"Host": "localhost:8000"})

        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_not_set_for_127_0_0_1(self):
        """HSTS must NOT be added when Host starts with '127.0.0.1'."""
        client = TestClient(_make_security_app())
        resp = client.get("/test", headers={"Host": "127.0.0.1:8000"})

        assert "Strict-Transport-Security" not in resp.headers

    def test_hsts_set_for_non_localhost(self):
        """HSTS must be added for production-like hosts."""
        client = TestClient(_make_security_app())
        resp = client.get("/test", headers={"Host": "api.enlace.com"})

        assert "Strict-Transport-Security" in resp.headers
        assert resp.headers["Strict-Transport-Security"] == (
            "max-age=31536000; includeSubDomains"
        )


# ===========================================================================
# RateLimiterMiddleware
# ===========================================================================


class TestRateLimiterRequestsUnderLimit:
    """Requests that are within the rate limit should succeed."""

    def test_success_with_rate_limit_headers(self):
        """A normal request should return 200 with X-RateLimit-* headers."""
        client = _make_client(default_limit=60)
        resp = client.get("/test")

        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "60"
        assert resp.headers["X-RateLimit-Remaining"] == "59"

    def test_remaining_decrements(self):
        """Each request should decrement X-RateLimit-Remaining."""
        client = _make_client(default_limit=5)

        for i in range(5):
            resp = client.get("/test")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Remaining"] == str(5 - 1 - i)


class TestRateLimiterExceedsLimit:
    """Requests that exceed the rate limit should be rejected."""

    def test_429_when_limit_exceeded(self):
        """Once the limit is hit the next request must get 429."""
        client = _make_client(default_limit=3)

        # Use up the budget
        for _ in range(3):
            resp = client.get("/test")
            assert resp.status_code == 200

        # This one should be blocked
        resp = client.get("/test")
        assert resp.status_code == 429

    def test_429_body_contains_detail(self):
        """The 429 response must include an explanatory JSON body."""
        client = _make_client(default_limit=1)
        client.get("/test")  # exhaust the budget

        resp = client.get("/test")
        assert resp.status_code == 429
        body = resp.json()
        assert "detail" in body
        assert "too many requests" in body["detail"].lower()

    def test_retry_after_header_present(self):
        """The 429 response must include a Retry-After header >= 1."""
        client = _make_client(default_limit=1)
        client.get("/test")

        resp = client.get("/test")
        assert resp.status_code == 429
        retry_after = int(resp.headers["Retry-After"])
        assert retry_after >= 1


class TestRateLimiterAuthPaths:
    """Auth endpoints have a stricter rate limit."""

    def test_auth_login_uses_auth_limit(self):
        """Requests to /api/v1/auth/login should use auth_limit."""
        client = _make_client(default_limit=60, auth_limit=3)

        for _ in range(3):
            resp = client.get("/api/v1/auth/login")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Limit"] == "3"

        resp = client.get("/api/v1/auth/login")
        assert resp.status_code == 429

    def test_auth_register_uses_auth_limit(self):
        """Requests to /api/v1/auth/register should use auth_limit."""
        client = _make_client(default_limit=60, auth_limit=2)

        for _ in range(2):
            resp = client.get("/api/v1/auth/register")
            assert resp.status_code == 200

        resp = client.get("/api/v1/auth/register")
        assert resp.status_code == 429

    def test_auth_and_default_buckets_are_independent(self):
        """Exhausting the auth bucket must not affect the default bucket."""
        client = _make_client(default_limit=5, auth_limit=2)

        # Exhaust auth bucket
        for _ in range(2):
            client.get("/api/v1/auth/login")

        resp = client.get("/api/v1/auth/login")
        assert resp.status_code == 429

        # Default bucket should still be fine
        resp = client.get("/test")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "5"


class TestRateLimiterIPDetection:
    """Client IP detection and per-IP isolation."""

    def test_x_forwarded_for_respected(self):
        """X-Forwarded-For should override the socket IP."""
        client = _make_client(default_limit=2)

        # Two requests from the forwarded IP — uses up the budget
        for _ in range(2):
            resp = client.get(
                "/test", headers={"X-Forwarded-For": "203.0.113.50"}
            )
            assert resp.status_code == 200

        # Third from the same forwarded IP — blocked
        resp = client.get(
            "/test", headers={"X-Forwarded-For": "203.0.113.50"}
        )
        assert resp.status_code == 429

    def test_different_ips_have_separate_counters(self):
        """Rate limit counters must be per-IP — different IPs don't interfere."""
        client = _make_client(default_limit=2)

        # Exhaust budget for IP-A
        for _ in range(2):
            client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})

        resp = client.get("/test", headers={"X-Forwarded-For": "10.0.0.1"})
        assert resp.status_code == 429

        # IP-B should still be fine
        resp = client.get("/test", headers={"X-Forwarded-For": "10.0.0.2"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Remaining"] == "1"

    def test_x_forwarded_for_uses_first_ip(self):
        """When X-Forwarded-For has multiple IPs, use the first (client IP)."""
        client = _make_client(default_limit=2)

        # Both requests come from the same real client
        for _ in range(2):
            client.get(
                "/test",
                headers={"X-Forwarded-For": "198.51.100.1, 10.0.0.1, 172.16.0.1"},
            )

        resp = client.get(
            "/test",
            headers={"X-Forwarded-For": "198.51.100.1, 10.0.0.1, 172.16.0.1"},
        )
        assert resp.status_code == 429

        # A different real client behind the same proxies should be OK
        resp = client.get(
            "/test",
            headers={"X-Forwarded-For": "198.51.100.2, 10.0.0.1, 172.16.0.1"},
        )
        assert resp.status_code == 200


class TestRateLimiterWindowExpiry:
    """Requests should be allowed again once the time window expires."""

    def test_requests_allowed_after_window_expires(self):
        """After the window elapses old entries are cleaned up."""
        client = _make_client(default_limit=2, window_seconds=60)

        # Exhaust the budget at t=1000
        with patch(
            "python.api.middleware.rate_limiter.time.time",
            return_value=1000.0,
        ):
            for _ in range(2):
                client.get("/test")

            resp = client.get("/test")
            assert resp.status_code == 429

        # Jump forward past the window — should be allowed again
        with patch(
            "python.api.middleware.rate_limiter.time.time",
            return_value=1061.0,
        ):
            resp = client.get("/test")
            assert resp.status_code == 200
