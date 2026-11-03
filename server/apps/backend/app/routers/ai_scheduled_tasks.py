"""定时任务 CRUD 路由。

- GET    /api/v1/ai/scheduled-tasks      — 列出当前家庭的定时任务
- POST   /api/v1/ai/scheduled-tasks      — 创建定时任务
- PUT    /api/v1/ai/scheduled-tasks/{id} — 更新定时任务（含启用/禁用）
- DELETE /api/v1/ai/scheduled-tasks/{id} — 删除定时任务

所有端点仅家庭 Owner 可访问。cron 表达式按 Asia/Shanghai 解释，
``next_run_at`` 持久化为 UTC。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.scheduled_task import (
    ALLOWED_SCHEDULABLE_SKILLS,
    ScheduledTaskCreate,
    ScheduledTaskListResponse,
    ScheduledTaskResponse,
    ScheduledTaskUpdate,
)
from packages.core.cron import compute_next_run_at, is_valid_cron
from packages.db.models.scheduled_task import ScheduledTask

router = APIRouter(prefix="/ai/scheduled-tasks", tags=["ai-scheduled-tasks"])


def _validate_skill(skill_id: str) -> str:
    skill = skill_id.strip()
    if skill not in ALLOWED_SCHEDULABLE_SKILLS:
        raise AppError(ErrorCode.SCHEDULED_TASK_SKILL_INVALID)
    return skill


def _validate_cron(cron_expression: str) -> str:
    expression = cron_expression.strip()
    if not is_valid_cron(expression):
        raise AppError(ErrorCode.SCHEDULED_TASK_CRON_INVALID)
    return expression


def _get_family_task(db: Session, *, task_id: int, family_id: int) -> ScheduledTask:
    """Fetch a task scoped to the caller's family.

    Cross-family access surfaces as 404 rather than 403 so the endpoint does not
    reveal whether a task id exists in another family.
    """
    task = (
        db.query(ScheduledTask)
        .filter(
            ScheduledTask.id == task_id,
            ScheduledTask.family_id == family_id,
        )
        .first()
    )
    if not task:
        raise AppError(ErrorCode.SCHEDULED_TASK_NOT_FOUND)
    return task


@router.get("", response_model=ScheduledTaskListResponse)
def list_scheduled_tasks(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> ScheduledTaskListResponse:
    """列出当前家庭的全部定时任务（仅 owner）。"""
    tasks = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.family_id == current_user.family_id)
        .order_by(ScheduledTask.created_at, ScheduledTask.id)
        .all()
    )
    return ScheduledTaskListResponse(
        items=[ScheduledTaskResponse.model_validate(t) for t in tasks]
    )


@router.post("", response_model=ScheduledTaskResponse, status_code=201)
def create_scheduled_task(
    payload: ScheduledTaskCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> ScheduledTaskResponse:
    """创建定时任务（仅 owner）。"""
    skill_id = _validate_skill(payload.skill_id)
    cron_expression = _validate_cron(payload.cron_expression)

    task = ScheduledTask(
        family_id=current_user.family_id,
        skill_id=skill_id,
        cron_expression=cron_expression,
        is_enabled=payload.is_enabled,
        next_run_at=compute_next_run_at(cron_expression),
        status="idle",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return ScheduledTaskResponse.model_validate(task)


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
def update_scheduled_task(
    task_id: int,
    payload: ScheduledTaskUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> ScheduledTaskResponse:
    """更新定时任务（仅 owner）。

    cron 表达式变化时重新计算 ``next_run_at``；仅切换启用状态时保留原计划，
    避免用户只是想临时禁用却意外推迟下次执行时间。
    """
    task = _get_family_task(db, task_id=task_id, family_id=current_user.family_id)

    if payload.skill_id is not None:
        task.skill_id = _validate_skill(payload.skill_id)

    if payload.cron_expression is not None:
        cron_expression = _validate_cron(payload.cron_expression)
        if cron_expression != task.cron_expression:
            task.cron_expression = cron_expression
            task.next_run_at = compute_next_run_at(cron_expression)

    if payload.is_enabled is not None:
        task.is_enabled = payload.is_enabled

    db.commit()
    db.refresh(task)

    return ScheduledTaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=204)
def delete_scheduled_task(
    task_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """删除定时任务（仅 owner）。"""
    task = _get_family_task(db, task_id=task_id, family_id=current_user.family_id)
    db.delete(task)
    db.commit()
