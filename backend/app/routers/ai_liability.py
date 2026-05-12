"""AI 负债优化顾问端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_chat_session import AIChatSession
from app.models.user import User
from app.routers._ai_events_helper import proxy_capability_events
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/liability-advice", tags=["ai-liability"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_liability_advice(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
):
    """获取负债优化建议（实时调用 agent）。"""
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/liability/analyze",
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException as e:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT) from e
    except Exception as e:
        logger.error(f"调用 agent liability 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e


@router.post("/events")
async def events_liability_advice(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """获取负债优化建议（NDJSON 事件流）。"""
    existing = AITaskService.get_running_task(current_user.family_id, "liability", db)
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
                capability="liability",
                session_id=session.id,
                db=db,
            )
            return JSONResponse(
                status_code=202,
                content={"status": "queued", "task_id": task.id, "queue_position": task.queue_position},
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            capability="liability",
            session_id=session.id,
            db=db,
        )
        session_id = session.id

    task_id = task.id
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/liability/events",
            capability="liability",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
        ),
        media_type="application/x-ndjson",
    )
