"""AI 处置建议端点。"""

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
from apps.backend.app.models.ai_disposal_suggestion import AIDisposalSuggestion
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import proxy_capability_events
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/disposal-suggestions", tags=["ai-disposal"])
logger = logging.getLogger(__name__)


@router.get("")
def get_disposal_suggestions(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    suggestions = (
        db.query(AIDisposalSuggestion)
        .filter(
            AIDisposalSuggestion.family_id == current_user.family_id,
            AIDisposalSuggestion.is_dismissed.is_(False),
        )
        .order_by(AIDisposalSuggestion.inefficiency_score.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "asset_id": s.asset_id,
            "asset_name": s.asset_name,
            "category_name": s.category_name,
            "inefficiency_score": s.inefficiency_score,
            "suggested_channel": s.suggested_channel,
            "estimated_resale_range": s.estimated_resale_range,
            "suggestion": s.suggestion,
            "daily_cost": s.daily_cost,
            "created_at": s.created_at.isoformat(),
        }
        for s in suggestions
    ]


@router.post("/refresh/events")
async def refresh_disposal_events(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新处置建议（NDJSON 事件流）。"""
    existing = AITaskService.get_running_task(current_user.family_id, "disposal", db)
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
                capability="disposal",
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
            capability="disposal",
            session_id=session.id,
            db=db,
        )
        session_id = session.id

    task_id = task.id
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/disposal/events",
            capability="disposal",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
        ),
        media_type="application/x-ndjson",
    )


@router.post("/{suggestion_id}/dismiss")
def dismiss_suggestion(
    suggestion_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    s = (
        db.query(AIDisposalSuggestion)
        .filter(
            AIDisposalSuggestion.id == int(suggestion_id),
            AIDisposalSuggestion.family_id == current_user.family_id,
        )
        .first()
    )
    if not s:
        raise AppError(ErrorCode.AI_SUGGESTION_NOT_FOUND)
    s.is_dismissed = True
    s.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
