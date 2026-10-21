"""Session service — manage learning sessions and assessments."""

import json
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.learning import SessionCreate
from apps.backend.app.services.learning import progress_service
from packages.core.logging import get_logger
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession

logger = get_logger(__name__)


def _build_difficulty_warning(db: Session, child_id: int, topic) -> dict | None:
    """Build difficulty warning dict based on age group and prerequisites."""
    from apps.backend.app.services.learning.progress_service import (
        AGE_GROUP_ORDER,
        _age_to_group,
        _compute_age,
        find_age_appropriate_topic,
        get_unmet_prerequisites,
    )
    from apps.backend.app.services.learning.topic_service import (
        get_effective_source_taxonomy,
    )
    from packages.db.models.user import User

    child = db.query(User).filter(User.id == child_id).first()
    if not child or not child.birthday:
        return None

    child_age = _compute_age(child.birthday)
    child_age_group = _age_to_group(child_age)
    source_taxonomy = get_effective_source_taxonomy(db, child.language)

    # Age difficulty check
    age_warning = None
    if AGE_GROUP_ORDER.get(topic.age_group, 1) > AGE_GROUP_ORDER.get(child_age_group, 1):
        suggested = find_age_appropriate_topic(
            db, child_id, topic.subject, source_taxonomy=source_taxonomy
        )
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
    from apps.backend.app.services.learning.topic_service import (
        get_effective_source_taxonomy,
    )
    from packages.db.models.learning.topic import LearningTopic
    from packages.db.models.user import User

    topic = db.query(LearningTopic).filter(LearningTopic.id == req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    # Cross-source guard: ensure the topic belongs to the child's locale taxonomy
    child = db.query(User).filter(User.id == child_id).first()
    expected_source = get_effective_source_taxonomy(db, child.language if child else None)
    if topic.source_taxonomy != expected_source:
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
    # Derive thread_id from session ID (same pattern as AIChatSession)
    session.thread_id = str(session.id)
    db.commit()
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
    """End a learning session, optionally recording a score and AI evaluation.

    If a score is provided and the progress is in 'assessing' state, the
    dual-track logic applies: high scores may auto-pass to 'mastered' via
    AI assessment, while lower scores go to 'parent_review'.
    """
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

    # Dual-track: auto-pass logic when score is provided and progress is assessing
    if score is not None:
        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=session.child_id, topic_id=session.topic_id)
            .first()
        )
        if not progress:
            logger.warning(
                "end_session: no progress record for child=%s topic=%s, skipping dual-track",
                session.child_id,
                session.topic_id,
            )
        elif progress.mastery_level != "assessing":
            logger.info(
                "end_session: progress in '%s' (not assessing), skipping dual-track for child=%s topic=%s",
                progress.mastery_level,
                session.child_id,
                session.topic_id,
            )
        else:
            ai_available = _check_ai_available(db, session.child_id)
            ai_paused = progress_service.is_ai_auto_pass_paused(db, session.child_id)
            auto_result = progress_service.check_auto_pass(
                db,
                score,
                session.child_id,
                ai_paused=ai_paused,
                duration_seconds=session.duration_seconds,
            )
            try:
                if ai_available and auto_result.should_auto_pass:
                    progress_service.transition_to_mastered(
                        db, progress, score, completed_via="ai_assessment"
                    )
                else:
                    progress.mastery_level = "parent_review"
                    progress.mastery_score = score
            except Exception:
                # If transition fails, fall back to parent_review so progress
                # does not remain stuck in "assessing" indefinitely.
                logger.exception(
                    "end_session: transition_to_mastered failed for child=%s topic=%s, falling back to parent_review",
                    session.child_id,
                    session.topic_id,
                )
                progress.mastery_level = "parent_review"
                progress.mastery_score = score

    db.flush()
    db.commit()
    return session


def _check_ai_available(db: Session, child_id: int) -> bool:
    """Check whether AI assessment is available for this child's family.

    Placeholder: returns True for now. The real implementation would check
    the family's AI configuration (provider availability, model access, etc.).
    """
    return True


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

    # Transition learning -> assessing (idempotent: re-entry on retry when
    # already 'assessing' must not 409 — e.g. stream error + Retry button)
    if progress.mastery_level != "assessing":
        progress_service.validate_transition(progress.mastery_level, "assessing")
        progress.mastery_level = "assessing"
    db.flush()
    db.commit()
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
