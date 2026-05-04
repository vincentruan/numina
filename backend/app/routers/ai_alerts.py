"""AI 老化预警端点。"""

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
from app.models.ai_asset_alert import AIAssetAlert
from app.models.user import User
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/asset-alerts", tags=["ai-alerts"])
logger = logging.getLogger(__name__)


@router.get("")
def get_alerts(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    alerts = (
        db.query(AIAssetAlert)
        .filter(
            AIAssetAlert.family_id == current_user.family_id,
            AIAssetAlert.is_dismissed == False,
        )
        .order_by(AIAssetAlert.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(a.id),
            "asset_id": a.asset_id,
            "asset_name": a.asset_name,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "suggestion": a.suggestion,
            "remaining_life_days": a.remaining_life_days,
            "daily_cost": a.daily_cost,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/refresh")
async def refresh_alerts(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新预警（streaming，任务状态追踪）。"""
    # 1. 检查在途任务
    existing = AITaskService.get_running_task(current_user.family_id, "alerts", db)
    if existing:
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS, "⏳ 预警刷新中，请稍后")

    # 2. 创建 AIChatSession
    session = await ChatSessionService.create_session(
        family_id=str(current_user.family_id),
        user_id=str(current_user.id),
        db=db,
    )

    # 3. 创建 AITask
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="alerts",
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
                        f"{settings.AGENT_BASE_URL}/alerts/stream",
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
                logger.error(f"[ai_alerts] proxy_stream failed: {e}")
                if buffer:
                    await ChatSessionService.append_message(
                        session, "assistant", "".join(buffer), current_user, stream_db
                    )
                AITaskService.fail_task(task.id, "agent_stream_error", stream_db)
                raise

    return StreamingResponse(proxy_stream(), media_type="text/plain; charset=utf-8")


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    alert = db.query(AIAssetAlert).filter(
        AIAssetAlert.id == int(alert_id),
        AIAssetAlert.family_id == current_user.family_id,
    ).first()
    if not alert:
        raise AppError(ErrorCode.AI_ALERT_NOT_FOUND)
    alert.is_dismissed = True
    alert.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
