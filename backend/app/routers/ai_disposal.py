"""AI 处置建议端点。"""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import SessionLocal, get_db
from app.errors import AppError, ErrorCode
from app.models.ai_disposal_suggestion import AIDisposalSuggestion
from app.models.user import User
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

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
            AIDisposalSuggestion.is_dismissed == False,
        )
        .order_by(AIDisposalSuggestion.inefficiency_score.desc())
        .all()
    )
    return [
        {
            "id": str(s.id),
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


@router.post("/refresh")
async def refresh_disposal_suggestions(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新处置建议（streaming，任务状态追踪）。"""
    # 1. 检查在途任务
    existing = AITaskService.get_running_task(current_user.family_id, "disposal", db)
    if existing:
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS, "⏳ 处置建议生成中，请稍后")

    # 2. 创建 AIChatSession
    session = await ChatSessionService.create_session(
        family_id=str(current_user.family_id),
        user_id=str(current_user.id),
        db=db,
    )

    # 3. 创建 AITask
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="disposal",
        session_id=session.id,
        db=db,
    )

    # 4. 透传 agent streaming
    async def proxy_stream():
        buffer: list[str] = []
        with SessionLocal() as stream_db:
            try:
                async with (
                    httpx.AsyncClient(timeout=None) as client,
                    client.stream(
                        "POST",
                        f"{settings.AGENT_BASE_URL}/disposal/stream",
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
                logger.error(f"[ai_disposal] proxy_stream failed: {e}")
                if buffer:
                    await ChatSessionService.append_message(
                        session, "assistant", "".join(buffer), current_user, stream_db
                    )
                AITaskService.fail_task(task.id, "agent_stream_error", stream_db)
                raise

    return StreamingResponse(proxy_stream(), media_type="text/plain; charset=utf-8")


@router.post("/{suggestion_id}/dismiss")
def dismiss_suggestion(
    suggestion_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    s = db.query(AIDisposalSuggestion).filter(
        AIDisposalSuggestion.id == int(suggestion_id),
        AIDisposalSuggestion.family_id == current_user.family_id,
    ).first()
    if not s:
        raise AppError(ErrorCode.AI_SUGGESTION_NOT_FOUND)
    s.is_dismissed = True
    s.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
