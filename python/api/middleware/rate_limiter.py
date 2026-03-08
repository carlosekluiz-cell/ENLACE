"""
ENLACE Rate Limiting Middleware

Redis-backed sliding-window rate limiter with automatic in-memory fallback.

Uses Redis sorted sets (ZADD + ZREMRANGEBYSCORE + ZCARD) for distributed
rate limiting across multiple worker processes.  If Redis is unreachable the
middleware transparently degrades to a per-process in-memory counter so the
application never crashes due to a cache outage.

Defaults:
  - General endpoints: 60 requests/minute per IP
  - Auth endpoints (/api/v1/auth/login, /api/v1/auth/register): 10 requests/minute per IP
"""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from typing import Callable, Optional

import redis.asyncio as aioredis
from redis.exceptions import NoScriptError as _NoScriptError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from python.api.config import settings

logger = logging.getLogger(__name__)

# Auth paths that get stricter rate limits (brute-force protection)
_AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}

# ---------------------------------------------------------------------------
# Lua script executed atomically on Redis.  In a single round-trip it:
#   1. Prunes entries outside the sliding window
#   2. Adds the new request with its timestamp as the score
#   3. Returns the current count and the score of the oldest surviving entry
#
# KEYS[1] = sorted-set key
# ARGV[1] = cutoff timestamp (now - window)
# ARGV[2] = current timestamp (score for the new entry)
# ARGV[3] = unique member id
# ARGV[4] = TTL for the key (window + buffer)
# ---------------------------------------------------------------------------
_LUA_SLIDING_WINDOW = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[3])
local count = redis.call('ZCARD', KEYS[1])
local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
if #oldest >= 2 then
    return {count, oldest[2]}
end
return {count, ARGV[2]}
"""


class _InMemoryBackend:
    """Per-process fallback when Redis is not available."""

    def __init__(self) -> None:
        # { key_str: [timestamp, ...] }
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def record_and_count(
        self,
        key: str,
        now: float,
        window_seconds: int,
    ) -> tuple[int, float]:
        """Record a request and return (count_in_window, oldest_timestamp).

        Returns the count *including* the new request.
        ``oldest`` is the earliest timestamp still inside the window (used to
        compute Retry-After when the limit is exceeded).
        """
        cutoff = now - window_seconds
        entries = self._requests[key]

        # Prune expired entries
        i = 0
        while i < len(entries) and entries[i] < cutoff:
            i += 1
        if i:
            entries = entries[i:]
            self._requests[key] = entries

        entries.append(now)
        oldest = entries[0] if entries else now
        return len(entries), oldest


class _RedisBackend:
    """Distributed sliding-window backend using Redis sorted sets."""

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: Optional[aioredis.Redis] = None
        self._script_sha: Optional[str] = None

    async def _get_client(self) -> aioredis.Redis:
        """Lazily create (and reuse) a Redis connection pool."""
        if self._pool is None:
            self._pool = aioredis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return self._pool

    async def _load_script(self, client: aioredis.Redis) -> str:
        """Load the Lua script into Redis and cache its SHA."""
        if self._script_sha is None:
            self._script_sha = await client.script_load(_LUA_SLIDING_WINDOW)
        return self._script_sha

    async def record_and_count(
        self,
        key: str,
        now: float,
        window_seconds: int,
    ) -> tuple[int, float]:
        """Atomically record a request and return (count, oldest_ts).

        The sorted set stores ``member=<unique_id>`` with ``score=timestamp``.
        Uses EVALSHA with a pre-loaded Lua script for efficiency.
        """
        client = await self._get_client()
        redis_key = f"enlace:ratelimit:{key}"
        cutoff = now - window_seconds

        # Unique member so concurrent requests never collide
        member = f"{now}:{uuid.uuid4().hex[:8]}"

        sha = await self._load_script(client)
        try:
            result = await client.evalsha(
                sha,
                1,
                redis_key,
                str(cutoff),
                str(now),
                member,
                str(window_seconds + 10),
            )
        except _NoScriptError:
            # Script was flushed; re-load and retry once
            self._script_sha = None
            sha = await self._load_script(client)
            result = await client.evalsha(
                sha,
                1,
                redis_key,
                str(cutoff),
                str(now),
                member,
                str(window_seconds + 10),
            )

        count = int(result[0])
        oldest = float(result[1]) if len(result) > 1 else now
        return count, oldest

    async def close(self) -> None:
        """Shut down the connection pool gracefully."""
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter per client IP.

    Prefers Redis for distributed counting.  Falls back to an in-memory
    backend when Redis is unavailable so the application keeps running.
    """

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

        # Backends
        self._redis_backend = _RedisBackend(settings.redis_url)
        self._memory_backend = _InMemoryBackend()
        self._redis_available: bool = True  # optimistic start
        self._redis_last_failure: float = 0.0
        self._redis_retry_interval: float = 30.0  # seconds between reconnect attempts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract the client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def _check_rate_limit(
        self,
        key: str,
        limit: int,
    ) -> tuple[int, float]:
        """Try Redis first; fall back to in-memory on connection errors.

        After a Redis failure the middleware periodically retries the
        connection (every ``_redis_retry_interval`` seconds) so it can
        recover automatically once Redis comes back.
        """
        now = time.time()

        # Decide whether to attempt Redis this request
        should_try_redis = self._redis_available or (
            now - self._redis_last_failure >= self._redis_retry_interval
        )

        if should_try_redis:
            try:
                count, oldest = await self._redis_backend.record_and_count(
                    key, now, self.window_seconds,
                )
                if not self._redis_available:
                    logger.info("Redis connection restored for rate limiter.")
                    self._redis_available = True
                return count, oldest
            except (
                aioredis.ConnectionError,
                aioredis.TimeoutError,
                OSError,
                RuntimeError,
                Exception,
            ) as exc:
                if self._redis_available:
                    logger.warning(
                        "Redis unavailable for rate limiter (%s); falling back "
                        "to in-memory counting. Distributed rate limiting is "
                        "disabled until Redis recovers.",
                        type(exc).__name__,
                    )
                self._redis_available = False
                self._redis_last_failure = now
                # Reset the pool so stale connections are discarded
                self._redis_backend._pool = None
                self._redis_backend._script_sha = None

        # In-memory fallback
        count, oldest = await self._memory_backend.record_and_count(
            key, now, self.window_seconds,
        )
        return count, oldest

    # ------------------------------------------------------------------
    # Middleware entry point
    # ------------------------------------------------------------------

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = self._get_client_ip(request)
        path = request.url.path.rstrip("/")

        # Determine which bucket and limit to use
        if path in _AUTH_PATHS:
            bucket_key = "auth"
            limit = self.auth_limit
        else:
            bucket_key = "default"
            limit = self.default_limit

        key = f"{ip}:{bucket_key}"
        count, oldest = await self._check_rate_limit(key, limit)

        if count > limit:
            # The request that pushed us over was already recorded.
            # ``oldest`` is the earliest request still in the window; the
            # client must wait until that entry expires out of the window.
            retry_after = int(self.window_seconds - (time.time() - oldest))
            retry_after = max(retry_after, 1)
            logger.warning(
                "Rate limit exceeded for %s on bucket %s (%d/%d)",
                ip, bucket_key, count, limit,
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)

        # Include rate-limit headers for client awareness
        remaining = max(0, limit - count)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
