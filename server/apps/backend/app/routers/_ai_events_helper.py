"""Shared helper for proxying NDJSON capability event streams from the agent."""

import json
import logging
from collections.abc import AsyncGenerator

from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_extraction_circuit_service import (
    AIExtractionCircuitService,
)
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.utils.snowflake import next_id

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

    Task state machine (R1):
      running → [stream ends] → post_processing → [parse+write success] → completed
                                                 → [parse+write fail]    → failed + capability.error
    """
    user_id = current_user.id

    from apps.backend.app.database import SessionLocal

    gen_db = SessionLocal()

    answer_parts: list[str] = []
    try:
        request_json: dict = extra_json or {}
        agent_client = AgentClient(family_id, user_id)
        async with agent_client.stream(
            "POST",
            agent_path,
            json=request_json if request_json else None,
            headers={
                "X-Task-Id": str(task_id),
                "X-Thread-Id": str(session_id),
            },
        ) as resp:
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

        # Stream ended — enter post_processing (R1.1)
        AITaskService.mark_post_processing(task_id, gen_db)

        answer = "".join(answer_parts)

        # Parse + write structured results (R1.2)
        from apps.backend.app.services.ai_result_parser import parse_capability_result
        from apps.backend.app.services.ai_result_writer import write_capability_results

        data, method, extraction_error_type = await parse_capability_result(capability, answer, family_id, gen_db)

        # Write audit record (R2.4 / R5.1)
        _write_audit(
            gen_db,
            family_id=family_id,
            capability=capability,
            task_id=task_id,
            method=method,
            error_msg=None if data is not None else extraction_error_type or "extraction_failed",
            answer_excerpt=answer[:500] if answer else None,
        )

        if data is not None:
            try:
                write_capability_results(capability, family_id, data, gen_db)
            except Exception as write_err:
                logger.error(
                    f"[{capability}] write_capability_results failed for family {family_id}: {write_err}"
                )
                AITaskService.fail_task(task_id, "structured_write_failed", gen_db)
                yield _error_event("structured_write_failed")
                # Evaluate circuit after failure
                AIExtractionCircuitService.evaluate(family_id, capability, gen_db)
                _promote_next(family_id, gen_db)
                return

            # All good → completed (R1.2)
            AITaskService.complete_task(task_id, gen_db)
        else:
            # Extraction failed (regex + fallback both missed)
            logger.error(
                f"[{capability}] structured extraction failed for family {family_id}, "
                f"method={method}, error_type={extraction_error_type}, answer[:200]={answer[:200] if answer else ''}"
            )
            AITaskService.fail_task(task_id, extraction_error_type or "structured_extraction_failed", gen_db)
            # Evaluate circuit breaker (may transition to rate_limited/circuit_open)
            AIExtractionCircuitService.evaluate(family_id, capability, gen_db)
            yield _error_event(extraction_error_type or "extraction_failed")

        _promote_next(family_id, gen_db)
    except Exception as e:
        logger.error(f"[{capability}] proxy_capability_events failed: {e}")
        AITaskService.fail_task(task_id, "agent_stream_error", gen_db)
        _promote_next(family_id, gen_db)
        yield _error_event("agent_stream_error")
    finally:
        gen_db.close()


def _promote_next(family_id: int, db: Session) -> None:
    next_task = AITaskService.get_next_queued_task(family_id, db)
    if next_task:
        AITaskService.promote_queued_task(next_task.id, db)


def _error_event(code: str, message: str | None = None) -> bytes:
    """Create a capability.error NDJSON event with specific message."""
    message_map = {
        "extraction_failed": "分析已完成，但结构化数据提取失败",
        "structured_write_failed": "分析已完成，但结果保存失败",
        "agent_stream_error": "智能体响应中断",
        "post_processing_timeout": "处理超时，请稍后重试",
        "quota_exceeded": "AI服务配额已耗尽，请检查API额度或稍后重试",
        "llm_fallback_failed": "分析已完成，但结构化数据提取失败",
    }
    final_message = message or message_map.get(code, code)
    return (
        json.dumps({
            "type": "capability.error",
            "code": code,
            "message": final_message,
        }) + "\n"
    ).encode("utf-8")


def _write_audit(
    db: Session,
    family_id: int,
    capability: str,
    task_id: str,
    method: str,
    error_msg: str | None,
    answer_excerpt: str | None,
) -> None:
    """Best-effort audit write — never raises."""
    try:
        audit = AIExtractionAudit(
            id=next_id(),
            family_id=family_id,
            capability=capability,
            task_id=task_id,
            method=method,
            error_msg=error_msg,
            answer_excerpt=answer_excerpt,
        )
        db.add(audit)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"[{capability}] audit write failed: {e}")


def check_circuit_blocked(family_id: int, capability: str, db: Session) -> StreamingResponse | None:
    """Check if the circuit breaker blocks this capability for the family.

    Returns a StreamingResponse with a single capability.error NDJSON line if blocked,
    or None if the request should proceed normally.
    """
    blocked, reason = AIExtractionCircuitService.is_open(family_id, capability, db)
    if not blocked:
        return None

    async def _blocked_stream():
        yield _error_event(f"circuit_blocked:{reason}", message="服务暂时不可用，请稍后重试")

    return StreamingResponse(
        _blocked_stream(),
        media_type="application/x-ndjson",
    )


async def proxy_agent_first_events(
    agent_id: int,
    capability: str,
    trigger_message: str,
    task_id: str,
    session_id: str,
    family_id: int,
    current_user: User,
    db: Session,
) -> AsyncGenerator[bytes, None]:
    """Proxy NDJSON events from the agent-first path (/agent/{agent_id}/stream).

    This is the agent-first dispatch path that activates per-agent skill scoping.
    After the stream ends, it parses structured results and persists them,
    following the same task lifecycle as proxy_capability_events.

    Args:
        agent_id: The system/builtin/custom agent ID to dispatch to.
        capability: The capability name for structured extraction (e.g. "report").
        trigger_message: The message that triggers the skill (e.g. "生成资产报告").
        task_id: The AITask ID for status tracking.
        session_id: The ChatSession ID.
        family_id: The family ID.
        current_user: The requesting user.
        db: Database session.
    """
    user_id = current_user.id

    from apps.backend.app.database import SessionLocal

    gen_db = SessionLocal()

    answer_parts: list[str] = []
    try:
        request_body = {
            "message": trigger_message,
            "thread_id": str(session_id),
            "enable_thinking": False,
            "web_search": False,
            "reasoning_effort": "medium",
        }
        agent_client = AgentClient(family_id, user_id)
        async with agent_client.stream(
            "POST",
            f"/agent/{agent_id}/stream",
            json=request_body,
            headers={
                "X-Task-Id": str(task_id),
                "X-Thread-Id": str(session_id),
            },
        ) as resp:
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

        # Stream ended — enter post_processing (R1.1)
        AITaskService.mark_post_processing(task_id, gen_db)

        answer = "".join(answer_parts)

        # Parse + write structured results (R1.2)
        from apps.backend.app.services.ai_result_parser import parse_capability_result
        from apps.backend.app.services.ai_result_writer import write_capability_results

        data, method, extraction_error_type = await parse_capability_result(capability, answer, family_id, gen_db)

        # Write audit record (R2.4 / R5.1)
        _write_audit(
            gen_db,
            family_id=family_id,
            capability=capability,
            task_id=task_id,
            method=method,
            error_msg=None if data is not None else extraction_error_type or "extraction_failed",
            answer_excerpt=answer[:500] if answer else None,
        )

        if data is not None:
            try:
                write_capability_results(capability, family_id, data, gen_db)
            except Exception as write_err:
                logger.error(
                    f"[{capability}] write_capability_results failed for family {family_id}: {write_err}"
                )
                AITaskService.fail_task(task_id, "structured_write_failed", gen_db)
                yield _error_event("structured_write_failed")
                AIExtractionCircuitService.evaluate(family_id, capability, gen_db)
                _promote_next(family_id, gen_db)
                return

            # All good → completed (R1.2)
            AITaskService.complete_task(task_id, gen_db)
        else:
            # Extraction failed (regex + fallback both missed)
            logger.error(
                f"[{capability}] structured extraction failed for family {family_id}, "
                f"method={method}, error_type={extraction_error_type}, answer[:200]={answer[:200] if answer else ''}"
            )
            AITaskService.fail_task(task_id, extraction_error_type or "structured_extraction_failed", gen_db)
            AIExtractionCircuitService.evaluate(family_id, capability, gen_db)
            yield _error_event(extraction_error_type or "extraction_failed")

        _promote_next(family_id, gen_db)
    except Exception as e:
        logger.error(f"[{capability}] proxy_agent_first_events failed: {e}")
        AITaskService.fail_task(task_id, "agent_stream_error", gen_db)
        _promote_next(family_id, gen_db)
        yield _error_event("agent_stream_error")
    finally:
        gen_db.close()


async def _call_agent_skill(
    skill_name: str,
    family_id: int,
    task_id: str,
    session_id: str,
    user_id: int,
    extra_context: dict | None = None,
) -> AsyncGenerator[bytes, None]:
    """Call an agent skill and yield NDJSON events.

    Internal helper for proxy_report_events phase dispatch.
    Maps skill_name to the correct agent endpoint.
    """
    # Map skill names to agent endpoints
    endpoint_map = {
        "report_generate": "/report/generate/events",
        "report_structured": "/report/structured/events",
    }
    endpoint = endpoint_map.get(skill_name)
    if not endpoint:
        raise ValueError(f"Unknown skill: {skill_name}")

    headers = {
        "X-Task-Id": str(task_id),
        "X-Thread-Id": str(session_id),
    }

    # Pass markdown path via header for Phase 2
    if extra_context and extra_context.get("markdown_file_path"):
        headers["X-Markdown-Path"] = extra_context["markdown_file_path"]

    agent_client = AgentClient(family_id, user_id)
    async with agent_client.stream(
        "POST",
        endpoint,
        headers=headers,
    ) as resp:
        async for line in resp.aiter_lines():
            if line:
                yield (line + "\n").encode("utf-8")
