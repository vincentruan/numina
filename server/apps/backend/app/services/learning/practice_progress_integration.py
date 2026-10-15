"""Bridge between practice sessions and the learning progress state machine."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.progress_service import (
    transition_to_mastered,
    unlock_dependent_topics,
    update_sm2_after_session,
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
    - score >= 0.8: advance state (learning->assessing, assessing->mastered)
    - score < 0.5: no state change, update mastery_score
    - 0.5 <= score < 0.8: no state change, update mastery_score

    Always updates SM-2 spaced repetition (stability + next_review_at)
    regardless of state transitions.

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

                if target == "mastered":
                    # Use canonical transition_to_mastered
                    transition_to_mastered(db, progress, score, "practice_session")
                else:
                    progress.mastery_level = target
                    progress.mastery_score = score
                    progress.completed_via = "practice_session"
                    db.flush()

                mastery_changed = True
                logger.info(
                    "Progress transition via practice: child=%s topic=%s %s->%s score=%.2f",
                    child_id,
                    session.topic_id,
                    old_level,
                    target,
                    score,
                )
                if target == "mastered":
                    unlock_dependent_topics(db, child_id, session.topic_id)
            except AppError:
                logger.warning("Transition %s->%s not valid", old_level, target)
    else:
        # Update score without state change
        progress.mastery_score = score
        db.flush()

    # Always update SM-2 spaced repetition after every session
    # (transition_to_mastered already handles this internally)
    if progress.mastery_level != "mastered" or not mastery_changed:
        update_sm2_after_session(progress, score)
        from apps.backend.app.services.learning.progress_service import (
            compute_next_review,
        )

        progress.next_review_at = compute_next_review(progress)
        db.flush()

    db.commit()
    return {
        "mastery_changed": mastery_changed,
        "new_mastery_level": progress.mastery_level,
    }
