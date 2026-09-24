"""Backend-side event buffer and SSE consumer for AI task event delivery.

Phase 2 architecture (Redis bridge):
  - Agent writes events directly to Redis StreamBridge.
  - Backend triggers the agent via POST (``trigger_agent_run()``) and
    extracts the ``run_id`` from the ``Content-Location`` header.
  - Frontend SSE endpoints subscribe to the shared Redis bridge for event
    delivery via ``consume_task_stream()``.
  - Lifecycle consumer subscribes to the shared bridge for task finalization.

The shared bridge is a singleton per backend process (Redis-backed by default).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from fastapi.responses import StreamingResponse

from apps.backend.app.services.ai_task_service import AITaskService
from packages.db.session import SessionLocal

from .subscriber_registry import tracked_sse_stream

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Agent trigger (POST → run_id extraction)
# ---------------------------------------------------------------------------


async def trigger_agent_run(
    *,
    agent_client: Any,
    agent_url: str,
    json_body: dict[str, Any],
    task_id: str,
    family_id: int | str | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Trigger an agent run and return run_id for Redis subscription.

    Unlike the removed pump function, this does NOT consume
    HTTP SSE.  The agent writes events directly to Redis StreamBridge.
    Backend subscribes to the same Redis Stream via ``bridge.subscribe()``.
    The actual subscribe happens in the caller via ``consume_task_stream()``.

    Args:
        agent_client: ``AgentClient`` instance (injects auth headers).
        agent_url: Agent endpoint URL (e.g. ``/internal/gateway/runs/asset-report/{thread_id}``).
        json_body: Request body for the agent trigger.
        task_id: AITask ID for logging.
        family_id: Family ID for logging.
        headers: Optional extra headers (e.g. ``X-Thread-Id`` for chat).

    Returns:
        dict with 'run_id' (extracted from Content-Location header) and
        'content_location' (raw header value for DB persistence).
    """
    resp = await agent_client.post(agent_url, json=json_body, headers=headers or {})
    resp.raise_for_status()

    # Extract run_id from Content-Location header
    content_location = resp.headers.get("Content-Location", "")
    run_id = (
        content_location.rstrip("/").rsplit("/", 1)[-1]
        if "/" in content_location
        else ""
    )

    logger.info(
        "[trigger_agent_run] task=%s run_id=%s",
        task_id,
        run_id or "(empty)",
    )

    return {"run_id": run_id, "content_location": content_location}


# ---------------------------------------------------------------------------
# Lease heartbeat (defence-in-depth for long-running tasks)
# ---------------------------------------------------------------------------


async def _lease_heartbeat(
    task_id: str,
    family_id: int | str | None,
    stop_event: asyncio.Event,
) -> None:
    """Renew AITask lease every 40s as a safety net for the agent heartbeat.

    The agent runs its own heartbeat (every 40s), but network issues or
    event-loop contention can cause missed beats.  This backend-side
    heartbeat renews the lease every 40s as a fallback so the orphan
    detector (scan every 120s, lease TTL 120s) never kills a live task.
    """
    if family_id is None:
        return
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=40.0)
            break  # stop event set
        except TimeoutError:
            pass
        try:
            _db = SessionLocal()
            try:
                _task = AITaskService.get_task_by_id(int(task_id), int(family_id), _db)
                if _task is None or _task.status not in (
                    "running",
                    "post_processing",
                    "queued",
                ):
                    logger.debug(
                        "[lease-heartbeat] task=%s status=%s — stopping",
                        task_id,
                        _task.status if _task else "gone",
                    )
                    break
                AITaskService.update_lease(int(task_id), int(family_id), _db)
            finally:
                _db.close()
            logger.debug("[lease-heartbeat] task=%s family=%s", task_id, family_id)
        except Exception:
            logger.warning("[lease-heartbeat] failed task=%s", task_id, exc_info=True)


# ---------------------------------------------------------------------------
# Shared bridge singleton (backend-owned buffer)
# ---------------------------------------------------------------------------

_shared_bridge: Any = None


def get_shared_bridge() -> Any:
    """Return the backend-owned shared StreamBridge singleton.

    Creates on first call using ``STREAM_BRIDGE_TYPE`` env var (default ``"redis"``).
    The singleton lives for the process lifetime (FastAPI lifespan manages
    cleanup via ``close_shared_bridge()``.
    """
    global _shared_bridge
    if _shared_bridge is None:
        from packages.stream_bridge import make_stream_bridge
        from packages.stream_bridge.config import StreamBridgeConfig

        bridge_type = os.environ.get("STREAM_BRIDGE_TYPE", "redis")
        config = StreamBridgeConfig(
            type=bridge_type,
            redis_url=os.environ.get("REDIS_URL", "redis://redis:6379/0"),
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        _shared_bridge = make_stream_bridge(config)
        logger.info("Created shared backend bridge (type=%s)", bridge_type)
    return _shared_bridge


async def close_shared_bridge() -> None:
    """Close the shared bridge.  Call from FastAPI shutdown."""
    global _shared_bridge
    if _shared_bridge is not None:
        await _shared_bridge.close()
        _shared_bridge = None


# ---------------------------------------------------------------------------
# Bridge subscriber (shared bridge → events)
# ---------------------------------------------------------------------------


async def bridge_consumer(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
    run_id: str | None = None,
    *,
    bridge: Any | None = None,
    recover_from_gap: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    """Consume events from the backend-owned shared bridge.

    Subscribes to the shared StreamBridge for the given run_id.
    Yields events as dicts with 'event' and 'data' keys.

    Args:
        task_id: AITask primary key (used to look up the run_id)
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection
        run_id: Pre-resolved agent RunRecord UUID. When provided, skips the
                DB lookup (avoids race with attach_run_id commit).
        bridge: Optional shared bridge instance.  When None, creates a
                per-call bridge (backward compatibility for tests).
        recover_from_gap: When True, if a StreamGap is encountered,
                re-subscribe from the latest available event ID instead
                of yielding the gap and returning.  Used by the lifecycle
                consumer which only needs the terminal ``end`` event and
                can tolerate gaps in intermediate events.

    Yields:
        Dict with 'event' (str) and 'data' (Any) keys
    """
    from apps.backend.app.services.ai_task_service import AITaskService
    from packages.stream_bridge import (
        END_SENTINEL,
        HEARTBEAT_SENTINEL,
        StreamGap,
    )

    # Resolve run_id: prefer caller-provided value (avoids DB lookup race),
    # fall back to querying the AITask table.
    if not run_id:
        _max_attempts = 15
        _attempt_interval = 2.0
        for _attempt in range(_max_attempts):
            db = SessionLocal()
            try:
                task = AITaskService.get_task_by_id(task_id, family_id, db)
                if not task:
                    raise RuntimeError(f"Task {task_id} not found")
                if task.run_id:
                    run_id = task.run_id
                    break
            finally:
                db.close()
            if _attempt < _max_attempts - 1:
                await asyncio.sleep(_attempt_interval * (1 + _attempt * 0.1))
        if not run_id:
            raise RuntimeError(
                f"Task {task_id} has no run_id after ~15s "
                f"(agent may not have started yet)"
            )

    # Use shared bridge or create per-call bridge (for tests)
    own_bridge = bridge is None
    if own_bridge:
        bridge = get_shared_bridge()
    assert bridge is not None, "stream bridge is not initialised"

    try:
        # P1 fix: gap recovery loop.  When recover_from_gap is True and the
        # bridge reports a StreamGap (retained buffer overflow), re-subscribe
        # from the latest available event ID instead of giving up.  This
        # prevents the lifecycle consumer from incorrectly failing a task
        # when it falls behind the MAXLEN window.
        current_last_event_id = last_event_id
        _MAX_GAP_RECOVERIES = 3
        _gap_recoveries = 0

        # Overall timeout to prevent indefinite hangs if the agent crashes
        # without publishing END_SENTINEL.  30 min covers long report runs.
        _SUBSCRIBE_TIMEOUT_SECS = int(
            os.environ.get("BRIDGE_SUBSCRIBE_TIMEOUT", "1800")
        )
        _deadline = asyncio.get_event_loop().time() + _SUBSCRIBE_TIMEOUT_SECS

        while True:
            gap_encountered = False
            async for entry in bridge.subscribe(
                run_id=run_id,
                last_event_id=current_last_event_id,
            ):
                # Check deadline on every event
                if asyncio.get_event_loop().time() > _deadline:
                    logger.error(
                        "[bridge_consumer] subscribe timeout (%ds) task=%s run=%s",
                        _SUBSCRIBE_TIMEOUT_SECS,
                        task_id,
                        run_id,
                    )
                    yield {
                        "event": "error",
                        "data": {"error": "事件流超时，请重新触发"},
                    }
                    return

                if entry is HEARTBEAT_SENTINEL:
                    yield {"event": "heartbeat", "data": None}
                    continue

                if entry is END_SENTINEL:
                    yield {"event": "end", "data": None}
                    return

                if isinstance(entry, StreamGap):
                    if recover_from_gap and _gap_recoveries < _MAX_GAP_RECOVERIES:
                        # Re-subscribe from latest available position.
                        # The lifecycle consumer only needs the terminal
                        # ``end`` event; losing intermediate events is
                        # acceptable.
                        current_last_event_id = entry.latest_available_event_id
                        _gap_recoveries += 1
                        logger.warning(
                            "[bridge_consumer] gap recovered task=%s "
                            "resuming_from=%s (recovery %d/%d)",
                            task_id,
                            current_last_event_id,
                            _gap_recoveries,
                            _MAX_GAP_RECOVERIES,
                        )
                        gap_encountered = True
                        break  # break inner loop, re-subscribe in outer loop
                    # No recovery: yield gap and return (SSE consumer path)
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

                yield {"event": entry.event, "data": entry.data, "id": entry.id}

            if not gap_encountered:
                # Inner loop ended without gap (shouldn't happen normally,
                # but handle gracefully to avoid infinite loop).
                return
    finally:
        if own_bridge:
            await bridge.close()


# ---------------------------------------------------------------------------
# Task result verification
# ---------------------------------------------------------------------------


def _verify_task_result(task_id: str, family_id: int, db: Any) -> bool:
    """Verify the task produced its expected result in the DB.

    For report tasks, checks that a row exists in ``ai_reports`` for this
    family within the last 10 minutes.  For other task types, returns True
    (the agent's ``set_error`` already controls the pipeline status).

    Returns False only when the task type expects persisted data that is
    missing — indicating the pipeline silently failed.
    Returns True (trust the pipeline) when the task cannot be looked up
    (e.g. invalid ID in tests).
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    try:
        task = AITaskService.get_task_by_id(task_id, family_id, db)
    except (ValueError, TypeError):
        return True
    if not task:
        return False
    if task.skill_id in ("asset-report", "finance-coach"):
        from datetime import UTC, datetime, timedelta

        from apps.backend.app.models.ai_report import AIReport

        cutoff = datetime.now(UTC) - timedelta(minutes=10)

        report_skill_id = task.skill_id

        recent_report = (
            db.query(AIReport)
            .filter(
                AIReport.family_id == int(family_id),
                AIReport.skill_id == report_skill_id,
                AIReport.generated_at >= cutoff,
            )
            .first()
        )
        return recent_report is not None
    return True


# ---------------------------------------------------------------------------
# Safe error message mapping
# ---------------------------------------------------------------------------


def _map_to_safe_message(exc: Exception) -> str:
    """Map internal exceptions to user-safe SSE error messages."""
    if isinstance(exc, RuntimeError):
        msg = str(exc)
        if "not found" in msg.lower():
            return "任务未找到"
        return "任务执行异常"
    return "服务异常"


# ---------------------------------------------------------------------------
# Lifecycle consumer (independent background task)
# ---------------------------------------------------------------------------


def _spawn_lifecycle_consumer(
    task_id: str,
    family_id: int,
    run_id: str | None,
    on_result: Callable[[str, Any], Coroutine[Any, Any, None]] | None = None,
    *,
    bridge: Any | None = None,
    thread_id: str | None = None,
) -> asyncio.Task[None]:
    """Spawn an independent background consumer for task lifecycle management.

    Subscribes to the shared bridge independently of any SSE client.
    Handles complete_task / fail_task on stream end.

    Args:
        task_id: AITask primary key
        family_id: Family ID for tenant isolation
        run_id: Pre-resolved agent RunRecord UUID
        on_result: Optional async callback invoked for each ``custom`` event.
        bridge: Optional shared bridge.  When None, uses get_shared_bridge().
        thread_id: DeerFlow thread UUID for event persistence. When provided,
            events are persisted to DbRunEventStore for permanent logging.

    Returns:
        An ``asyncio.Task`` running the background consumer.
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    effective_bridge = bridge or get_shared_bridge()

    async def _consume() -> None:
        db = SessionLocal()
        try:
            # P1 fix: recover_from_gap=True so the lifecycle consumer
            # re-subscribes from the latest position when the Redis buffer
            # overflows, instead of incorrectly failing the task.
            async for event in bridge_consumer(
                task_id,
                family_id,
                run_id=run_id,
                bridge=effective_bridge,
                recover_from_gap=True,
            ):
                event_type = event["event"]
                event_data = event["data"]

                # Event persistence (U4): write to DbRunEventStore if enabled.
                # Non-fatal: failures are logged and skipped.
                if (
                    thread_id
                    and run_id
                    and event_type in ("messages", "custom", "end", "error")
                ):
                    try:
                        from apps.backend.app.services.event_persistence import (
                            persist_event,
                        )

                        await persist_event(
                            thread_id=thread_id,
                            run_id=run_id,
                            event_type=event_type,
                            event_data=event_data,
                            family_id=family_id,
                        )
                    except Exception:
                        logger.debug(
                            "[lifecycle] event persistence failed (non-fatal) event=%s",
                            event_type,
                            exc_info=True,
                        )

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
                    AITaskService.fail_task(task_id, "事件流缓冲区间断，请重新触发", db)
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


# ---------------------------------------------------------------------------
# SSE forwarder (shared bridge → SSE text for frontend)
# ---------------------------------------------------------------------------


async def consume_task_stream(
    task_id: str,
    family_id: int,
    last_event_id: str | None = None,
    run_id: str | None = None,
    *,
    bridge: Any | None = None,
) -> AsyncIterator[str]:
    """SSE event forwarder — yields SSE-formatted strings.

    Subscribes to the shared bridge and formats events as SSE text.
    Lifecycle management is handled by ``_spawn_lifecycle_consumer``.

    Args:
        task_id: AITask primary key
        family_id: Family ID for tenant isolation
        last_event_id: Optional SSE Last-Event-ID for reconnection
        run_id: Pre-resolved agent RunRecord UUID
        bridge: Optional shared bridge.  When None, uses get_shared_bridge().

    Yields:
        SSE-formatted strings (e.g., "event: update\\ndata: {...}\\n\\n")
    """
    effective_bridge = bridge or get_shared_bridge()

    try:
        # Emit task_id as the first SSE event so the frontend can immediately
        # enable cancel / progress-tracking without polling.
        yield f"event: metadata\ndata: {json.dumps({'task_id': task_id})}\n\n"

        error_seen = False
        async for event in bridge_consumer(
            task_id,
            family_id,
            last_event_id,
            run_id=run_id,
            bridge=effective_bridge,
        ):
            event_type = event["event"]
            event_data = event["data"]

            if event_type == "heartbeat":
                yield ": heartbeat\n\n"
            elif event_type == "error":
                error_seen = True
                error_id = event.get("id")
                error_id_line = f"id: {error_id}\n" if error_id else ""
                yield f"event: error\n{error_id_line}data: {json.dumps(event_data, default=str)}\n\n"
            elif event_type == "end":
                if not error_seen:
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
                # P1-4: include SSE id: field for Last-Event-ID reconnection
                event_id = event.get("id")
                id_line = f"id: {event_id}\n" if event_id else ""
                yield f"event: {event_type}\n{id_line}data: {json.dumps(event_data, default=str)}\n\n"

    except Exception as e:
        logger.error(f"Error consuming task stream {task_id}: {e}", exc_info=True)
        safe_msg = _map_to_safe_message(e)
        yield f"event: error\ndata: {json.dumps({'error': safe_msg})}\n\n"


# ---------------------------------------------------------------------------
# High-level helper: trigger agent + full SSE lifecycle
# ---------------------------------------------------------------------------


async def trigger_and_stream(
    *,
    agent_client: Any,
    agent_url: str,
    json_body: dict[str, Any],
    task_id: str,
    family_id: int | str,
    session_id: str,
    last_event_id: str | None = None,
    on_result: Callable[..., Coroutine[Any, Any, None]] | None = None,
    thread_id: str | None = None,
) -> StreamingResponse:
    """Full SSE lifecycle: trigger agent → heartbeat → lifecycle consumer → stream.

    Encapsulates the common pattern shared by ai_report, ai_finance_coach,
    and ai_literacy_report routers.

    Note: learning_child.py is NOT included — it has a different SSE lifecycle
    (no heartbeat, no tracked_sse_stream, uses consume_task_stream with
    Last-Event-ID reconnection, and manages its own DB session).

    Raises:
        Exception: If agent trigger fails — caller handles with app-specific error stream.
    """
    # 1. Trigger agent
    result = await trigger_agent_run(
        agent_client=agent_client,
        agent_url=agent_url,
        json_body=json_body,
        task_id=task_id,
        family_id=family_id,
    )
    run_id = result["run_id"]

    # 2. Attach run_id to task
    AITaskService.extract_and_attach_run_id(
        task_id, result["content_location"], family_id
    )

    # 3. Lease heartbeat
    _hb_stop = asyncio.Event()
    _hb_task = asyncio.create_task(_lease_heartbeat(task_id, family_id, _hb_stop))

    # 4. Lifecycle consumer
    shared_bridge = get_shared_bridge()
    lifecycle_kwargs: dict[str, Any] = dict(
        task_id=task_id,
        family_id=family_id,
        run_id=run_id,
        bridge=shared_bridge,
    )
    if on_result is not None:
        lifecycle_kwargs["on_result"] = on_result
    lifecycle_kwargs["thread_id"] = thread_id if thread_id is not None else session_id
    _spawn_lifecycle_consumer(**lifecycle_kwargs)

    # 5. SSE forwarder with cleanup
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=run_id,
        bridge=shared_bridge,
    )

    async def _stream():
        try:
            async for chunk in stream_gen:
                yield chunk
        finally:
            _hb_stop.set()
            with contextlib.suppress(asyncio.CancelledError):
                await _hb_task

    return StreamingResponse(
        tracked_sse_stream(task_id, _stream()),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
