"""Shared helper for proxying NDJSON capability event streams from the agent."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.user import User
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

logger = logging.getLogger(__name__)


async def proxy_capability_events(
    agent_path: str,
    capability: str,
    task_id: str,
    session_id: str,
    family_id: int,
    current_user: User,
    extra_json: dict | None = None,
) -> AsyncGenerator[bytes, None]:
    """Proxy NDJSON events from the agent, persist the answer, and manage task lifecycle.

    Yields raw NDJSON lines (with trailing newline) to the caller.
    Promotes the next queued task after completion or failure.

    Args:
        agent_path: Agent endpoint path, e.g. "/alerts/events".
        capability: Capability name for task service calls.
        task_id: Running task ID (captured before generator starts).
        session_id: Chat session ID (captured before generator starts).
        family_id: Family ID (captured before generator starts).
        current_user: Authenticated user (for append_message).
        extra_json: Optional extra JSON body fields for the agent request.
    """
    with SessionLocal() as stream_db:
        answer_parts: list[str] = []
        session_obj = ChatSessionService.get_session(session_id, family_id, stream_db)
        try:
            request_json: dict = extra_json or {}
            async with (
                httpx.AsyncClient(timeout=None) as client,
                client.stream(
                    "POST",
                    f"{settings.AGENT_BASE_URL}{agent_path}",
                    json=request_json if request_json else None,
                    headers={
                        "X-Family-Id": str(family_id),
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Task-Id": task_id,
                        "X-Thread-Id": session_id,
                    },
                    timeout=None,
                ) as resp,
            ):
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    yield (line + "\n").encode("utf-8")
                    try:
                        event = json.loads(line)
                        if event.get("type") == "token.stream" and not event.get("is_thinking"):
                            answer_parts.append(event.get("token", ""))
                        elif event.get("type") == "capability.end":
                            summary = event.get("result", {}).get("summary", "")
                            if summary:
                                answer_parts.append(summary)
                    except (json.JSONDecodeError, AttributeError):
                        pass
            answer = "".join(answer_parts)
            if answer and session_obj:
                await ChatSessionService.append_message(
                    session_obj, "assistant", answer, current_user, stream_db
                )
            AITaskService.complete_task(task_id, stream_db)
            next_task = AITaskService.get_next_queued_task(family_id, stream_db)
            if next_task:
                AITaskService.promote_queued_task(next_task.id, stream_db)
        except Exception as e:
            logger.error(f"[{capability}] proxy_capability_events failed: {e}")
            AITaskService.fail_task(task_id, "agent_stream_error", stream_db)
            next_task = AITaskService.get_next_queued_task(family_id, stream_db)
            if next_task:
                AITaskService.promote_queued_task(next_task.id, stream_db)
            yield (
                json.dumps({"type": "capability.error", "message": "agent_stream_error"}) + "\n"
            ).encode("utf-8")
