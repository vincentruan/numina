"""Literacy weekly report trigger endpoints.

POST /api/v1/ai/literacy-report/generate         — synchronous (legacy, scheduler)
POST /api/v1/ai/literacy-report/generate/events  — SSE streaming (frontend)
"""
import json
import logging
from collections.abc import AsyncGenerator
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
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


async def _proxy_agent_stream(
    *,
    family_id: int,
    user_id: int,
    child_id: int,
    week_start: date,
    thread_id: str,
    db: Session,
) -> AsyncGenerator[bytes, None]:
    """Proxy the agent's SSE stream to the frontend, then persist the result.

    After the stream completes, parse the ``literacy_weekly_report.result``
    custom event and persist a ``LiteracyWeeklyReport`` row.
    """
    agent_client = AgentClient(family_id=family_id, user_id=user_id, timeout=120.0)
    agent_url = f"/internal/gateway/runs/literacy-weekly-report/{thread_id}"

    trigger = (
        f"/literacy-weekly-report 请为孩子 {child_id} 生成"
        f" {week_start.isoformat()} 起始周的周报"
    )

    collected = b""

    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": str(user_id),
                "input": {"messages": [{"role": "user", "content": trigger}]},
            },
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[literacy-report-sse] agent non-200: status=%s body=%s",
                    resp.status_code,
                    body[:200],
                )
                err = json.dumps(
                    {"message": "报告生成服务异常", "name": "AgentError"}
                ).encode()
                yield f"event: error\ndata: {err.decode()}\n\n".encode()
                return

            async for line in resp.aiter_lines():
                chunk = (line + "\n").encode()
                collected += chunk + b"\n"
                yield chunk

    except Exception as exc:
        logger.warning(
            "[literacy-report-sse] stream failed child=%s err=%s",
            child_id,
            exc,
        )
        err = json.dumps(
            {"message": "报告生成服务中断", "name": type(exc).__name__}
        ).encode()
        yield f"event: error\ndata: {err.decode()}\n\n".encode()
        return

    # Persist the report from the captured SSE bytes (best-effort)
    try:
        _persist_report_result(
            db,
            child_id=child_id,
            week_start=week_start,
            thread_id=thread_id,
            collected_sse=collected,
        )
    except Exception:
        logger.warning(
            "[literacy-report-sse] persist failed child=%s",
            child_id,
            exc_info=True,
        )


@router.post("/generate/events")
async def trigger_generate_events(
    child_id: str = Query(..., description="Child user ID"),
    force: bool = Query(False),
    current_user: User = Depends(require_adult),
    _ai: User = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """Trigger literacy report generation with SSE streaming.

    Cache hit (``force=false`` + report exists): returns JSON ``{status: 'ready'}``.
    Cache miss / ``force=true``: proxies the agent SSE stream to the frontend
    so the report text appears incrementally.  After the stream completes,
    persists the ``LiteracyWeeklyReport`` row.
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

    # Cache miss / force → stream from agent
    thread_id = _make_thread_id(current_user.family_id, cid)

    return StreamingResponse(
        _proxy_agent_stream(
            family_id=current_user.family_id,
            user_id=current_user.id,
            child_id=cid,
            week_start=week_start,
            thread_id=thread_id,
            db=db,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
