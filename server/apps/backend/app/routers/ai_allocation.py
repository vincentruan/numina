"""AI 资产配置漂移端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_allocation_drift_result import AIAllocationDriftResult
from apps.backend.app.models.ai_allocation_target import AIAllocationTarget
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import proxy_capability_events
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/allocation-target", tags=["ai-allocation"])
logger = logging.getLogger(__name__)


class AllocationTargetUpdate(BaseModel):
    category_targets: dict[str, float]
    drift_threshold: float = 10.0

    @field_validator("category_targets")
    @classmethod
    def validate_targets(cls, v: dict) -> dict:
        if v:
            total = sum(v.values())
            if abs(total - 100.0) > 0.5:
                raise ValueError(f"配置目标总和必须为100%，当前为{total:.1f}%")
        return v


@router.get("")
def get_target(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    target = (
        db.query(AIAllocationTarget)
        .filter(AIAllocationTarget.family_id == current_user.family_id)
        .first()
    )
    if not target:
        return {"has_target": False}
    return {
        "has_target": True,
        "category_targets": target.category_targets,
        "drift_threshold": target.drift_threshold,
        "updated_at": target.updated_at.isoformat(),
    }


@router.put("")
def set_target(
    body: AllocationTargetUpdate,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    target = (
        db.query(AIAllocationTarget)
        .filter(AIAllocationTarget.family_id == current_user.family_id)
        .first()
    )
    if target:
        target.category_targets = body.category_targets
        target.drift_threshold = body.drift_threshold
    else:
        target = AIAllocationTarget(
            family_id=current_user.family_id,
            category_targets=body.category_targets,
            drift_threshold=body.drift_threshold,
        )
        db.add(target)
    db.commit()
    return {"ok": True}


@router.get("/check/result")
def get_drift_result(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取最近一次配置漂移分析结果（从 DB 读取）。"""
    result = (
        db.query(AIAllocationDriftResult)
        .filter(AIAllocationDriftResult.family_id == current_user.family_id)
        .order_by(AIAllocationDriftResult.generated_at.desc())
        .first()
    )
    if not result:
        return {"has_result": False}
    return {
        "has_result": True,
        "has_significant_drift": result.has_significant_drift,
        "narrative": result.narrative,
        "drifts": result.drifts_json,
        "generated_at": result.generated_at.isoformat(),
    }


@router.get("/check")
async def check_drift(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """检测当前配置与目标的漂移。"""
    target = (
        db.query(AIAllocationTarget)
        .filter(AIAllocationTarget.family_id == current_user.family_id)
        .first()
    )
    if not target or not target.category_targets:
        return {"has_target": False, "message": "尚未设置配置目标"}

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/allocation/drift",
                json={
                    "targets": target.category_targets,
                    "threshold": target.drift_threshold,
                },
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"调用 agent allocation drift 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e


@router.post("/check/events")
async def events_check_drift(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """检测当前配置与目标的漂移（NDJSON 事件流）。"""
    target = (
        db.query(AIAllocationTarget)
        .filter(AIAllocationTarget.family_id == current_user.family_id)
        .first()
    )
    if not target or not target.category_targets:
        return JSONResponse({"has_target": False, "message": "尚未设置配置目标"})

    existing = AITaskService.get_running_task(current_user.family_id, "allocation", db)
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
                capability="allocation",
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
            capability="allocation",
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = task.id
    family_id = current_user.family_id

    return StreamingResponse(
        proxy_capability_events(
            agent_path="/allocation/events",
            capability="allocation",
            task_id=task_id,
            session_id=session_id,
            family_id=family_id,
            current_user=current_user,
            db=db,
            extra_json={
                "targets": target.category_targets,
                "threshold": target.drift_threshold,
            },
        ),
        media_type="application/x-ndjson",
    )
