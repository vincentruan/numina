"""Progress service — state machine + spaced repetition for learning progress."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency

VALID_TRANSITIONS = {
    "locked": {"available"},
    "available": {"learning"},
    "learning": {"assessing", "parent_review"},
    "assessing": {"mastered", "review"},
    "parent_review": {"mastered", "learning"},
    "mastered": {"review"},               # only -> review (via next_review_at expiry)
    "review": {"mastered", "learning"},   # pass -> mastered; fail -> learning
}


def get_or_create_progress(db: Session, child_id: int, topic_id: int) -> LearningProgress:
    """Get existing progress or create new one with initial state based on prerequisites.

    Initial state is "available" if all hard prerequisites are mastered, else "locked".
    """
    existing = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .first()
    )
    if existing:
        return existing

    # Check hard prerequisites
    hard_prereqs = (
        db.query(LearningDependency)
        .filter_by(topic_id=topic_id, strength="hard")
        .all()
    )
    all_met = all(
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=hp.prerequisite_id, mastery_level="mastered")
        .first()
        is not None
        for hp in hard_prereqs
    ) if hard_prereqs else True

    initial_level = "available" if all_met else "locked"
    progress = LearningProgress(
        child_id=child_id,
        topic_id=topic_id,
        mastery_level=initial_level,
    )
    db.add(progress)
    db.flush()
    return progress


def can_start_learning(progress: LearningProgress) -> bool:
    """Check if a topic can be started (is available or already learning)."""
    return progress.mastery_level in ("available", "learning")


def transition_to_learning(db: Session, progress: LearningProgress) -> LearningProgress:
    """Transition progress to 'learning' state."""
    _validate_transition(progress.mastery_level, "learning")
    progress.mastery_level = "learning"
    progress.last_practice_at = datetime.now(UTC)
    db.flush()
    return progress


def transition_to_mastered(
    db: Session,
    progress: LearningProgress,
    score: float,
    completed_via: str,
) -> LearningProgress:
    """Transition progress to 'mastered' state and update stability/review schedule."""
    _validate_transition(progress.mastery_level, "mastered")
    if completed_via not in ("ai_assessment", "parent_approval"):
        raise ValueError(f"Invalid completed_via: {completed_via}")
    now = datetime.now(UTC)
    progress.mastery_level = "mastered"
    progress.mastery_score = score
    progress.completed_via = completed_via
    if not progress.first_mastered_at:
        progress.first_mastered_at = now
    progress.stability = update_stability(progress, score)
    progress.next_review_at = compute_next_review(progress)
    db.flush()
    return progress


def compute_next_review(progress: LearningProgress) -> datetime:
    """Compute next review date using simplified SM-2 algorithm.

    interval_days = max(1, int(3 * stability))
    """
    stability = progress.stability or 1.0
    interval_days = max(1, int(3 * stability))
    return datetime.now(UTC) + timedelta(days=interval_days)


def update_stability(progress: LearningProgress, score: float) -> float:
    """Update stability based on assessment score.

    High score (>= 0.8): multiply by 1.3, capped at 10.0
    Low score (< 0.8): multiply by 0.6, floored at 1.0
    """
    current = progress.stability or 1.0
    if score >= 0.8:
        return min(current * 1.3, 10.0)
    else:
        return max(current * 0.6, 1.0)


def recheck_prerequisites(
    db: Session, child_id: int, topic_id: int
) -> LearningProgress:
    """Re-evaluate hard prerequisites for a locked topic; unlock if all met.

    Returns the updated progress (may still be "locked" if prerequisites unmet).
    """
    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .first()
    )
    if progress is None or progress.mastery_level != "locked":
        return progress  # type: ignore[return-value]

    hard_prereqs = (
        db.query(LearningDependency)
        .filter_by(topic_id=topic_id, strength="hard")
        .all()
    )
    all_met = all(
        db.query(LearningProgress)
        .filter_by(
            child_id=child_id,
            topic_id=hp.prerequisite_id,
            mastery_level="mastered",
        )
        .first()
        is not None
        for hp in hard_prereqs
    ) if hard_prereqs else True

    if all_met:
        progress.mastery_level = "available"
        db.flush()
    return progress


def unlock_dependent_topics(
    db: Session, child_id: int, mastered_topic_id: int
) -> list[LearningProgress]:
    """Unlock all topics that have `mastered_topic_id` as a hard prerequisite.

    Returns the list of newly-unlocked progress records.
    """
    dependent_ids = [
        row.topic_id
        for row in db.query(LearningDependency.topic_id)
        .filter_by(prerequisite_id=mastered_topic_id, strength="hard")
        .all()
    ]
    unlocked: list[LearningProgress] = []
    for dep_topic_id in dependent_ids:
        p = recheck_prerequisites(db, child_id, dep_topic_id)
        if p is not None and p.mastery_level == "available":
            unlocked.append(p)
    return unlocked


def _validate_transition(from_level: str, to_level: str) -> None:
    """Validate that a state transition is allowed."""
    if to_level not in VALID_TRANSITIONS.get(from_level, set()):
        raise AppError(ErrorCode.LEARNING_INVALID_STATE_TRANSITION)


def get_child_progress_overview(db: Session, child_id: int) -> dict:
    """Get counts of topics per mastery level for a child."""
    rows = (
        db.query(
            LearningProgress.mastery_level,
            sa_func.count(LearningProgress.id).label("cnt"),
        )
        .filter_by(child_id=child_id)
        .group_by(LearningProgress.mastery_level)
        .all()
    )
    counts = {r.mastery_level: r.cnt for r in rows}
    return {
        "mastered": counts.get("mastered", 0),
        "learning": counts.get("learning", 0),
        "available": counts.get("available", 0),
        "locked": counts.get("locked", 0),
        "review": counts.get("review", 0),
        "assessing": counts.get("assessing", 0),
        "parent_review": counts.get("parent_review", 0),
    }
