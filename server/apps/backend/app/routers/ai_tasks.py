"""AI 任务状态查询端点。

- GET /ai/tasks/{skill_id}         — 查询当前 skill_id 的任务状态
- GET /ai/tasks/{skill_id}/session — 获取关联的 session_id（用于前端接续）
- POST /ai/tasks/{skill_id}/cancel — 终止当前运行的任务
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.services.ai_task_service import AITaskService

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


@router.get("/{skill_id}")
def get_task_status(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """查询当前 skill_id 的任务状态（含排队状态）。"""
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
    """获取当前 running 任务关联的 session_id（用于前端接续历史消息）。"""
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
    """终止当前运行或排队的任务。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"ok": False, "message": "invalid_skill_id"}

    cancelled = AITaskService.cancel_task(current_user.family_id, skill_id, db)
    if cancelled:
        return {"ok": True, "status": "cancelled"}
    return {"ok": False, "message": "no_running_task"}
