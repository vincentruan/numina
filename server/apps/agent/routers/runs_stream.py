"""Runs streaming endpoint — new SSE protocol with StreamBridge + RunManager.

This is the v2 streaming endpoint that uses the full StreamBridge + RunManager
lifecycle pipeline: heartbeat sentinels, client disconnect handling,
Last-Event-ID reconnection, and deferred garbage collection.

The existing ``routers/runs.py`` endpoint is kept for backward compatibility;
this file provides the new SSE protocol.

# [Copied from DeerFlow Reference] — adapted from app/gateway/routers/thread_runs.py
# [Integrated with Numina Multi-Tenant] — X-Family-Id header for tenant isolation
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from deerflow.runtime import CancelOutcome, RunManager
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.services.runtime.lifespan import get_run_manager, get_stream_bridge
from apps.agent.services.runtime.sse_gateway import sse_consumer, start_run

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["runs"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunCreateRequest(BaseModel):
    """Request body matching the LangGraph Platform runs API."""

    assistant_id: str | None = Field(
        default=None, description="Agent / assistant to use"
    )
    input: dict[str, Any] | None = Field(
        default=None, description="Graph input (e.g. {messages: [...]})"
    )
    command: dict[str, Any] | None = Field(
        default=None, description="LangGraph Command"
    )
    metadata: dict[str, Any] | None = Field(default=None, description="Run metadata")
    config: dict[str, Any] | None = Field(
        default=None, description="RunnableConfig overrides"
    )
    context: dict[str, Any] | None = Field(
        default=None, description="DeerFlow context overrides"
    )
    stream_mode: list[str] | str | None = Field(
        default=None, description="Stream mode(s)"
    )
    stream_subgraphs: bool = Field(default=False, description="Include subgraph events")
    on_disconnect: Literal["cancel", "continue"] = Field(
        default="cancel", description="Behaviour on SSE disconnect"
    )
    multitask_strategy: Literal["reject", "rollback", "interrupt", "enqueue"] = Field(
        default="reject", description="Concurrency strategy"
    )
    on_completion: Literal["delete", "keep"] = Field(
        default="keep", description="Delete temp thread on completion"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


async def disconnect_watcher(
    request: Request, record: Any, run_mgr: RunManager
):
    """Background task to actively poll for client disconnect.

    This ensures that cooperative cancellation is triggered immediately,
    even if the SSE generator is currently suspended waiting for the next event.

    U2: Respects on_disconnect mode — only cancels if record.on_disconnect == 'cancel'.
    When on_disconnect='continue', the watcher detects disconnect but does NOT cancel,
    allowing the background task to continue running (for asset-report, finance-coach, etc.).
    """
    try:
        while True:
            if await request.is_disconnected():
                # U2: Check on_disconnect mode before cancelling
                on_disconnect = getattr(record, "on_disconnect", None)
                if on_disconnect == "continue":
                    logger.info(
                        "[runs_stream] disconnect detected but on_disconnect=continue for run_id=%s, skipping cancel",
                        record.run_id,
                    )
                    break

                logger.info("[runs_stream] active disconnect detected for run_id=%s", record.run_id)
                await run_mgr.cancel(record.run_id)
                break
            await asyncio.sleep(0.5)
    except asyncio.CancelledError:
        pass


@router.post("/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    body: RunCreateRequest,
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> StreamingResponse:
    """Create a run and stream events via SSE with full lifecycle management.

    Uses ``StreamBridge`` + ``RunManager`` for:
    - Heartbeat sentinels (``: heartbeat\\n\\n`` every 15s during silence)
    - Client disconnect handling (``on_disconnect=cancel`` aborts the run)
    - ``Last-Event-ID`` reconnection (replay buffered events after reconnect)
    - Deferred garbage collection (cleanup after 60s / 300s)

    Response headers match the LangGraph Platform protocol so the ``useStream``
    React hook from ``@langchain/langgraph-sdk/react`` works without modification.

    # [Copied from DeerFlow Reference] — app/gateway/routers/thread_runs.py stream_run
    # [Integrated with Numina Multi-Tenant] — family_id in run metadata
    """
    # Use the user_id from the verified JWT, not a separate ``X-User-Id``
    # header. The frontend LangGraph SDK client (ai-chat.ts:getClient) only
    # sends ``X-Family-Id`` + cookies - it does NOT set ``X-User-Id`` - so
    # reading the header left user_id=None, which made worker.py skip
    # ``X-Caller-User-Id`` on the MCP SSE handshake, causing the backend
    # /internal/mcp/{family_id}/sse endpoint to 403 ("missing caller_user_id")
    # and load zero MCP tools (the agent then reported "所有记录仍为空").
    record = await start_run(body, thread_id, request, x_family_id, verified.user_id)
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)

    watcher_task = asyncio.create_task(disconnect_watcher(request, record, run_mgr))

    async def sse_generator():
        try:
            async for frame in sse_consumer(bridge, record, request, run_mgr):
                yield frame
        finally:
            watcher_task.cancel()

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/api/threads/{thread_id}/runs/{record.run_id}",
        },
    )


@router.post("/{thread_id}/runs/{run_id}/cancel")
async def cancel_run(
    thread_id: str,
    run_id: str,
    action: Literal["interrupt", "rollback"] = "interrupt",
    verified: VerifiedFamily = Depends(verify_family_token),
    run_mgr: RunManager = Depends(get_run_manager),
) -> dict[str, Any]:
    """Cancel an in-flight agent run.

    Implements the ``@langchain/langgraph-sdk`` ``runs.cancel`` protocol — the
    SDK sends ``POST /threads/{thread_id}/runs/{run_id}/cancel?action=interrupt&wait=0``.
    The run is cancelled via ``RunManager``; tenant isolation is enforced by
    checking the run's ``family_id`` metadata against the verified family. A
    mismatched or unknown run returns 404 so existence is not leaked.
    """
    record = await run_mgr.get(run_id)
    if (
        record is None
        or record.thread_id != thread_id
        or record.metadata.get("family_id") != verified.family_id
    ):
        raise HTTPException(status_code=404, detail="运行不存在")
    cancelled = await run_mgr.cancel(run_id, action=action)
    return {"run_id": run_id, "cancelled": cancelled is CancelOutcome.cancelled}
