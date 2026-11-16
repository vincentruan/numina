"""Shared SSE pipeline for agent-triggered learning streams.

Both the smart-tutor and teach-back endpoints drive the same
``learning-smart-tutor`` agent app: create an AITask, trigger the run, persist
the run id, spawn the lifecycle consumer, and wrap the bridge stream in a
``StreamingResponse``. Keeping that plumbing here means a change to it is made
once (previously it was duplicated across two endpoints in
``routers/learning_child.py``).
"""

import json

import httpx
from fastapi import Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.database import SessionLocal
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.bridge_consumer import (
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
    trigger_agent_run,
)


async def stream_learning_agent_sse(
    *,
    http_request: Request,
    db: Session,
    thread_id: str,
    agent_body: dict,
    family_id: int,
    child: User,
    learning_session_id: int,
    prepend_event: tuple[str, dict] | None = None,
) -> StreamingResponse:
    """Run the agent and return its SSE stream.

    ``thread_id`` is the agent routing key and ``agent_body`` the payload; the
    helper owns everything else. When ``prepend_event`` is given, a single
    custom SSE event carrying that type and data is emitted before the bridge
    stream, with a stable ``id:`` so a ``Last-Event-ID`` reconnect can replay it.
    """
    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="learning-smart-tutor",
        session_id=None,
        db=db,
    )
    task.progress = {"learning_session_id": str(learning_session_id)}
    db.commit()
    task_id = str(task.id)

    agent_client = AgentClient(family_id=str(family_id), user_id=str(child.id))
    try:
        result = await trigger_agent_run(
            agent_client=agent_client,
            agent_url=f"/internal/gateway/runs/learning-smart-tutor/{thread_id}",
            json_body=agent_body,
            task_id=task_id,
        )
    except httpx.HTTPStatusError as e:
        _fail_task(task_id, e)
        if e.response.status_code == 409:
            raise AppError(ErrorCode.AI_TASK_IN_PROGRESS) from e
        raise AppError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, details={"reason": str(e)}
        ) from e
    except Exception as e:
        _fail_task(task_id, e)
        raise AppError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, details={"reason": str(e)}
        ) from e

    AITaskService.extract_and_attach_run_id(
        task_id, result["content_location"], family_id
    )

    shared_bridge = get_shared_bridge()
    _spawn_lifecycle_consumer(
        task_id=task_id,
        family_id=family_id,
        run_id=result["run_id"],
        bridge=shared_bridge,
    )

    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=http_request.headers.get("Last-Event-ID"),
        run_id=result["run_id"],
        bridge=shared_bridge,
    )

    if prepend_event is None:
        return _sse_response(stream_gen)

    event_type, event_data = prepend_event
    event_id = f"{event_type}-{learning_session_id}"

    async def _with_prepend():
        yield (
            f"id: {event_id}\n"
            f"event: {event_type}\n"
            f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        )
        async for chunk in stream_gen:
            yield chunk

    return _sse_response(_with_prepend())


def _fail_task(task_id: str, error: Exception) -> None:
    """Mark the AITask failed on a trigger error, on its own session."""
    _fdb = SessionLocal()
    try:
        AITaskService.fail_task(
            task_id, f"agent trigger failed: {type(error).__name__}", _fdb
        )
    finally:
        _fdb.close()


def _sse_response(stream) -> StreamingResponse:
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
