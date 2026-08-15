"""Backend-side Redis stream subscriber for AI task event consumption.

This module provides the bridge_consumer that subscribes to Redis streams
published by the agent's StreamBridge, enabling backend SSE endpoints to
consume task events with reconnection support.

Replaces the direct HTTP proxy pattern (ai_report.py:_stream_asset_report_sse)
with Redis Stream subscription for cross-process event delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncIterator

from packages.db.session import SessionLocal

logger = logging.getLogger(__name__)


async def bridge_consumer(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Consume events from a task's Redis stream.

    Subscribes to the Redis stream published by the agent's StreamBridge
    for the given task_id. Yields events as dicts with 'event' and 'data' keys.

    Args:
        task_id: AITask primary key (the stream key suffix)
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection

    Yields:
        Dict with 'event' (str) and 'data' (Any) keys

    Raises:
        RuntimeError: If Redis connection fails or stream not found
    """
    from apps.agent.services.runtime.stream_bridge import (
        END_SENTINEL,
        HEARTBEAT_SENTINEL,
        StreamGap,
        make_stream_bridge,
    )
    from apps.agent.services.runtime.stream_bridge.config import StreamBridgeConfig

    # Create Redis bridge (or memory bridge for dev)
    # In production, this reads from the same Redis instance the agent writes to
    config = StreamBridgeConfig(
        type="redis",
        redis_url="redis://localhost:6379/0",  # TODO: read from env/config
        queue_maxsize=256,
        stream_ttl_seconds=86400,
    )
    bridge = make_stream_bridge(config)

    try:
        # Subscribe to the task's stream
        # The bridge.subscribe() method handles:
        # - Last-Event-ID replay
        # - StreamGap detection (cursor beyond retained buffer)
        # - Heartbeat sentinels (every 15s)
        # - End sentinel (stream closed)
        async for entry in bridge.subscribe(
            run_id=task_id,
            last_event_id=last_event_id,
        ):
            if entry is HEARTBEAT_SENTINEL:
                # Yield heartbeat as a special event
                yield {"event": "heartbeat", "data": None}
                continue

            if entry is END_SENTINEL:
                # Stream ended - yield end event and stop
                yield {"event": "end", "data": None}
                return

            if isinstance(entry, StreamGap):
                # Gap detected - cursor beyond retained buffer
                # Yield gap event with recovery info
                yield {
                    "event": "gap",
                    "data": {
                        "code": "stream_replay_gap",
                        "requested_event_id": entry.requested_event_id,
                        "earliest_available": entry.earliest_available_event_id,
                        "latest_available": entry.latest_available_event_id,
                    },
                }
                return

            # Regular event - yield as-is
            yield {"event": entry.event, "data": entry.data}

    finally:
        # Cleanup bridge resources
        await bridge.close()


async def consume_task_stream(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
) -> AsyncIterator[str]:
    """High-level wrapper that yields SSE-formatted strings.

    Consumes from bridge_consumer and formats each event as SSE text.
    Updates AITask status when end event is received.

    Args:
        task_id: AITask primary key
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection

    Yields:
        SSE-formatted strings (e.g., "event: update\ndata: {...}\n\n")
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    try:
        async for event in bridge_consumer(task_id, family_id, last_event_id):
            event_type = event["event"]
            event_data = event["data"]

            # Format as SSE
            if event_type == "heartbeat":
                yield ": heartbeat\n\n"
            elif event_type == "end":
                # Mark task as completed
                db = SessionLocal()
                try:
                    AITaskService.complete_task(task_id, db)
                finally:
                    db.close()
                yield f"event: end\ndata: {json.dumps(None)}\n\n"
                return
            elif event_type == "gap":
                yield f"event: gap\ndata: {json.dumps(event_data)}\n\n"
                return
            else:
                yield f"event: {event_type}\ndata: {json.dumps(event_data, default=str)}\n\n"

    except Exception as e:
        logger.error(f"Error consuming task stream {task_id}: {e}")
        # Mark task as failed
        db = SessionLocal()
        try:
            AITaskService.fail_task(task_id, str(e), db)
        finally:
            db.close()
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
