"""AI 消费漏洞检测端点。"""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import SessionLocal, get_db
from app.errors import AppError, ErrorCode
from app.models.ai_chat_session import AIChatSession
from app.models.ai_spending_leak import AISpendingLeak
from app.models.user import User
from app.routers._ai_events_helper import proxy_capability_events
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

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
            AISpendingLeak.is_dismissed == False,  # noqa: E712
        )
        .order_by(AISpendingLeak.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(leak.id),
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
    existing = AITaskService.get_running_task(current_user.family_id, "spending_leak", db)
    if existing:
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS, "⏳ 消费漏洞分析中，请稍后")

    session = await ChatSessionService.create_session(
        family_id=str(current_user.family_id),
        user_id=str(current_user.id),
        db=db,
    )
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="spending_leak",
        session_id=session.id,
        db=db,
    )

    async def proxy_stream():
        buffer: list[str] = []
        with SessionLocal() as stream_db:
            try:
                async with (
                    httpx.AsyncClient(timeout=None) as client,
                    client.stream(
                        "POST",
                        f"{settings.AGENT_BASE_URL}/spending-leak/stream",
                        headers={
                            "X-Family-Id": str(current_user.family_id),
                            "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                            "X-Task-Id": task.id,
                            "X-Thread-Id": session.id,
                        },
                        timeout=None,
                    ) as resp,
                ):
                    async for chunk in resp.aiter_text():
                        buffer.append(chunk)
                        yield chunk.encode("utf-8")
                        if chunk.endswith(("。", "！", "？", ".", "!", "?", "\n")):
                            await ChatSessionService.append_message(
                                session, "assistant", "".join(buffer), current_user, stream_db
                            )
                            buffer.clear()
                if buffer:
                    await ChatSessionService.append_message(
                        session, "assistant", "".join(buffer), current_user, stream_db
                    )
                AITaskService.complete_task(task.id, stream_db)
            except Exception as e:
                logger.error(f"[ai_spending_leaks] proxy_stream failed: {e}")
                if buffer:
                    await ChatSessionService.append_message(
                        session, "assistant", "".join(buffer), current_user, stream_db
                    )
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
    existing = AITaskService.get_running_task(current_user.family_id, "spending_leak", db)
    if existing:
        task = existing
        session_id = task.session_id or str(task.id)
        session = db.query(AIChatSession).filter_by(id=session_id, family_id=current_user.family_id).first()
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        session = await ChatSessionService.create_session(
            family_id=str(current_user.family_id),
            user_id=str(current_user.id),
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
                content={"status": "queued", "task_id": task.id, "queue_position": task.queue_position},
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            capability="spending_leak",
            session_id=session.id,
            db=db,
        )
        session_id = session.id

    task_id = task.id
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/spending-leak/events",
            capability="spending_leak",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/{leak_id}/dismiss")
def dismiss_leak(
    leak_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leak = db.query(AISpendingLeak).filter(
        AISpendingLeak.id == int(leak_id),
        AISpendingLeak.family_id == current_user.family_id,
    ).first()
    if not leak:
        raise AppError(ErrorCode.AI_SPENDING_LEAK_NOT_FOUND)
    leak.is_dismissed = True
    leak.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
