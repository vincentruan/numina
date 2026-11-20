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
from apps.backend.app.services.scheduled_task import validate_cron_expression
from packages.db.models.scheduled_task import ScheduledTask

router = APIRouter(prefix="/ai/scheduled-tasks", tags=["ai-scheduled-tasks"])


def _validate_skill(skill_id: str) -> str:
    skill = skill_id.strip()
    if skill not in ALLOWED_SCHEDULABLE_SKILLS:
        raise AppError(ErrorCode.SCHEDULED_TASK_SKILL_INVALID)
    return skill


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
    """List all scheduled tasks for the current family (owner only).

    Defaults are materialized at family creation; an empty list after explicit
    deletion stays empty.
    """
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
    """Create a scheduled task (owner only)."""
    skill_id = _validate_skill(payload.skill_id)
    cron_expression, next_run_at = validate_cron_expression(payload.cron_expression)

    task = ScheduledTask(
        family_id=current_user.family_id,
        skill_id=skill_id,
        cron_expression=cron_expression,
        is_enabled=payload.is_enabled,
        is_default=False,
        next_run_at=next_run_at,
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
    """Update a scheduled task (owner only)."""
    task = _get_family_task(db, task_id=task_id, family_id=current_user.family_id)

    if payload.skill_id is not None:
        task.skill_id = _validate_skill(payload.skill_id)

    if payload.cron_expression is not None:
        cron_expression, next_run_at = validate_cron_expression(payload.cron_expression)
        if cron_expression != task.cron_expression:
            task.cron_expression = cron_expression
            task.next_run_at = next_run_at

    if payload.is_enabled is not None:
        task.is_enabled = payload.is_enabled

    # Any owner edit makes the task a family-specific configuration.
    task.is_default = False

    db.commit()
    db.refresh(task)

    return ScheduledTaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=204)
def delete_scheduled_task(
    task_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """Delete a scheduled task (owner only)."""
    task = _get_family_task(db, task_id=task_id, family_id=current_user.family_id)
    db.delete(task)
    db.commit()
