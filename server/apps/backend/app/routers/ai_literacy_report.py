"""Literacy weekly report trigger endpoints.

POST /api/v1/ai/literacy-report/generate         — synchronous (legacy, scheduler)
POST /api/v1/ai/literacy-report/generate/events  — SSE streaming (U14 bridge consumer)
"""
import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_task_service import (
    AITaskService,
    extract_run_id_from_content_location,
)
from apps.backend.app.services.bridge_consumer import consume_task_stream
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.literacy_report import _sunday_of
from apps.backend.app.services.literacy_report_service import (
    _make_thread_id,
    _persist_report_result,
    _validate_child_in_family,
    generate_literacy_report,
    get_report_status,
)
from packages.core.roles import UserRole

router = APIRouter(prefix="/ai/literacy-report", tags=["ai-literacy-report"])
logger = logging.getLogger(__name__)

# skill_id for AITask tracking (matches VALID_SKILL_IDS in ai_tasks.py)
SKILL_ID = "literacy"


@router.post("/generate")
async def trigger_generate(
    child_id: str = Query(..., description="Child user ID"),
    force: bool = Query(False),
    current_user: User = Depends(require_adult),
    _ai: User = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """Generate (or return cached) weekly literacy report for a child."""
    try:
        cid = int(child_id)
    except (ValueError, TypeError):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=f"无效的 child_id: {child_id}",
        ) from None

    child = (
        db.query(User)
        .filter(
            User.id == cid,
            User.family_id == current_user.family_id,
            User.role == UserRole.CHILD,
        )
        .first()
    )
    if child is None:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    week_start = _sunday_of(date.today())

    if not force:
        status = get_report_status(db, family_id=current_user.family_id, child_id=cid)
        if status["status"] == "ready":
            return status

    report = await generate_literacy_report(
        db,
        family_id=current_user.family_id,
        child_id=cid,
        week_start=week_start,
        user_id=current_user.id,
        force=force,
    )

    if report is None:
        return {
            "status": "error",
            "thread_id": None,
            "week_start": week_start.isoformat(),
            "narrative": None,
            "generated_at": None,
        }

    return {
        "status": "ready",
        "thread_id": report.thread_id,
        "week_start": report.week_start.isoformat(),
        "narrative": report.narrative[:100] if report.narrative else None,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
    }


# ---------------------------------------------------------------------------
# SSE streaming endpoint (frontend)
# ---------------------------------------------------------------------------


def _validate_child(
    db: Session, *, child_id_str: str, family_id: int
) -> int:
    """Parse and validate child_id belongs to family. Returns int child_id."""
    try:
        cid = int(child_id_str)
    except (ValueError, TypeError):
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            details=f"无效的 child_id: {child_id_str}",
        ) from None

    _validate_child_in_family(db, child_id=cid, family_id=family_id)
    return cid


async def _sse_stream_with_persist(
    stream_gen: AsyncIterator[str],
    *,
    child_id: int,
    week_start: date,
    thread_id: str,
) -> AsyncGenerator[bytes, None]:
    """Wrap bridge_consumer output, persisting literacy_weekly_report.result."""
    collected = b""
    async for sse_text in stream_gen:
        collected += sse_text.encode("utf-8")
        yield sse_text.encode("utf-8")

    # After stream ends, persist the report from collected SSE bytes (best-effort)
    try:
        from apps.backend.app.database import SessionLocal

        _db = SessionLocal()
        try:
            _persist_report_result(
                _db,
                child_id=child_id,
                week_start=week_start,
                thread_id=thread_id,
                collected_sse=collected,
            )
            _db.commit()
        finally:
            _db.close()
    except Exception:
        logger.warning(
            "[literacy-report] persist failed child=%s",
            child_id,
            exc_info=True,
        )


@router.post("/generate/events")
async def trigger_generate_events(
    request: Request,
    child_id: str = Query(..., description="Child user ID"),
    force: bool = Query(False),
    current_user: User = Depends(require_adult),
    _ai: User = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """Trigger literacy report generation with AITask-tracked SSE streaming (U14).

    Cache hit → JSON ``{status: 'ready'}``.
    Cache miss / force → AITask tracking + bridge consumer SSE.
    """
    cid = _validate_child(
        db, child_id_str=child_id, family_id=current_user.family_id
    )

    week_start = _sunday_of(date.today())

    # Cache hit → return JSON (non-streaming)
    if not force:
        status = get_report_status(
            db, family_id=current_user.family_id, child_id=cid
        )
        if status["status"] == "ready":
            return status

    # Check if there's already a running task - resume it
    existing = AITaskService.get_running_task(current_user.family_id, SKILL_ID, db)
    if existing:
        task = existing
        session_id = str(task.session_id) if task.session_id else str(task.id)
        session = (
            db.query(AIChatSession)
            .filter_by(id=session_id, family_id=current_user.family_id)
            .first()
        )
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # No running task - create new session and task
        session = await ChatSessionService.create_session(
            family_id=current_user.family_id,
            user_id=current_user.id,
            db=db,
        )
        any_running = AITaskService.get_any_running_task(current_user.family_id, db)
        if any_running:
            task = AITaskService.create_queued_task(
                family_id=current_user.family_id,
                skill_id=SKILL_ID,
                session_id=session.id,
                db=db,
            )
            return JSONResponse(
                status_code=202,
                content={
                    "status": "queued",
                    "task_id": task.id,
                    "queue_position": task.queue_position,
                },
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            skill_id=SKILL_ID,
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id
    user_id = str(current_user.id)
    thread_id = _make_thread_id(family_id, cid)

    trigger = (
        f"/literacy-weekly-report 请为孩子 {cid} 生成"
        f" {week_start.isoformat()} 起始周的周报"
    )

    # Trigger agent via non-streaming POST (bridge consumer pattern)
    agent_client = AgentClient(family_id=family_id, user_id=user_id, timeout=120.0)
    agent_url = f"/internal/gateway/runs/literacy-weekly-report/{session_id}"

    try:
        resp = await agent_client.post(
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": user_id,
                "language": current_user.language,
                "on_disconnect": "continue",
                "task_id": task_id,
                "input": {"messages": [{"role": "user", "content": trigger}]},
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "[literacy-report] agent trigger failed: status=%s body=%s task=%s",
                resp.status_code,
                resp.text[:200],
                task_id,
            )
            from apps.backend.app.database import SessionLocal

            _db = SessionLocal()
            try:
                AITaskService.fail_task(task_id, "报告生成服务异常", _db)
            finally:
                _db.close()
            err = json.dumps({"message": "报告生成服务异常", "name": "AgentError"}).encode()
            return StreamingResponse(
                iter([f"event: error\ndata: {err.decode()}\n\n".encode()]),
                media_type="text/event-stream",
            )

        # Extract agent run_id from Content-Location header and persist to AITask
        run_id = extract_run_id_from_content_location(resp.headers.get("Content-Location"))
        if run_id:
            from apps.backend.app.database import SessionLocal

            _db = SessionLocal()
            try:
                AITaskService.attach_run_id(task_id, run_id, family_id, _db)
            except Exception:
                logger.warning("[literacy-report] attach_run_id failed task=%s", task_id, exc_info=True)
            finally:
                _db.close()
    except Exception as exc:
        logger.warning(
            "[literacy-report] agent trigger failed task=%s err=%s", task_id, exc
        )
        from apps.backend.app.database import SessionLocal

        _db = SessionLocal()
        try:
            AITaskService.fail_task(task_id, f"报告生成服务中断: {type(exc).__name__}", _db)
        finally:
            _db.close()
        err = json.dumps({"message": "报告生成服务中断", "name": type(exc).__name__}).encode()
        return StreamingResponse(
            iter([f"event: error\ndata: {err.decode()}\n\n".encode()]),
            media_type="text/event-stream",
        )

    # Subscribe to Redis stream via bridge_consumer
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
    )

    return StreamingResponse(
        _sse_stream_with_persist(
            stream_gen,
            child_id=cid,
            week_start=week_start,
            thread_id=thread_id,
        ),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
