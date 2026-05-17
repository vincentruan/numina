"""Shared helper for proxying NDJSON capability event streams from the agent."""

import json
import logging
from collections.abc import AsyncGenerator

import httpx
from sqlalchemy.orm import Session

from apps.backend.app.config import settings
from apps.backend.app.models.user import User
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

logger = logging.getLogger(__name__)


async def proxy_capability_events(
    agent_path: str,
    capability: str,
    task_id: str,
    session_id: str,
    family_id: int,
    current_user: User,
    db: Session,
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
        db: Database session from the request context (used for initial query only).
        extra_json: Optional extra JSON body fields for the agent request.
    """
    # Capture session_id and user_id before streaming (don't use detached session_obj)
    user_id = current_user.id

    # Import SessionLocal inside generator to respect test overrides
    # (Test fixtures override SessionLocal after module imports are cached)
    from apps.backend.app.database import SessionLocal

    # Create a NEW db session for the generator (will be closed when generator ends)
    # This avoids using the request's db session after FastAPI closes it
    gen_db = SessionLocal()

    answer_parts: list[str] = []
    try:
        request_json: dict = extra_json or {}
        async with (
            httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)) as client,
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

        # Success path - use generator's own db session
        answer = "".join(answer_parts)
        if answer:
            # Fetch session in generator's db (fresh query, not detached instance)
            session_obj = ChatSessionService.get_session(session_id, family_id, gen_db)
            if session_obj:
                # Fetch user in generator's db
                user = gen_db.query(User).filter(User.id == user_id).first()
                if user:
                    await ChatSessionService.append_message(
                        session_obj, "assistant", answer, user, gen_db
                    )
        # Task completion semantics:
        # Task is marked complete BEFORE result persistence. This is intentional:
        # "completed" means "agent stream finished successfully" not "results persisted".
        # If persistence fails, user can still view the text answer in session history.
        # The writer's rollback ensures no partial/corrupted data remains in DB.
        AITaskService.complete_task(task_id, gen_db)

        # Extract structured results from answer and persist to DB
        # This is a best-effort operation — failure is logged but not fatal
        from apps.backend.app.services.ai_result_parser import parse_capability_result
        from apps.backend.app.services.ai_result_writer import write_capability_results

        try:
            results = parse_capability_result(capability, answer, family_id, gen_db)
            if results:
                write_capability_results(capability, family_id, results, gen_db)
        except Exception as result_error:
            logger.error(
                f"[{capability}] failed to parse/write results for family {family_id}: {result_error}"
            )
            # Result persistence failed, but task completed successfully
            # The writer's rollback handles DB cleanup; log and continue

        next_task = AITaskService.get_next_queued_task(family_id, gen_db)
        if next_task:
            AITaskService.promote_queued_task(next_task.id, gen_db)
    except Exception as e:
        logger.error(f"[{capability}] proxy_capability_events failed: {e}")
        # Error path - use generator's own db session
        AITaskService.fail_task(task_id, "agent_stream_error", gen_db)
        next_task = AITaskService.get_next_queued_task(family_id, gen_db)
        if next_task:
            AITaskService.promote_queued_task(next_task.id, gen_db)
        yield (
            json.dumps({"type": "capability.error", "message": "agent_stream_error"}) + "\n"
        ).encode("utf-8")
    finally:
        # ALWAYS close the generator's db session
        gen_db.close()
