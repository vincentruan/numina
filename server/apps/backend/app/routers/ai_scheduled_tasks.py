from datetime import datetime

from croniter import CroniterBadCronError, CroniterBadDateError
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
from packages.db.models.scheduled_task import ScheduledTask, ScheduledTaskStatus

router = APIRouter(prefix="/ai/scheduled-tasks", tags=["ai-scheduled-tasks"])


def _validate_skill(skill_id: str) -> str:
    skill = skill_id.strip()
    if skill not in ALLOWED_SCHEDULABLE_SKILLS:
        raise AppError(ErrorCode.SCHEDULED_TASK_SKILL_INVALID)
    return skill


def _next_run_or_reject(cron_expression: str) -> tuple[str, datetime]:
    """Normalize a cron expression and compute its next run.

    Enforces the documented 5-field contract with ``is_valid_cron`` first,
    because ``compute_next_run_at`` (croniter) silently accepts 6-field
    expressions (with a seconds field) and macros like ``@daily``.
    """
    expression = cron_expression.strip()
    if not is_valid_cron(expression):
        raise AppError(ErrorCode.SCHEDULED_TASK_CRON_INVALID)
    try:
        return expression, compute_next_run_at(expression)
    except (ValueError, KeyError, CroniterBadCronError, CroniterBadDateError):
        raise AppError(ErrorCode.SCHEDULED_TASK_CRON_INVALID) from None


def _get_family_task(db: Session, *, task_id: int, family_id: int) -> ScheduledTask:
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
    cron_expression, next_run_at = _next_run_or_reject(payload.cron_expression)

    task = ScheduledTask(
        family_id=current_user.family_id,
        skill_id=skill_id,
        cron_expression=cron_expression,
        is_enabled=payload.is_enabled,
        next_run_at=next_run_at,
        status=ScheduledTaskStatus.IDLE,
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
    """更新定时任务（仅 owner）。"""
    task = _get_family_task(db, task_id=task_id, family_id=current_user.family_id)

    if payload.skill_id is not None:
        task.skill_id = _validate_skill(payload.skill_id)

    if payload.cron_expression is not None:
        cron_expression, next_run_at = _next_run_or_reject(payload.cron_expression)
        if cron_expression != task.cron_expression:
            task.cron_expression = cron_expression
            task.next_run_at = next_run_at

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
