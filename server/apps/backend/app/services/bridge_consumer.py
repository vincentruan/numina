"""Backend-side event buffer and SSE consumer for AI task event delivery.

Phase 1 architecture (backend-owned buffer):
  - Agent uses DeerFlow-native in-memory bridge (producer).
  - Backend consumes agent's HTTP SSE response via ``_pump_agent_sse_to_bridge()``
    and publishes events to a shared backend-owned StreamBridge.
  - Frontend SSE endpoints subscribe to the shared bridge for event delivery.
  - Lifecycle consumer subscribes to the shared bridge for task finalization.

The shared bridge is a singleton per backend process (memory or Redis-backed).
Redis is only used when the backend needs cross-node buffer sharing (cluster);
single-instance deployments use the in-memory bridge with zero external deps.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Any

from packages.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Bridge type for the backend-owned buffer.  "memory" (default) for single
# instance; "redis" for cluster deployments.  Only the backend accesses this
# bridge — the agent uses its own in-memory bridge (DeerFlow native).
_BRIDGE_TYPE: str = os.getenv("STREAM_BRIDGE_TYPE", "memory")

# ---------------------------------------------------------------------------
# Shared bridge singleton (backend-owned buffer)
# ---------------------------------------------------------------------------

_shared_bridge: Any = None


def get_shared_bridge() -> Any:
    """Return the backend-owned shared StreamBridge singleton.

    Creates on first call using ``STREAM_BRIDGE_TYPE`` env var.
    The singleton lives for the process lifetime (FastAPI lifespan manages
    cleanup via ``close_shared_bridge()``).
    """
    global _shared_bridge
    if _shared_bridge is None:
        from packages.stream_bridge import make_stream_bridge
        from packages.stream_bridge.config import StreamBridgeConfig

        config = StreamBridgeConfig(
            type=_BRIDGE_TYPE,
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            queue_maxsize=256,
            stream_ttl_seconds=86400,
        )
        _shared_bridge = make_stream_bridge(config)
        logger.info("Created shared backend bridge (type=%s)", _BRIDGE_TYPE)
    return _shared_bridge


async def close_shared_bridge() -> None:
    """Close the shared bridge.  Call from FastAPI shutdown."""
    global _shared_bridge
    if _shared_bridge is not None:
        await _shared_bridge.close()
        _shared_bridge = None


# ---------------------------------------------------------------------------
# Agent SSE pump (agent HTTP SSE → shared bridge)
# ---------------------------------------------------------------------------


async def _pump_agent_sse_to_bridge(
    *,
    agent_client: Any,
    agent_url: str,
    json_body: dict[str, Any],
    bridge: Any,
    run_id: str,
    task_id: str,
    on_run_id: Callable[[str], None] | None = None,
    on_authoritative_run_id: Callable[[str], None] | None = None,
) -> None:
    """Consume agent HTTP SSE response and publish events to the shared bridge.

    This is the bridge between the agent's HTTP SSE output and the backend's
    shared event buffer.  It reads the agent's streaming HTTP response line by
    line, parses SSE frames, and publishes each event to the backend-owned
    bridge for downstream consumption (frontend SSE + lifecycle consumer).

    Runs as a background ``asyncio.Task`` so it survives frontend disconnect.
    The agent's ``on_disconnect=continue`` ensures the agent keeps producing
    events even if this pump's HTTP connection drops.

    Args:
        agent_client: ``AgentClient`` instance (injects auth headers).
        agent_url: Agent endpoint URL (e.g. ``/internal/gateway/runs/asset-report/{thread_id}``).
        json_body: Request body for the agent trigger.
        bridge: Shared backend StreamBridge instance.
        run_id: Agent run ID for bridge publishing.  Initially ``""`` —
            resolved from ``Content-Location`` header via the ``on_run_id``
            callback before body consumption.  The pump uses a mutable list
            ``[run_id]`` so the resolved UUID is visible after the callback.
        task_id: AITask ID for logging.
        on_run_id: Optional callback invoked with the run_id extracted from
            the agent's response ``Content-Location`` header.  Callers use
            this to spawn lifecycle consumers before the response body is
            fully consumed, avoiding a second HTTP trigger.
        on_authoritative_run_id: Optional callback invoked AFTER the metadata
            event updates ``resolved_run_id[0]``.  The metadata event carries
            the authoritative run_id from the agent (may differ from
            Content-Location when interrupt strategy fires a second run).
            Callers should spawn lifecycle consumers in this callback to
            ensure they subscribe to the correct run_id that receives
            subsequent publishes.
    """
    # Mutable wrapper so the resolved run_id from the callback is visible
    # to the publish loop below.  ``run_id`` arrives as ``""`` (placeholder)
    # and is replaced once the agent returns Content-Location.
    resolved_run_id = [run_id]

    def _set_run_id(cl_run_id: str) -> None:
        # Extract the trailing UUID from the Content-Location URL (e.g.
        # "/internal/gateway/runs/asset-report/{thread}/{run_id}") — MUST match
        # the run_id the lifecycle consumer subscribes with, otherwise publish
        # and subscribe target different bridge streams and never meet.
        resolved_run_id[0] = cl_run_id.rstrip("/").rsplit("/", 1)[-1]

    # Compose the caller's on_run_id callback with our own run_id capture.
    original_on_run_id = on_run_id

    def _composed_on_run_id(cl: str) -> None:
        _set_run_id(cl)
        if original_on_run_id is not None:
            original_on_run_id(cl)

    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json=json_body,
        ) as resp:
            # Early extraction: Content-Location is in response headers,
            # available before the body is consumed.
            if _composed_on_run_id is not None:
                cl = resp.headers.get("Content-Location")
                if cl:
                    try:
                        _composed_on_run_id(cl)
                    except Exception:
                        logger.warning(
                            "[agent-pump] on_run_id callback failed task=%s",
                            task_id,
                            exc_info=True,
                        )
                else:
                    logger.warning(
                        "[agent-pump] Content-Location header missing for task=%s",
                        task_id,
                    )

            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[agent-pump] non-200: status=%s body=%s task=%s",
                    resp.status_code,
                    body[:200],
                    task_id,
                )
                # Publish to resolved run_id (may still be "" if Content-Location
                # was absent — the lifecycle consumer fallback handles that).
                await bridge.publish(
                    resolved_run_id[0],
                    "error",
                    {"error": "报告生成服务异常", "error_type": "AgentError"},
                )
                await bridge.publish_end(resolved_run_id[0])
                return

            current_event = ""
            async for line in resp.aiter_lines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                elif line.startswith("data:"):
                    data_str = line[5:].strip()
                    if data_str and data_str != "[DONE]":
                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            data = data_str
                        event_type = current_event or "message"
                        # Fix: metadata event carries the authoritative run_id
                        # from the agent. Content-Location header may return the
                        # first POST's run_id, but when interrupt strategy fires
                        # a second run is created with a different run_id.
                        # Use the metadata run_id to keep publish/subscribe aligned.
                        if event_type == "metadata" and isinstance(data, dict) and data.get("run_id"):
                            actual_run_id = data["run_id"]
                            if actual_run_id != resolved_run_id[0]:
                                # Update resolved_run_id so subsequent pump
                                # publishing stays aligned. However, do NOT
                                # fire on_authoritative_run_id — the worker
                                # publishes to the Content-Location run_id
                                # (record.run_id) which never changes. Spawning
                                # a new lifecycle consumer with the metadata
                                # run_id would subscribe to a different bridge
                                # stream, causing finance_coach.result and
                                # similar custom events to be silently lost
                                # (task completes but no result is persisted).
                                resolved_run_id[0] = actual_run_id
                        # Skip internal agent events not meant for the frontend
                        if event_type not in ("heartbeat",):
                            await bridge.publish(
                                resolved_run_id[0], event_type, data
                            )
                    current_event = ""
                elif line.startswith("id:"):
                    pass  # SSE event ID — frontend concern, not buffered
                elif line == "":
                    current_event = ""  # Blank line = event boundary

    except Exception as exc:
        logger.warning(
            "[agent-pump] stream failed task=%s err=%s",
            task_id,
            exc,
            exc_info=True,
        )
        await bridge.publish(
            resolved_run_id[0],
            "error",
            {"error": "报告生成服务中断", "error_type": type(exc).__name__},
        )
    finally:
        await bridge.publish_end(resolved_run_id[0])


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
        # Retry a few times — the pump's _on_run_id callback may not have
        # committed the run_id to the AITask row yet.  Without retries,
        # consume_task_stream would raise immediately and the frontend
        # would see an error; with retries, we wait for the pump to catch
        # up (typically < 1 s for a local agent, a few seconds for remote).
        _max_attempts = 10
        _attempt_interval = 1.0  # seconds
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
                await asyncio.sleep(_attempt_interval)
        if not run_id:
            raise RuntimeError(
                f"Task {task_id} has no run_id after {_max_attempts}s "
                f"(agent may not have started yet)"
            )

    # Use shared bridge or create per-call bridge (for tests)
    own_bridge = bridge is None
    if own_bridge:
        bridge = get_shared_bridge()

    try:
        async for entry in bridge.subscribe(
            run_id=run_id,
            last_event_id=last_event_id,
        ):
            if entry is HEARTBEAT_SENTINEL:
                yield {"event": "heartbeat", "data": None}
                continue

            if entry is END_SENTINEL:
                yield {"event": "end", "data": None}
                return

            if isinstance(entry, StreamGap):
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

            yield {"event": entry.event, "data": entry.data}

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
    if task.skill_id in ("report", "coach"):
        from datetime import datetime, timedelta

        from apps.backend.app.models.ai_report import AIReport

        # AIReport.generated_at is a naive DateTime column (UTC stored
        # without tzinfo).  Using datetime.now(UTC) would produce an
        # aware datetime — PostgreSQL rejects naive-vs-aware comparisons
        # with "operator does not exist", causing every report task to
        # fail verification even when the agent wrote the report.
        # Use utcnow() to match the naive-UTC convention (same pattern
        # as AITaskService.get_running_task line 44).
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        recent_report = (
            db.query(AIReport)
            .filter(
                AIReport.family_id == int(family_id),
                AIReport.skill_id == task.skill_id,
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

    Returns:
        An ``asyncio.Task`` running the background consumer.
    """
    from apps.backend.app.services.ai_task_service import AITaskService

    effective_bridge = bridge or get_shared_bridge()

    async def _consume() -> None:
        db = SessionLocal()
        try:
            async for event in bridge_consumer(
                task_id, family_id, run_id=run_id, bridge=effective_bridge
            ):
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
        yield f'event: metadata\ndata: {json.dumps({"task_id": task_id})}\n\n'

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
                yield f"event: error\ndata: {json.dumps(event_data, default=str)}\n\n"
            elif event_type == "end":
                if not error_seen:
                    _db = SessionLocal()
                    try:
                        from apps.backend.app.services.ai_task_service import (
                            AITaskService,
                        )

                        _task = AITaskService.get_task_by_id(
                            task_id, family_id, _db
                        )
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
        logger.error(
            f"Error consuming task stream {task_id}: {e}", exc_info=True
        )
        safe_msg = _map_to_safe_message(e)
        yield f"event: error\ndata: {json.dumps({'error': safe_msg})}\n\n"
