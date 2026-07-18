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

    # [Copied from DeerFlow Reference] — app/gateway/services.py sse_consumer
    """
    last_event_id = request.headers.get("Last-Event-ID")
    try:
        async for entry in bridge.subscribe(record.run_id, last_event_id=last_event_id):
            if await request.is_disconnected():
                break

            if entry is HEARTBEAT_SENTINEL:
                yield ": heartbeat\n\n"
                continue

            if entry is END_SENTINEL:
                yield format_sse("end", None, event_id=entry.id or None)
                return

            yield format_sse(entry.event, entry.data, event_id=entry.id or None)

    finally:
        # [Copied from DeerFlow Reference] — on_disconnect=cancel aborts background task
        # [Integrated with Numina Multi-Tenant] — uses record.metadata["family_id"]
        if (
            record.status in (RunStatus.pending, RunStatus.running)
            and record.on_disconnect == DisconnectMode.cancel
        ):
            await run_mgr.cancel(record.run_id)


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
    # worker dispatch branch fires (numina / asset-report / import-parse). It
    # originates from the client, so the server must validate it. allowlist is
    # intentionally narrow here and widened only as each app's auth is wired:
    #   - "numina" (default): always allowed (the /ai/chat path).
    #   - "asset-report": REJECTED direct — the report pipeline must be entered
    #     via the backend trigger_generate_events endpoint, which enforces
    #     require_owner + require_ai_enabled + per-family concurrency gating.
    #     Accepting it here would bypass that gating (R1 Finding 1).
    #     SKIPPED for internal callers (backend trigger via X-Agent-Token) —
    #     those have already passed the backend's owner/concurrency gate.
    #   - "import-parse": REJECTED until U8 wires its owner/member auth
    #     (lockstep with allowlist — no U2→U8 window where the value is
    #     accepted without /import/parse-pdf's guards).
    #   - any other value: 400.
    body_meta = getattr(body, "metadata", None) or {}
    app = body_meta.get("app", "numina") if isinstance(body_meta, dict) else "numina"
    if not internal and app == "asset-report":
        raise _app_rejected_error(
            status_code=409,
            app=app,
            reason="报告生成须经由后端触发端点，请勿直连 /runs/stream",
        )
    if app == "import-parse":
        raise _app_rejected_error(
            status_code=400,
            app=app,
            reason="import-parse 暂未启用，请使用 /import/parse-pdf",
        )
    if app != "numina" and app != "asset-report":
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
