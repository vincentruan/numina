"""Session service — manage learning sessions and assessments."""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.learning import SessionCreate
from apps.backend.app.services.learning import progress_service
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession


def create_session(
    db: Session,
    child_id: int,
    req: SessionCreate,
) -> LearningSession:
    """Create a new learning session for a child."""
    # Validate topic exists and child can learn it
    progress = progress_service.get_or_create_progress(db, child_id, req.topic_id)
    if not progress_service.can_start_learning(progress):
        raise AppError(ErrorCode.LEARNING_TOPIC_LOCKED)

    # Auto-transition available -> learning
    if progress.mastery_level == "available":
        progress_service.transition_to_learning(db, progress)

    session = LearningSession(
        child_id=child_id,
        topic_id=req.topic_id,
        assignment_id=req.assignment_id,
        session_type=req.session_type,
    )
    db.add(session)
    db.flush()
    return session


def end_session(
    db: Session,
    session_id: int,
    score: float | None = None,
    ai_evaluation: dict | None = None,
) -> LearningSession:
    """End a learning session, optionally recording a score and AI evaluation."""
    session = db.query(LearningSession).filter(LearningSession.id == session_id).first()
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)

    if session.ended_at is not None:
        raise AppError(ErrorCode.LEARNING_SESSION_ALREADY_ENDED)

    session.ended_at = datetime.now(UTC)
    if score is not None:
        session.score = score
    if ai_evaluation is not None:
        session.ai_evaluation_json = json.dumps(ai_evaluation)

    # Calculate duration if started_at exists
    if session.started_at:
        delta = session.ended_at - session.started_at
        session.duration_seconds = int(delta.total_seconds())

    db.flush()
    return session


def start_assessment(
    db: Session,
    session_id: int,
    child_id: int,
) -> LearningProgress:
    """Start an assessment within a session.

    Transitions the child's progress from 'learning' to 'assessing'.
    """
    session = (
        db.query(LearningSession)
        .filter(
            LearningSession.id == session_id,
            LearningSession.child_id == child_id,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)

    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=session.topic_id)
        .first()
    )
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)

    # Transition learning -> assessing
    progress_service.validate_transition(progress.mastery_level, "assessing")
    progress.mastery_level = "assessing"
    db.flush()
    return progress


def get_session(
    db: Session,
    session_id: int,
    child_id: int,
) -> LearningSession:
    """Get a session, validating ownership by child_id."""
    session = (
        db.query(LearningSession)
        .filter(
            LearningSession.id == session_id,
            LearningSession.child_id == child_id,
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
    return session


def get_thread_id_for_session(session_id: int) -> str:
    """Session ID is used as the DeerFlow thread_id (same pattern as AIChatSession)."""
    return str(session_id)
