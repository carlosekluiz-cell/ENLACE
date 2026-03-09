"""
ENLACE Events Router

Server-Sent Events (SSE) endpoint for real-time updates.
Streams pipeline status, data updates, and notifications to connected clients.
"""

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from python.api.auth.dependencies import require_auth
from python.api.services.event_bus import subscribe

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("/stream")
async def event_stream(
    types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    user: dict = Depends(require_auth),
):
    """SSE endpoint for real-time updates.

    Event types: pipeline_status, data_updated, notification
    Sends heartbeat every 30s to keep connection alive.
    """
    event_types = [t.strip() for t in types.split(",")] if types else None

    async def generate():
        async for event in subscribe(event_types):
            yield event

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
