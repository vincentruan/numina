"""Child learning endpoints — learning activities for children."""

import contextlib

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    AssignmentResponse,
    ProgressResponse,
    SessionCreate,
    SessionResponse,
    TopicResponse,
)
from apps.backend.app.services.learning import (
    assignment_service,
    session_service,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_submitted_for_review,
)
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic

router = APIRouter(prefix="/child/learning", tags=["learning-child"])


@router.get("/map", response_model=list[ProgressResponse])
def my_knowledge_map(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get my knowledge map with mastery levels."""
    return (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id == child.id)
        .all()
    )


@router.get("/assignments", response_model=list[AssignmentResponse])
def my_assignments(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get my learning assignments."""
    return assignment_service.list_assignments(db, child.id, status)


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_detail(
    topic_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get topic detail — public topic info (no per-child progress embedded)."""
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return topic


@router.post("/sessions", response_model=SessionResponse, status_code=201)
def create_session(
    req: SessionCreate,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Create a new learning session."""
    return session_service.create_session(db, child.id, req)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get a learning session."""
    session = (
        db.query(LearningSession)
        .filter(LearningSession.id == session_id, LearningSession.child_id == child.id)
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
    return session


@router.post("/sessions/{session_id}/start-assessment", response_model=ProgressResponse)
def start_assessment(
    session_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Start an assessment within a session (learning -> assessing)."""
    return session_service.start_assessment(db, session_id, child.id)


@router.post("/assignments/{assignment_id}/submit", response_model=ProgressResponse)
def submit_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Submit an assignment for parent review."""
    progress = assignment_service.submit_for_review(db, assignment_id, child.id)
    # Fire notification — parent should review
    assignment = (
        db.query(LearningAssignment)
        .filter(LearningAssignment.id == assignment_id)
        .first()
    )
    if assignment:
        topic = db.query(LearningTopic).filter(LearningTopic.id == assignment.topic_id).first()
        child_name = child.display_name or child.username or ""
        topic_name = topic.name_zh or topic.name or "" if topic else ""
        with contextlib.suppress(Exception):
            notify_learning_submitted_for_review(
                db, child.family_id, child_name, topic_name
            )
    return progress


@router.get("/progress", response_model=ProgressResponse)
def my_overall_progress(
    db: Session = Depends(get_db),
    child: User = Depends(get_current_child_user),
):
    """Get overall progress overview — returns aggregated counts as a pseudo-progress.

    Since there's no single "overall" progress record, return a summary-like response.
    Frontend can use /map for per-topic breakdown.
    """
    # Return the most recently updated progress as a representative record
    progress = (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id == child.id)
        .order_by(LearningProgress.updated_at.desc())
        .first()
    )
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)
    return progress
