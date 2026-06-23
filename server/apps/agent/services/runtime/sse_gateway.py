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
from fastapi import Request

from .lifespan import get_run_manager, get_stream_bridge
from .worker import run_family_agent

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
async def start_run(
    body: Any,
    thread_id: str,
    request: Request,
    family_id: str,
    user_id: str | None,
) -> RunRecord:
    """Create a ``RunRecord`` and launch the background family agent task.

    Args:
        body: The validated request body (RunCreateRequest or compatible duck-type).
        thread_id: Target thread ID.
        request: FastAPI request — used to retrieve singletons from ``app.state``.
        family_id: Numina family (tenant) ID.
        user_id: Optional user ID.

    Returns:
        The created ``RunRecord`` with an attached ``asyncio.Task``.

    # [Copied from DeerFlow Reference] — app/gateway/services.py start_run
    """
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)

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
        },
        kwargs={
            "input": getattr(body, "input", None),
            "config": getattr(body, "config", None),
        },
        multitask_strategy=getattr(body, "multitask_strategy", "reject"),
        user_id=user_id,
    )

    task = asyncio.create_task(
        run_family_agent(
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
