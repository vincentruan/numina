"""Preset learning path endpoints — list and assign curriculum-aligned paths."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    AssignPresetRequest,
    PathResponse,
    PresetPathResponse,
)
from apps.backend.app.services.learning import preset_path_service
from packages.core.logging import get_logger
from packages.db.models.learning.preset_path import PresetLearningPath

logger = get_logger(__name__)

router = APIRouter(prefix="/family/learning", tags=["learning-preset"])


def _preset_to_response(preset: PresetLearningPath) -> dict:
    """Convert PresetLearningPath ORM object to response dict."""
    import json

    return {
        "id": preset.id,
        "grade": preset.grade,
        "semester": preset.semester,
        "subject": preset.subject,
        "name": preset.name,
        "name_zh": preset.name_zh,
        "description": preset.description,
        "topic_count": preset.topic_count,
        "topic_ids": json.loads(preset.topic_ids_json),
        "is_active": preset.is_active,
    }


@router.get("/preset-paths", response_model=list[PresetPathResponse])
def list_preset_paths_endpoint(
    grade: int | None = Query(None, description="Filter by grade (1-6)"),
    semester: str | None = Query(None, description="Filter by semester (fall/spring)"),
    subject: str | None = Query(None, description="Filter by subject"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """List available preset learning paths with optional filters."""
    presets = preset_path_service.list_preset_paths(
        db, grade=grade, semester=semester, subject=subject
    )
    return [_preset_to_response(p) for p in presets]


@router.post(
    "/preset-paths/{preset_id}/assign",
    response_model=PathResponse,
    status_code=201,
)
def assign_preset_path_endpoint(
    preset_id: int,
    req: AssignPresetRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Assign a preset learning path to a child.

    Creates a LearningPath + LearningPathItems for the child.
    """
    path = preset_path_service.assign_preset_path(
        db,
        preset_id=preset_id,
        child_id=req.child_id,
        parent_id=current_user.id,
    )

    # Build PathResponse
    from apps.backend.app.services.learning.path_service import get_path_progress

    progress = get_path_progress(db, path.id, path.family_id)

    return {
        "id": path.id,
        "family_id": path.family_id,
        "child_id": path.child_id,
        "created_by": path.created_by,
        "name": path.name,
        "name_zh": path.name_zh,
        "description": path.description,
        "description_zh": path.description_zh,
        "status": path.status,
        "per_task_score": path.per_task_score,
        "bonus_score": path.bonus_score,
        "milestone_scores": path.milestone_scores or [],
        "due_date": path.due_date,
        "created_at": path.created_at,
        "completed_at": path.completed_at,
        "items": progress["items"],
        "completed_count": progress["completed_count"],
        "total_count": progress["total_count"],
        "next_milestone": progress["next_milestone"],
    }
