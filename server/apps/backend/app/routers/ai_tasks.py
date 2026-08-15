"""AI task query endpoints for frontend task resume and status display."""

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
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[AITaskResponse]:
    """Query AI tasks for the current family.

    Used by frontend useTaskResume hook to check for running tasks on page load.
    Returns tasks filtered by skill_id and/or status, scoped to the user's family.

    Example: GET /api/v1/ai/tasks?skill=report&status=running
    """
    from packages.db.models.ai_task import AITask

    query = db.query(AITask).filter(AITask.family_id == current_user.family_id)

    if skill_id:
        query = query.filter(AITask.skill_id == skill_id)

    if status:
        query = query.filter(AITask.status == status)

    # Order by started_at descending (most recent first)
    query = query.order_by(AITask.started_at.desc())

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
