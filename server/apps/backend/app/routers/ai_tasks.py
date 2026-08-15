"""AI 任务状态查询端点。

- GET /ai/tasks                      - 查询任务列表（U6 useTaskResume）
- GET /ai/tasks/running              - 查询运行中任务（U6 便捷端点）
- GET /ai/tasks/{skill_id}           - 查询当前 skill_id 的任务状态（向后兼容）
- GET /ai/tasks/{skill_id}/session   - 获取关联的 session_id（向后兼容）
- POST /ai/tasks/{skill_id}/cancel   - 终止当前运行的任务（向后兼容）
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.services.ai_task_service import AITaskService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/tasks", tags=["ai-tasks"])

VALID_SKILL_IDS = {
    "report",
    "alerts",
    "disposal",
    "allocation",
    "spending_leak",
    "liability",
    "time_machine",
}

# Default limit for list endpoints - prevents unbounded queries (P2 fix)
DEFAULT_TASK_LIMIT = 50


class AITaskResponse(SnowflakeBase):
    """AITask response schema with Snowflake ID serialization."""

    id: int
    family_id: int
    skill_id: str
    status: str
    run_id: str | None = None
    worker_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[AITaskResponse])
async def get_tasks(
    skill_id: str | None = Query(None, description="Filter by skill_id"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(DEFAULT_TASK_LIMIT, ge=1, le=200, description="Max results"),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[AITaskResponse]:
    """Query AI tasks for the current family.

    Used by frontend useTaskResume hook to check for running tasks on page load.
    Returns tasks filtered by skill_id and/or status, scoped to the user's family.

    Example: GET /api/v1/ai/tasks?skill_id=report&status=running
    """
    from packages.db.models.ai_task import AITask

    query = db.query(AITask).filter(AITask.family_id == current_user.family_id)

    if skill_id:
        query = query.filter(AITask.skill_id == skill_id)

    if status:
        query = query.filter(AITask.status == status)

    # Order by started_at descending (most recent first), bounded by limit
    query = query.order_by(AITask.started_at.desc()).limit(limit)

    tasks = query.all()
    return [AITaskResponse.model_validate(task) for task in tasks]


@router.get("/running", response_model=list[AITaskResponse])
async def get_running_tasks(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[AITaskResponse]:
    """Get all running tasks for the current family.

    Convenience endpoint for frontend task resume. Returns all running tasks
    (excludes timed-out tasks).
    """
    tasks = AITaskService.get_running_tasks_by_family(current_user.family_id, db)
    return [AITaskResponse.model_validate(task) for task in tasks]


@router.get("/{skill_id}")
def get_task_status(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """查询当前 skill_id 的任务状态（含排队状态）。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"status": "idle"}

    # Check running task for this skill_id
    task = AITaskService.get_running_task(current_user.family_id, skill_id, db)
    if task is not None:
        return {
            "status": task.status,
            "task_id": task.id,
            "session_id": task.session_id,
            "started_at": task.started_at.isoformat() + "+00:00",
            "queue_position": None,
        }

    # Check queued task for this skill_id (position computed dynamically)
    queued = AITaskService.get_queued_task(current_user.family_id, skill_id, db)
    if queued is not None:
        return {
            "status": "queued",
            "task_id": queued.id,
            "session_id": queued.session_id,
            "started_at": queued.started_at.isoformat() + "+00:00",
            "queue_position": queued.queue_position,
        }

    return {"status": "idle"}


@router.get("/{skill_id}/session")
def get_task_session(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取当前 running 任务关联的 session_id（用于前端接续历史消息）。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"session_id": None}

    task = AITaskService.get_running_task(current_user.family_id, skill_id, db)
    if task is None:
        return {"session_id": None}

    return {"session_id": task.session_id, "task_id": task.id}


@router.post("/{skill_id}/cancel")
def cancel_task(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """终止当前运行或排队的任务。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"ok": False, "message": "invalid_skill_id"}

    cancelled = AITaskService.cancel_task(current_user.family_id, skill_id, db)
    if cancelled:
        return {"ok": True, "status": "cancelled"}
    return {"ok": False, "message": "no_running_task"}
