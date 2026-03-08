"""
ENLACE Rate Limiting Middleware

Simple in-memory sliding-window rate limiter. Production deployments should
replace this with a Redis-backed implementation for multi-process support.

Defaults:
  - General endpoints: 60 requests/minute per IP
  - Auth endpoints (/api/v1/auth/login, /api/v1/auth/register): 10 requests/minute per IP
"""

import logging
import time
from collections import defaultdict
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Auth paths that get stricter rate limits (brute-force protection)
_AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter per client IP."""

    def __init__(
        self,
        app,
        default_limit: int = 60,
        auth_limit: int = 10,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.default_limit = default_limit
        self.auth_limit = auth_limit
        self.window_seconds = window_seconds
        # { (ip, bucket_key): [timestamp, ...] }
        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract the client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    def _cleanup(self, key: tuple[str, str], now: float) -> None:
        """Remove timestamps older than the current window."""
        cutoff = now - self.window_seconds
        entries = self._requests[key]
        # Find first index within the window
        i = 0
        while i < len(entries) and entries[i] < cutoff:
            i += 1
        if i:
            self._requests[key] = entries[i:]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = self._get_client_ip(request)
        path = request.url.path.rstrip("/")
        now = time.time()

        # Determine which bucket and limit to use
        if path in _AUTH_PATHS:
            bucket_key = "auth"
            limit = self.auth_limit
        else:
            bucket_key = "default"
            limit = self.default_limit

        key = (ip, bucket_key)
        self._cleanup(key, now)

        if len(self._requests[key]) >= limit:
            logger.warning(
                "Rate limit exceeded for %s on bucket %s (%d/%d)",
                ip, bucket_key, len(self._requests[key]), limit,
            )
            retry_after = int(self.window_seconds - (now - self._requests[key][0]))
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(max(retry_after, 1))},
            )

        self._requests[key].append(now)
        response = await call_next(request)

        # Include rate-limit headers for client awareness
        remaining = max(0, limit - len(self._requests[key]))
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
