"""AI 老化预警端点。"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_asset_alert import AIAssetAlert
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import proxy_capability_events
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

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
            AIAssetAlert.is_dismissed.is_(False),
        )
        .order_by(AIAssetAlert.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
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


@router.post("/refresh/events")
async def refresh_alerts_events(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新预警（NDJSON 事件流）。
    若家庭已有其他 capability 运行，则排队等待（返回 202 + queued task）。
    若同 capability 已在运行（从排队提升），则接续该任务启动 agent 流。
    """
    # 1. 检查同 capability 是否已在运行（可能是从排队提升的）
    existing = AITaskService.get_running_task(current_user.family_id, "alerts", db)
    if existing:
        # 已有运行中任务（从排队提升）— 返回 409
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS)

    # 2. 创建 AIChatSession
    session = await ChatSessionService.create_session(
        family_id=current_user.family_id,
        user_id=current_user.id,
        db=db,
    )

    # 3. 检查家庭是否有其他 capability 在运行 → 排队
    any_running = AITaskService.get_any_running_task(current_user.family_id, db)
    if any_running:
        task = AITaskService.create_queued_task(
            family_id=current_user.family_id,
            capability="alerts",
            session_id=session.id,
            db=db,
        )
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=202,
            content={
                "status": "queued",
                "task_id": task.id,
                "queue_position": task.queue_position,
            },
        )

    # 4. 创建 AITask
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="alerts",
        session_id=session.id,
        db=db,
    )
    session_id = session.id

    task_id = task.id
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/alerts/events",
            capability="alerts",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
        ),
        media_type="application/x-ndjson",
    )


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

