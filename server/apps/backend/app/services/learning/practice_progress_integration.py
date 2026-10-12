"""Bridge between practice sessions and the learning progress state machine."""
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.progress_service import (
    unlock_dependent_topics,
    validate_transition,
)
from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeSession
from packages.db.models.learning.progress import LearningProgress

logger = get_logger(__name__)


def update_progress_from_session(
    db: Session,
    session_id: int,
    child_id: int,
) -> dict:
    """Update learning progress based on practice session results.

    Rules:
    - score >= 0.8: advance state (learning→assessing, assessing→mastered)
    - score < 0.5: no state change, update mastery_score
    - 0.5 <= score < 0.8: no state change, update mastery_score

    Returns dict with mastery_changed, new_mastery_level.
    """
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session or session.total_score is None:
        return {"mastery_changed": False, "new_mastery_level": None}

    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=session.topic_id)
        .first()
    )
    if not progress:
        return {"mastery_changed": False, "new_mastery_level": None}

    score = session.total_score
    old_level = progress.mastery_level
    mastery_changed = False

    if score >= 0.8:
        # Determine target state
        if old_level == "learning":
            target = "assessing"
        elif old_level == "assessing":
            target = "mastered"
        else:
            target = None

        if target:
            try:
                validate_transition(old_level, target)
                progress.mastery_level = target
                progress.mastery_score = score
                progress.completed_via = "practice_session"
                if target == "mastered":
                    progress.stability = _update_stability(progress, score)
                    from datetime import UTC, datetime, timedelta

                    progress.first_mastered_at = datetime.now(UTC)
                    progress.next_review_at = datetime.now(UTC) + timedelta(
                        days=max(1, int(3 * (progress.stability or 1.0)))
                    )
                db.flush()
                mastery_changed = True
                logger.info(
                    "Progress transition via practice: child=%s topic=%s %s→%s score=%.2f",
                    child_id,
                    session.topic_id,
                    old_level,
                    target,
                    score,
                )
                if target == "mastered":
                    unlock_dependent_topics(db, child_id, session.topic_id)
            except AppError:
                logger.warning("Transition %s→%s not valid", old_level, target)
    else:
        # Update score without state change
        progress.mastery_score = score
        db.flush()

    return {
        "mastery_changed": mastery_changed,
        "new_mastery_level": progress.mastery_level,
    }


def _update_stability(progress: LearningProgress, score: float) -> float:
    """Update stability (same logic as progress_service)."""
    current = progress.stability or 1.0
    if score >= 0.8:
        return min(current * 1.3, 10.0)
    return max(current * 0.6, 1.0)
