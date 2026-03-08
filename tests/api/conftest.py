"""Shared fixtures for ENLACE API integration tests.

Provides an async httpx client backed by ASGITransport against the real
FastAPI application, plus helper fixtures for authenticated requests.

The rate limiter is forced into in-memory-only mode and its counters are
cleared before every test so the 60-req/min limit never blocks test traffic.
"""

from __future__ import annotations

import pytest
import httpx

from python.api.main import app
from python.api.auth.jwt_handler import create_access_token
from python.api.middleware.rate_limiter import RateLimiterMiddleware

# Module-level reference, populated once the middleware stack is built.
_rate_limiter: RateLimiterMiddleware | None = None


def _ensure_rate_limiter_ref() -> None:
    """Walk the built ASGI middleware stack and cache the RateLimiterMiddleware."""
    global _rate_limiter
    if _rate_limiter is not None:
        return
    middleware = getattr(app, "middleware_stack", None)
    if middleware is None:
        return
    seen: set[int] = set()
    while middleware is not None and id(middleware) not in seen:
        seen.add(id(middleware))
        if isinstance(middleware, RateLimiterMiddleware):
            _rate_limiter = middleware
            return
        middleware = getattr(middleware, "app", None)


def _reset_rate_limiter() -> None:
    """Clear all rate-limiter state so the next test starts fresh.

    Forces in-memory mode so tests never depend on a running Redis server
    and avoids stale counters left over from a real or failed Redis connection.
    """
    _ensure_rate_limiter_ref()
    if _rate_limiter is None:
        return
    # Clear in-memory counters
    _rate_limiter._memory_backend._requests.clear()
    # Force in-memory mode (do NOT try Redis during tests)
    _rate_limiter._redis_available = False
    # Set the last failure far in the future so retry logic never kicks in
    _rate_limiter._redis_last_failure = float("inf")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    """Auto-use fixture: reset rate limiter state before and after every test."""
    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


@pytest.fixture
async def client():
    """Async httpx client wired to the ENLACE ASGI app (no network).

    On first use, a lightweight GET /health call is made to force the
    middleware stack to be built, after which the rate limiter can be
    located and reset between tests.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        # Force the middleware stack to build (idempotent after first call)
        if _rate_limiter is None:
            await ac.get("/health")
        # Clear any requests that built up during stack initialization
        _reset_rate_limiter()
        yield ac


@pytest.fixture
async def auth_token() -> str:
    """Generate a valid JWT token directly (bypasses login endpoint).

    This avoids hitting the auth rate limiter and is faster than
    making an HTTP request to /api/v1/auth/login for every test.
    """
    token = create_access_token(data={
        "sub": "test",
        "email": "test@test.com",
        "tenant_id": "default",
        "role": "admin",
    })
    return token


@pytest.fixture
async def auth_headers(auth_token: str) -> dict[str, str]:
    """Authorization header dict ready to pass to httpx requests."""
    return {"Authorization": f"Bearer {auth_token}"}
