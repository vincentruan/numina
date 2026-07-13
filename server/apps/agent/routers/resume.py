"""Resume endpoint for interrupted graph execution.

Accepts user answers to interrupt() prompts and resumes the graph using
LangGraph's Command(resume=...) mechanism. Returns SSE stream so the
frontend can display the agent's continued response in real-time.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _get_shared_checkpointer,
)
from apps.agent.services.runtime.lifespan import get_run_manager, get_stream_bridge
from apps.agent.services.runtime.sse_gateway import (
    format_sse,
    normalize_stream_modes,
    sse_consumer,
)
from apps.agent.services.runtime.worker import run_family_agent
from apps.agent.services.session_store import AiSessionRepository
from deerflow.runtime import DisconnectMode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["resume"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class ResumeRequest(BaseModel):
    """Request body for resuming an interrupted graph."""

    answer: str = Field(description="User's answer to the interrupt prompt")
    interrupt_id: str = Field(description="ID of the interrupt to resume")


class ResumeResponse(BaseModel):
    """Response after successfully resuming a graph."""

    thread_id: str = Field(description="Thread ID that was resumed")
    status: str = Field(default="resumed", description="Resume status")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{thread_id}/runs/resume")
async def resume_run(
    thread_id: str,
    body: ResumeRequest,
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
) -> StreamingResponse:
    """Resume an interrupted graph execution with user's answer.

    Validates thread ownership, then launches a background task to resume
    the graph using LangGraph's Command(resume=answer). Returns SSE stream
    so the frontend can display the agent's continued response.

    # [Integrated with Numina Multi-Tenant] — family_id validation
    """
    # 1. Validate thread exists and belongs to this family
    repo = AiSessionRepository(x_family_id)
    record = await repo.get_session(thread_id)

    if record is None:
        # Check if checkpoint exists (orphan thread case)
        checkpointer = _get_shared_checkpointer(None)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)

        if checkpoint_tuple is None:
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )

        # Checkpoint exists but no session row — verify family ownership
        ckpt_metadata = getattr(checkpoint_tuple, "metadata", {}) or {}
        ckpt_family_id = ckpt_metadata.get("family_id")
        if not ckpt_family_id or str(ckpt_family_id) != str(verified.family_id):
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )
    else:
        # Session row exists — verify family ownership
        record_family_id = record.get("family_id")
        if not record_family_id or str(record_family_id) != str(verified.family_id):
            raise HTTPException(
                status_code=404,
                detail=f"Thread {thread_id} not found",
            )

    # 2. Create a RunRecord and launch the background task
    bridge = get_stream_bridge(request)
    run_mgr = get_run_manager(request)

    run_record = await run_mgr.create_or_reject(
        thread_id,
        None,  # assistant_id
        on_disconnect=DisconnectMode.cancel,
        metadata={
            "family_id": x_family_id,
            "user_id": verified.user_id,
        },
        kwargs={
            "resume_answer": body.answer,
            "interrupt_id": body.interrupt_id,
        },
        multitask_strategy="reject",
    )

    task = asyncio.create_task(
        run_family_agent(
            bridge=bridge,
            run_manager=run_mgr,
            record=run_record,
            family_id=x_family_id,
            user_id=verified.user_id,
            thread_id=thread_id,
            graph_input=None,  # No new message — resuming
            config={},
            resume_answer=body.answer,
            interrupt_id=body.interrupt_id,
        )
    )
    run_record.task = task

    # 3. Stream the response via SSE
    async def disconnect_watcher(req: Request, rid: str, rm):
        """Background task to detect client disconnect."""
        try:
            while True:
                if await req.is_disconnected():
                    logger.info("[resume] disconnect detected for run_id=%s", rid)
                    await rm.cancel(rid)
                    break
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    watcher_task = asyncio.create_task(
        disconnect_watcher(request, run_record.run_id, run_mgr)
    )

    async def sse_generator():
        try:
            async for frame in sse_consumer(bridge, run_record, request, run_mgr):
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
            "Content-Location": f"/api/threads/{thread_id}/runs/{run_record.run_id}",
        },
    )
