"""
ENLACE Event Bus

Pub/sub event system using Redis for cross-worker broadcasting.
Falls back to in-memory asyncio.Queue when Redis is unavailable.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

logger = logging.getLogger(__name__)

# In-memory fallback
_subscribers: list[asyncio.Queue] = []


async def _get_redis():
    """Try to connect to Redis; return None if unavailable."""
    try:
        import redis.asyncio as aioredis
        from python.api.config import settings
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        return r
    except Exception:
        return None


async def publish(event_type: str, payload: dict) -> None:
    """Publish an event to all subscribers."""
    message = json.dumps({
        "type": event_type,
        "data": payload,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    redis = await _get_redis()
    if redis:
        try:
            await redis.publish("enlace:events", message)
            return
        except Exception as e:
            logger.warning("Redis publish failed, using in-memory: %s", e)
        finally:
            await redis.aclose()

    # In-memory fallback
    for q in _subscribers:
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            pass


async def subscribe(event_types: Optional[list[str]] = None) -> AsyncGenerator[str, None]:
    """Async generator yielding SSE-formatted event strings.

    If Redis is available, uses pub/sub. Otherwise falls back to in-memory queue.
    """
    redis = await _get_redis()

    if redis:
        try:
            pubsub = redis.pubsub()
            await pubsub.subscribe("enlace:events")
            try:
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        data = msg["data"]
                        if event_types:
                            try:
                                parsed = json.loads(data)
                                if parsed.get("type") not in event_types:
                                    continue
                            except json.JSONDecodeError:
                                continue
                        yield f"data: {data}\n\n"
            finally:
                await pubsub.unsubscribe("enlace:events")
                await pubsub.aclose()
        except Exception as e:
            logger.warning("Redis subscribe failed, using in-memory: %s", e)
            await redis.aclose()
        else:
            return

    # In-memory fallback
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers.append(q)
    try:
        while True:
            try:
                data = await asyncio.wait_for(q.get(), timeout=30.0)
                if event_types:
                    try:
                        parsed = json.loads(data)
                        if parsed.get("type") not in event_types:
                            continue
                    except json.JSONDecodeError:
                        continue
                yield f"data: {data}\n\n"
            except asyncio.TimeoutError:
                # Heartbeat
                yield f": heartbeat\n\n"
    finally:
        _subscribers.remove(q)
