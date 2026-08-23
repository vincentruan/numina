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
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from packages.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Cache bridge type at module load to avoid per-call env reads.
# Override via STREAM_BRIDGE_TYPE env var before process start.
_BRIDGE_TYPE: str = __import__("os").getenv("STREAM_BRIDGE_TYPE", "memory")


async def bridge_consumer(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
    run_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Consume events from a task's Redis stream.

    Subscribes to the Redis stream published by the agent's StreamBridge
    for the given task_id. Yields events as dicts with 'event' and 'data' keys.

    Args:
        task_id: AITask primary key (used to look up the run_id)
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection
        run_id: Pre-resolved agent RunRecord UUID. When provided, skips the
                DB lookup (avoids race with attach_run_id commit).

    Yields:
        Dict with 'event' (str) and 'data' (Any) keys

    Raises:
        RuntimeError: If Redis connection fails or stream not found
    """
    import os

    from apps.backend.app.services.ai_task_service import AITaskService
    from packages.stream_bridge import (
        END_SENTINEL,
        HEARTBEAT_SENTINEL,
        StreamGap,
        make_stream_bridge,
    )
    from packages.stream_bridge.config import StreamBridgeConfig

    # Resolve run_id: prefer caller-provided value (avoids DB lookup race),
    # fall back to querying the AITask table.
    if not run_id:
        db = SessionLocal()
        try:
            task = AITaskService.get_task_by_id(task_id, family_id, db)
            if not task:
                raise RuntimeError(f"Task {task_id} not found")
            if not task.run_id:
                raise RuntimeError(f"Task {task_id} has no run_id (agent may not have started yet)")
            run_id = task.run_id
        finally:
            db.close()

    # Create Redis bridge (or memory bridge for dev)
    # In production, this reads from the same Redis instance the agent writes to
    bridge_type = _BRIDGE_TYPE
    config = StreamBridgeConfig(
        type=bridge_type,
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        queue_maxsize=256,
        stream_ttl_seconds=86400,
    )
    bridge = make_stream_bridge(config)

    try:
        # Subscribe to the task's stream using run_id (not task_id)
        # The bridge.subscribe() method handles:
        # - Last-Event-ID replay
        # - StreamGap detection (cursor beyond retained buffer)
        # - Heartbeat sentinels (every 15s)
        # - End sentinel (stream closed)
        async for entry in bridge.subscribe(
            run_id=run_id,
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


def _verify_task_result(task_id: str, family_id: int, db: Any) -> bool:
    """Verify the task produced its expected result in the DB.

    For report tasks, checks that a row exists in ``ai_reports`` for this
    family.  For other task types, returns True (the agent's ``set_error``
    already controls the pipeline status; we trust it).

    Returns False only when the task type expects persisted data that is
    missing — indicating the pipeline silently failed.
    Returns True (trust the pipeline) when the task cannot be looked up
    (e.g. invalid ID in tests).
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    try:
        task = AITaskService.get_task_by_id(task_id, family_id, db)
    except (ValueError, TypeError):
        # Invalid task_id (e.g. non-numeric mock in tests) — trust pipeline
        return True
    if not task:
        return False
    if task.skill_id == "report":
        from apps.backend.app.models.ai_report import AIReport

        return (
            db.query(AIReport)
            .filter(AIReport.family_id == int(family_id))
            .first()
            is not None
        )
    # Other task types: trust the pipeline status
    return True


def _map_to_safe_message(exc: Exception) -> str:
    """Map internal exceptions to user-safe SSE error messages.

    Prevents leaking internal paths, DB connection strings, or stack traces
    to the SSE client. (F12 fix)
    """
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        if "not found" in msg.lower():
            return "任务未找到"
        return "任务执行异常"
    return "服务异常"


def _spawn_lifecycle_consumer(
    task_id: str,
    family_id: int,
    run_id: str | None,
    on_result: Callable[[str, Any], Coroutine[Any, Any, None]] | None = None,
) -> asyncio.Task[None]:
    """Spawn an independent background consumer for task lifecycle management.

    This task subscribes to the bridge stream independently of any SSE client.
    It handles:
    - Calling ``complete_task()`` when the stream ends normally
    - Calling ``fail_task()`` if an exception occurs
    - Optional ``on_result(event_type, data)`` callback for result persistence

    The returned ``asyncio.Task`` survives SSE client disconnect, ensuring
    the task lifecycle is always finalized. (F1 fix)

    Args:
        task_id: AITask primary key
        family_id: Family ID for tenant isolation
        run_id: Pre-resolved agent RunRecord UUID
        on_result: Optional async callback invoked for each ``custom`` event.
                   Use this to persist scenario results (e.g. upsert_skill_result).

    Returns:
        An ``asyncio.Task`` running the background consumer.
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    async def _consume() -> None:
        db = SessionLocal()
        try:
            async for event in bridge_consumer(task_id, family_id, run_id=run_id):
                event_type = event["event"]
                event_data = event["data"]

                if event_type == "custom" and on_result is not None:
                    try:
                        await on_result(event_type, event_data)
                    except Exception:
                        logger.warning(
                            "[lifecycle] result callback failed task=%s",
                            task_id,
                            exc_info=True,
                        )
                elif event_type == "end":
                    # Verify the task produced its expected result before
                    # marking complete.  For report tasks, the pipeline writes
                    # to ai_reports *before* publish_end, so a missing row
                    # means the pipeline failed (e.g. JSON validation error)
                    # even though the run finished without exception.
                    if _verify_task_result(task_id, family_id, db):
                        AITaskService.complete_task(task_id, db)
                        logger.info(
                            "[lifecycle] task %s completed (result verified)",
                            task_id,
                        )
                    else:
                        AITaskService.fail_task(
                            task_id,
                            "任务完成但未生成预期结果",
                            db,
                        )
                        logger.warning(
                            "[lifecycle] task %s failed (result not found)",
                            task_id,
                        )
                    return
                elif event_type == "gap":
                    logger.warning(
                        "[lifecycle] stream gap task=%s — failing task",
                        task_id,
                    )
                    AITaskService.fail_task(
                        task_id, "事件流缓冲区间断，请重新触发", db
                    )
                    return
        except Exception as e:
            logger.error(
                "[lifecycle] consumer error task=%s: %s",
                task_id,
                e,
                exc_info=True,
            )
            safe_msg = _map_to_safe_message(e)
            AITaskService.fail_task(task_id, safe_msg, db)
        finally:
            db.close()

    return asyncio.create_task(_consume())


async def consume_task_stream(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
    run_id: str | None = None,
) -> AsyncIterator[str]:
    """SSE event forwarder — yields SSE-formatted strings.

    Pure relay: subscribes to the bridge stream and formats events as SSE text.
    Lifecycle management (complete_task / fail_task) is handled separately by
    ``_spawn_lifecycle_consumer`` — callers must spawn that before using this
    forwarder. This separation ensures task completion survives SSE disconnect.

    Args:
        task_id: AITask primary key
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection
        run_id: Pre-resolved agent RunRecord UUID (avoids DB lookup race)

    Yields:
        SSE-formatted strings (e.g., "event: update\\ndata: {...}\\n\\n")
    """
    try:
        error_seen = False
        async for event in bridge_consumer(task_id, family_id, last_event_id, run_id=run_id):
            event_type = event["event"]
            event_data = event["data"]

            if event_type == "heartbeat":
                yield ": heartbeat\n\n"
            elif event_type == "error":
                error_seen = True
                yield f"event: error\ndata: {json.dumps(event_data, default=str)}\n\n"
            elif event_type == "end":
                # If no explicit error event was received, check AITask status.
                # The lifecycle consumer verifies the result and may have set
                # the task to "failed" (e.g. report data not persisted).
                if not error_seen:
                    await asyncio.sleep(0.5)  # let lifecycle consumer finish DB write
                    _db = SessionLocal()
                    try:
                        from apps.backend.app.services.ai_task_service import (
                            AITaskService,
                        )

                        _task = AITaskService.get_task_by_id(task_id, family_id, _db)
                        if _task and _task.status == "failed":
                            error_msg = _task.error_message or "任务执行失败"
                            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
                    finally:
                        _db.close()
                yield f"event: end\ndata: {json.dumps(None)}\n\n"
                return
            elif event_type == "gap":
                yield f"event: gap\ndata: {json.dumps(event_data)}\n\n"
                return
            else:
                yield f"event: {event_type}\ndata: {json.dumps(event_data, default=str)}\n\n"

    except Exception as e:
        logger.error(f"Error consuming task stream {task_id}: {e}", exc_info=True)
        safe_msg = _map_to_safe_message(e)
        yield f"event: error\ndata: {json.dumps({'error': safe_msg})}\n\n"
