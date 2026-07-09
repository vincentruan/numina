"""AI 消费漏洞检测端点。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_spending_leak import AISpendingLeak
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import (
    check_circuit_blocked,
    proxy_capability_events,
)
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/spending-leaks", tags=["ai-spending-leaks"])
logger = logging.getLogger(__name__)


@router.get("")
def get_leaks(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leaks = (
        db.query(AISpendingLeak)
        .filter(
            AISpendingLeak.family_id == current_user.family_id,
            AISpendingLeak.is_dismissed.is_(False),
        )
        .order_by(AISpendingLeak.created_at.desc())
        .all()
    )
    return [
        {
            "id": leak.id,
            "asset_id": leak.asset_id,
            "asset_name": leak.asset_name,
            "leak_type": leak.leak_type,
            "severity": leak.severity,
            "estimated_annual_waste": leak.estimated_annual_waste,
            "suggestion": leak.suggestion,
            "created_at": leak.created_at.isoformat(),
        }
        for leak in leaks
    ]


@router.post("/refresh")
async def refresh_leaks(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新消费漏洞（streaming，任务状态追踪）。"""
    existing = AITaskService.get_running_task(
        current_user.family_id, "spending_leak", db
    )
    if existing:
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS, "⏳ 消费漏洞分析中，请稍后")

    session = await ChatSessionService.create_session(
        family_id=current_user.family_id,
        user_id=current_user.id,
        db=db,
    )
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="spending_leak",
        session_id=session.id,
        db=db,
    )

    async def proxy_stream():
        # Import SessionLocal lazily so test fixtures can patch the module-level
        # binding (see tests/backend/conftest.py).
        from apps.backend.app.database import SessionLocal as _SessionLocal

        with _SessionLocal() as stream_db:
            try:
                agent_client = AgentClient(current_user.family_id, current_user.id, timeout=None)
                async with agent_client.stream(
                    "POST",
                    "/spending-leak/stream",
                    headers={
                        "X-Task-Id": str(task.id),
                        "X-Thread-Id": str(session.id),
                    },
                ) as resp:
                    async for chunk in resp.aiter_text():
                        yield chunk.encode("utf-8")
                AITaskService.complete_task(task.id, stream_db)
            except Exception as e:
                logger.error(f"[ai_spending_leaks] proxy_stream failed: {e}")
                AITaskService.fail_task(task.id, "agent_stream_error", stream_db)
                raise

    return StreamingResponse(proxy_stream(), media_type="text/plain; charset=utf-8")


@router.post("/refresh/events")
async def refresh_leaks_events(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新消费漏洞（NDJSON 事件流）。"""
    blocked_resp = check_circuit_blocked(current_user.family_id, "spending_leak", db)
    if blocked_resp is not None:
        return blocked_resp

    # Check if there's already a running task - resume it instead of 409
    existing = AITaskService.get_running_task(
        current_user.family_id, "spending_leak", db
    )
    if existing:
        # 已有运行中任务（从排队提升）— 直接接续，不重复创建
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
                capability="spending_leak",
                session_id=session.id,
                db=db,
            )
            return JSONResponse(
                status_code=202,
                content={
                    "status": "queued",
                    "task_id": str(task.id),
                    "queue_position": task.queue_position,
                },
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            capability="spending_leak",
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/spending-leak/events",
            capability="spending_leak",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/{leak_id}/dismiss")
def dismiss_leak(
    leak_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leak = (
        db.query(AISpendingLeak)
        .filter(
            AISpendingLeak.id == int(leak_id),
            AISpendingLeak.family_id == current_user.family_id,
        )
        .first()
    )
    if not leak:
        raise AppError(ErrorCode.AI_SPENDING_LEAK_NOT_FOUND)
    leak.is_dismissed = True
    leak.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
