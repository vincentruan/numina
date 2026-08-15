"""SSE frame formatting and stream consumer for the Numina streaming gateway.

Ports the core SSE logic from DeerFlow's ``app/gateway/services.py`` into
Numina, adding multi-tenant (family_id) integration for run metadata.

# [Copied from DeerFlow Reference] — adapted from app/gateway/services.py
# [Integrated with Numina Multi-Tenant] — family_id in run metadata
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from deerflow.runtime import (
    END_SENTINEL,
    HEARTBEAT_SENTINEL,
    DisconnectMode,
    RunManager,
    RunRecord,
    RunStatus,
    StreamBridge,
)
from fastapi import HTTPException, Request

from .lifespan import get_run_manager, get_stream_bridge
from .stream_bridge import StreamGap
from .worker import run_agent

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SSE formatting
# ---------------------------------------------------------------------------


# [Copied from DeerFlow Reference] — exact SSE frame format
def format_sse(event: str, data: Any, *, event_id: str | None = None) -> str:
    """Format a single SSE frame.

    Field order: ``event:`` -> ``data:`` -> ``id:`` (optional) -> blank line.
    This matches the LangGraph Platform wire format consumed by the
    ``useStream`` React hook and the Python ``langgraph-sdk`` SSE decoder.

    # [Copied from DeerFlow Reference] — app/gateway/services.py format_sse
    """
    payload = json.dumps(data, default=str, ensure_ascii=False)
    parts = [f"event: {event}", f"data: {payload}"]
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Input / config helpers
# ---------------------------------------------------------------------------


def normalize_stream_modes(raw: list[str] | str | None) -> list[str]:
    """Normalize the stream_mode parameter to a list.

    Default matches what ``useStream`` expects: values + messages-tuple.
    """
    if raw is None:
        return ["values"]
    if isinstance(raw, str):
        return [raw]
    return raw if raw else ["values"]


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------


# [Copied from DeerFlow Reference] — sse_consumer with heartbeat + disconnect handling
# [U2 Enhancement] — StreamGap handling + terminal probe + orphan recovery
async def sse_consumer(
    bridge: StreamBridge,
    record: RunRecord,
    request: Request,
    run_mgr: RunManager,
):
    """Async generator that yields SSE frames from the bridge.

    The ``finally`` block implements ``on_disconnect`` semantics:
    - ``cancel``: abort the background task on client disconnect.
    - ``continue``: let the task run; events are discarded.

    U2 enhancements (DeerFlow parity):
    - StreamGap handling: when cursor is beyond retained buffer, yield gap event
    - Terminal probe: if record is terminal and stream is empty, yield end immediately
    - Orphan recovery: after heartbeat, check if run was terminalized by orphan recovery

    # [Copied from DeerFlow Reference] — app/gateway/services.py sse_consumer
    """
    last_event_id = request.headers.get("Last-Event-ID")

    # U2: Terminal record probe — if record is already terminal and stream is empty,
    # yield end frame immediately instead of hanging on heartbeat
    if await _terminal_record_stream_missing(bridge, record):
        yield format_sse("end", None)
        return

    gap_emitted = False
    try:
        async for entry in bridge.subscribe(record.run_id, last_event_id=last_event_id):
            if await request.is_disconnected():
                break

            if entry is HEARTBEAT_SENTINEL:
                yield ": heartbeat\n\n"

                # U2: DeerFlow parity — orphan recovery observed after heartbeat
                # Check if the run was terminalized by orphan recovery while we were
                # waiting on heartbeat. If so, yield end frame and return.
                if await _orphan_recovery_observed_after_heartbeat(record):
                    yield format_sse("end", None)
                    return

                continue

            # U2: StreamGap handling — cursor is beyond retained buffer
            if isinstance(entry, StreamGap):
                gap_emitted = True
                yield format_sse(
                    "gap",
                    {
                        "code": "stream_replay_gap",
                        "run_id": record.run_id,
                        "requested_event_id": entry.requested_event_id,
                        "earliest_available_event_id": entry.earliest_available_event_id,
                        "latest_available_event_id": entry.latest_available_event_id,
                        "recovery": "reload_durable_state",
                    },
                )
                return

            if entry is END_SENTINEL:
                yield format_sse("end", None, event_id=entry.id or None)
                return

            yield format_sse(entry.event, entry.data, event_id=entry.id or None)

    finally:
        # [Copied from DeerFlow Reference] — on_disconnect=cancel aborts background task
        # [Integrated with Numina Multi-Tenant] — uses record.metadata["family_id"]
        # U2: Skip cancel if gap was emitted (client will reconnect) or if
        # on_disconnect=continue (background task should keep running)
        if (
            record.status in (RunStatus.pending, RunStatus.running)
            and record.on_disconnect == DisconnectMode.cancel
            and not gap_emitted
        ):
            await run_mgr.cancel(record.run_id)


async def _terminal_record_stream_missing(
    bridge: StreamBridge, record: RunRecord
) -> bool:
    """U2: Probe whether a terminal record has an empty stream.

    If the record status is terminal (completed/failed/cancelled/interrupted) AND
    the bridge has no events for this run, return True. This prevents hanging on
    stale records where the stream was already cleaned up.

    Returns True if the record is terminal and stream is empty/missing.
    """
    if record.status not in (
        RunStatus.success,
        RunStatus.error,
        RunStatus.timeout,
        RunStatus.interrupted,
    ):
        return False

    # Check if stream exists and has events
    # For DeerFlow's RedisStreamBridge, we can check stream_exists()
    # For MemoryStreamBridge, we assume stream is gone if record is terminal
    if hasattr(bridge, "stream_exists"):
        exists = await bridge.stream_exists(record.run_id)
        return not exists

    # MemoryStreamBridge doesn't persist, so if record is terminal, stream is gone
    return True


async def _orphan_recovery_observed_after_heartbeat(record: RunRecord) -> bool:
    """U2: Check if run was terminalized by orphan recovery after heartbeat.

    After yielding a heartbeat sentinel, check if the run record has been
    terminalized by orphan recovery (status=interrupted AND stop_reason='orphan_recovered').
    If so, the SSE consumer should yield end frame and return to prevent hanging
    on heartbeat forever when the producer died and a peer reconciler has already
    marked the run terminal.

    Returns True if orphan recovery was observed.
    """
    # Check if record status is interrupted with orphan_recovered stop_reason
    # This requires checking the run record's metadata or a separate field
    # For now, we check if the record status is interrupted
    if record.status == RunStatus.interrupted:
        # Check if stop_reason is 'orphan_recovered' (if available in metadata)
        metadata = getattr(record, "metadata", {}) or {}
        stop_reason = metadata.get("stop_reason")
        if stop_reason == "orphan_recovered":
            logger.info(
                "Orphan recovery observed after heartbeat for run %s",
                record.run_id,
            )
            return True
    return False


# [Integrated with Numina Multi-Tenant] — family_id in metadata
def _app_rejected_error(*, status_code: int, app: str, reason: str) -> HTTPException:
    """Build an HTTPException rejecting a disallowed ``app`` dispatch value.

    Used by ``start_run`` to enforce the R1 allowlist before the run is created.
    """
    return HTTPException(
        status_code=status_code,
        detail=f"app='{app}' 不允许直连：{reason}",
    )


async def start_run(
    body: Any,
    thread_id: str,
    request: Request,
    family_id: str,
    user_id: str | None,
    *,
    internal: bool = False,
) -> RunRecord:
    """Create a ``RunRecord`` and launch the background family agent task.

    Args:
        body: The validated request body (RunCreateRequest or compatible duck-type).
        thread_id: Target thread ID.
        request: FastAPI request — used to retrieve singletons from ``app.state``.
        family_id: Numina family (tenant) ID.
        user_id: Optional user ID.
        internal: When True, the caller is a trusted backend service (authenticated
            via ``X-Agent-Token`` at the gateway endpoint, e.g. the asset-report
            trigger). The R1 ``app`` allowlist gate is relaxed for internal calls
            because the backend trigger endpoint already enforces owner +
            require_ai_enabled + per-family concurrency gating — R1's purpose is
            to stop *frontend* direct dispatch, not service-to-service dispatch.

    Returns:
        The created ``RunRecord`` with an attached ``asyncio.Task``.

    # [Copied from DeerFlow Reference] — app/gateway/services.py start_run
    """
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)

    # R1 security gate (P0): the ``app`` field in body.metadata controls which
    # worker dispatch branch fires (numina / asset-report / import-parse /
    # finance-coach / wish-advice). It originates from the client, so the server
    # must validate it. allowlist is intentionally narrow here and widened only
    # as each app's auth is wired:
    #   - "numina" (default): always allowed (the /ai/chat path).
    #   - "asset-report": REJECTED direct — the report pipeline must be entered
    #     via the backend trigger_generate_events endpoint, which enforces
    #     require_owner + require_ai_enabled + per-family concurrency gating.
    #     Accepting it here would bypass that gating (R1 Finding 1).
    #     SKIPPED for internal callers (backend trigger via X-Agent-Token) —
    #     those have already passed the backend's owner/concurrency gate.
    #   - "import-parse": REJECTED direct (U8) — the parse pipeline must be
    #     entered via the backend /import/parse-pdf endpoint, which enforces
    #     require_adult (owner/member) gating. SKIPPED for internal callers
    #     (backend trigger via X-Agent-Token gateway) — those have already
    #     passed the backend's auth gate (lockstep with allowlist, no window).
    #   - "finance-coach": REJECTED direct (Plan A) — the advice pipeline must
    #     be entered via the backend /ai/finance-coach/generate endpoint, which
    #     enforces require_ai_enabled + require_adult + per-family concurrency
    #     gating. SKIPPED for internal callers (backend trigger via X-Agent-Token
    #     gateway) — those have already passed the backend's auth gate.
    #   - "wish-advice": REJECTED direct (Plan B T7) — the W4 advice pipeline
    #     must be entered via the backend /ai/wish-advice/generate endpoint,
    #     which enforces require_ai_enabled + require_adult + require_owner
    #     gating. SKIPPED for internal callers (backend trigger via X-Agent-Token
    #     gateway) — those have already passed the backend's auth gate.
    #   - any other value: 400.
    body_meta = getattr(body, "metadata", None) or {}
    app = body_meta.get("app", "numina") if isinstance(body_meta, dict) else "numina"
    if not internal and app == "asset-report":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="报告生成须经由后端触发端点，请勿直连 /runs/stream",
        )
    if not internal and app == "import-parse":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="导入解析须经由后端 /import/parse-pdf 端点，请勿直连 /runs/stream",
        )
    if not internal and app == "finance-coach":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="财务教练建议须经由后端 /ai/finance-coach/generate 端点，请勿直连 /runs/stream",
        )
    if not internal and app == "wish-advice":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="心愿储蓄建议须经由后端 /ai/wish-advice/generate 端点，请勿直连 /runs/stream",
        )
    if not internal and app == "dashboard-narrative":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="财务叙事须经由后端 /dashboard/narrative 端点，请勿直连 /runs/stream",
        )
    if not internal and app == "literacy-weekly-report":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="启蒙周报须经由后端触发端点，请勿直连 /runs/stream",
        )
    if (
        app != "numina"
        and app != "asset-report"
        and app != "import-parse"
        and app != "finance-coach"
        and app != "wish-advice"
        and app != "dashboard-narrative"
        and app != "literacy-weekly-report"
    ):
        raise _app_rejected_error(status_code=400, app=app, reason="未知的 app 值")

    disconnect = (
        DisconnectMode.cancel
        if getattr(body, "on_disconnect", "cancel") == "cancel"
        else DisconnectMode.continue_
    )

    record = await run_mgr.create_or_reject(
        thread_id,
        getattr(body, "assistant_id", None),
        on_disconnect=disconnect,
        metadata={
            **(getattr(body, "metadata", None) or {}),
            "family_id": family_id,
            "user_id": user_id,
            # Normalise so worker.py can always read record.metadata["app"]
            # without re-checking body shape. Defaults to "numina".
            "app": app,
        },
        kwargs={
            "input": getattr(body, "input", None),
            "config": getattr(body, "config", None),
        },
        multitask_strategy=getattr(body, "multitask_strategy", "reject"),
    )

    task = asyncio.create_task(
        run_agent(
            bridge=bridge,
            run_manager=run_mgr,
            record=record,
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            graph_input=getattr(body, "input", None),
            config=getattr(body, "config", None) or {},
            stream_modes=normalize_stream_modes(getattr(body, "stream_mode", None)),
        )
    )
    record.task = task
    return record
