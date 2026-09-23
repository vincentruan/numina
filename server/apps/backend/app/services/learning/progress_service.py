"""Progress service — state machine + spaced repetition for learning progress."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningAssessmentAttempt
from packages.db.models.learning.topic import LearningDependency, LearningTopic

VALID_TRANSITIONS = {
    "locked": {"available"},
    "available": {"learning"},
    "learning": {"assessing", "parent_review"},
    "assessing": {"mastered", "review", "parent_review"},
    "parent_review": {"mastered", "learning"},
    "mastered": {"review", "learning"},  # review via expiry; learning for re-study
    "review": {"learning"},              # fail -> re-learn; pass handled via assessing
}


def _all_hard_prereqs_met(db: Session, child_id: int, topic_id: int) -> bool:
    """Check whether all hard prerequisites for a topic are mastered by the child."""
    hard_prereqs = (
        db.query(LearningDependency)
        .filter_by(topic_id=topic_id, strength="hard")
        .all()
    )
    if not hard_prereqs:
        return True
    return all(
        db.query(LearningProgress)
        .filter_by(
            child_id=child_id,
            topic_id=hp.prerequisite_id,
            mastery_level="mastered",
        )
        .first()
        is not None
        for hp in hard_prereqs
    )


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

    initial_level = "available" if _all_hard_prereqs_met(db, child_id, topic_id) else "locked"
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
    validate_transition(progress.mastery_level, "learning")
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
    validate_transition(progress.mastery_level, "mastered")
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

    if _all_hard_prereqs_met(db, child_id, topic_id):
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


def validate_transition(from_level: str, to_level: str) -> None:
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


REWARD_COINS = 10


def approve_parent_review(
    db: Session,
    progress: LearningProgress,
    family_id: int,
) -> LearningProgress:
    """Approve a parent_review → mastered transition with full side-effects.

    Performs atomic CAS, updates stability, unlocks dependents,
    creates coin reward + assessment attempt.
    """
    # Atomic CAS: only transition if currently in parent_review
    result = db.execute(
        LearningProgress.__table__.update()
        .where(
            LearningProgress.id == progress.id,
            LearningProgress.mastery_level == "parent_review",
        )
        .values(mastery_level="mastered", completed_via="parent_approval")
    )
    if result.rowcount == 0:
        raise AppError(ErrorCode.LEARNING_INVALID_STATE_TRANSITION)

    db.refresh(progress)

    # Update spaced-repetition bookkeeping
    now = datetime.now(UTC)
    if not progress.first_mastered_at:
        progress.first_mastered_at = now
    progress.mastery_score = progress.mastery_score or 1.0
    progress.stability = update_stability(progress, progress.mastery_score)
    progress.next_review_at = compute_next_review(progress)

    # Unlock dependent topics
    unlock_dependent_topics(db, progress.child_id, progress.topic_id)

    # Resolve topic name for narrative (prefer localized name)
    topic = db.query(LearningTopic).filter(LearningTopic.id == progress.topic_id).first()
    topic_label = (topic.name_zh or topic.name or "learning") if topic else "learning"

    # Create assessment attempt record
    attempt = LearningAssessmentAttempt(
        child_id=progress.child_id,
        topic_id=progress.topic_id,
        assessment_type="parent_approval",
        score=progress.mastery_score,
        passed=True,
    )
    db.add(attempt)

    # Create coin reward transaction
    txn = CoinTransaction(
        family_id=family_id,
        child_user_id=progress.child_id,
        amount=REWARD_COINS,
        transaction_type="learning_earn",
        narrative=f"掌握知识点：{topic_label}",
        narrative_emoji="🌟",
    )
    db.add(txn)
    db.flush()

    # Link coin transaction to attempt for idempotency
    txn.ref_id = attempt.id

    return progress
