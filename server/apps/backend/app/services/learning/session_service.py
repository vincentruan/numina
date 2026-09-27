"""Session service — manage learning sessions and assessments."""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.learning import SessionCreate
from apps.backend.app.services.learning import progress_service
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession


def _build_difficulty_warning(db: Session, child_id: int, topic) -> dict | None:
    """Build difficulty warning dict based on age group and prerequisites."""
    from apps.backend.app.services.learning.progress_service import (
        AGE_GROUP_ORDER,
        _age_to_group,
        _compute_age,
        find_age_appropriate_topic,
        get_unmet_prerequisites,
    )
    from packages.db.models.user import User

    child = db.query(User).filter(User.id == child_id).first()
    if not child or not child.birthday:
        return None

    child_age = _compute_age(child.birthday)
    child_age_group = _age_to_group(child_age)

    # Age difficulty check
    age_warning = None
    if AGE_GROUP_ORDER.get(topic.age_group, 1) > AGE_GROUP_ORDER.get(child_age_group, 1):
        suggested = find_age_appropriate_topic(db, child_id, topic.subject)
        age_warning = {
            "level": topic.age_group,
            "child_level": child_age_group,
            "suggested_topic_id": str(suggested.id) if suggested else None,
            "suggested_topic_name_zh": suggested.name_zh if suggested else None,
            "suggested_topic_name": suggested.name if suggested else None,
        }

    # Prerequisite check
    prereq_warning = None
    unmet = get_unmet_prerequisites(db, topic.id, child_id)
    if unmet:
        prereq_warning = {
            "unmet_count": len(unmet),
            "suggested_topic_id": str(unmet[0].id),
            "suggested_topic_name_zh": unmet[0].name_zh,
            "suggested_topic_name": unmet[0].name,
        }

    # Merge: age takes priority
    if age_warning:
        return {"type": "age", **age_warning}
    elif prereq_warning:
        return {"type": "prerequisite", **prereq_warning}
    return None


def create_session(
    db: Session,
    child_id: int,
    req: SessionCreate,
) -> dict:
    """Create a new learning session for a child.

    Supports self-directed learning: if the topic is locked, it is
    overridden to 'available' so the child can start anyway.
    Returns a dict including ``difficulty_warning`` when the topic's
    age group exceeds the child's or prerequisites are unmet.
    """
    from packages.db.models.learning.topic import LearningTopic
    from packages.db.models.user import User

    topic = db.query(LearningTopic).filter(LearningTopic.id == req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    progress = progress_service.get_or_create_progress(db, child_id, req.topic_id)

    # Self-selected bypass: override locked -> available
    if progress.mastery_level == "locked":
        progress.mastery_level = "available"
        db.flush()

    # Validate can start (should now pass since we unlocked above)
    if not progress_service.can_start_learning(progress):
        raise AppError(ErrorCode.LEARNING_TOPIC_LOCKED)

    # Auto-transition available -> learning
    if progress.mastery_level == "available":
        progress_service.transition_to_learning(db, progress)

    # Build difficulty warning
    difficulty_warning = _build_difficulty_warning(db, child_id, topic)

    # Resolve assignment: use provided, or find existing, or auto-create self_selected
    assignment_id = req.assignment_id
    if not assignment_id:
        existing_assignment = (
            db.query(LearningAssignment)
            .filter(
                LearningAssignment.child_id == child_id,
                LearningAssignment.topic_id == req.topic_id,
                LearningAssignment.status.in_(["pending", "in_progress"]),
            )
            .first()
        )
        if existing_assignment:
            assignment_id = existing_assignment.id
        else:
            # Auto-create self_selected assignment
            child = db.query(User).filter(User.id == child_id).first()
            if not child:
                raise AppError(ErrorCode.CHILD_NOT_FOUND)
            assignment = LearningAssignment(
                family_id=child.family_id,
                child_id=child_id,
                topic_id=req.topic_id,
                created_by=child_id,
                assignment_type="self_selected",
            )
            db.add(assignment)
            db.flush()
            assignment_id = assignment.id

    session = LearningSession(
        child_id=child_id,
        topic_id=req.topic_id,
        assignment_id=assignment_id,
        session_type=req.session_type,
    )
    db.add(session)
    db.flush()
    db.refresh(session)

    return {
        "id": session.id,
        "assignment_id": session.assignment_id,
        "child_id": session.child_id,
        "topic_id": session.topic_id,
        "thread_id": session.thread_id,
        "session_type": session.session_type,
        "score": session.score,
        "duration_seconds": session.duration_seconds,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "difficulty_warning": difficulty_warning,
    }


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
