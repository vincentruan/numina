"""AI 负债优化顾问端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_liability_result import AILiabilityResult
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import proxy_capability_events
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/liability-advice", tags=["ai-liability"])
logger = logging.getLogger(__name__)


@router.get("/result")
def get_liability_result(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取最近一次负债分析结果（从 DB 读取）。"""
    result = (
        db.query(AILiabilityResult)
        .filter(AILiabilityResult.family_id == current_user.family_id)
        .order_by(AILiabilityResult.generated_at.desc())
        .first()
    )
    if not result:
        return {"has_result": False}
    return {
        "has_result": True,
        "has_liabilities": result.has_liabilities,
        "total_remaining": result.total_remaining,
        "total_monthly_payment": result.total_monthly_payment,
        "liability_count": result.liability_count,
        "narrative": result.narrative,
        "recommended_strategy": result.recommended_strategy,
        "strategies": result.strategies_json,
        "generated_at": result.generated_at.isoformat(),
    }


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
                capability="liability",
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
