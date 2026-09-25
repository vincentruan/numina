"""Progress service — state machine + spaced repetition for learning progress."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import (
    LearningAssessmentAttempt,
    LearningSession,
)
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


def aggregate_study_minutes(db: Session, child_id: int) -> dict[str, int]:
    """Return total and today study minutes for a child in a single query.

    Excludes sessions with ended_at=None (still in progress).
    Returns 0 for both fields when no matching sessions exist.
    """
    from sqlalchemy import case

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

    total_seconds, today_seconds = (
        db.query(
            sa_func.coalesce(sa_func.sum(LearningSession.duration_seconds), 0),
            sa_func.coalesce(
                sa_func.sum(
                    case(
                        (LearningSession.ended_at >= today_start, LearningSession.duration_seconds),
                        else_=0,
                    )
                ),
                0,
            ),
        )
        .filter(
            LearningSession.child_id == child_id,
            LearningSession.ended_at.isnot(None),
        )
        .one()
    )

    return {
        "total_study_minutes": int(total_seconds) // 60,
        "today_study_minutes": int(today_seconds) // 60,
    }


STREAK_THRESHOLD = 3


def check_consecutive_failures(db: Session, child_id: int, topic_id: int) -> int:
    """Count consecutive failed assessments for a child on a specific topic.

    Walks backward from the most recent attempt. Stops at the first pass
    or beginning of attempts.

    Returns:
        Number of consecutive failures (0 if last attempt passed or no attempts).
    """
    attempts = (
        db.query(LearningAssessmentAttempt)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .order_by(LearningAssessmentAttempt.created_at.desc())
        .all()
    )
    streak = 0
    for attempt in attempts:
        if not attempt.passed:
            streak += 1
        else:
            break
    return streak


def record_failed_assessment(
    db: Session,
    child_id: int,
    topic_id: int,
    session_id: int | None,
    score: float | None,
) -> int:
    """Record a failed assessment attempt and check for streak notification.

    Creates a LearningAssessmentAttempt with passed=False, then checks
    if the consecutive failure count has reached the threshold.

    Returns:
        Current consecutive failure count. Caller should dispatch notification
        if return value == STREAK_THRESHOLD (exactly 3, not > 3 to avoid duplicates).
    """
    attempt = LearningAssessmentAttempt(
        child_id=child_id,
        topic_id=topic_id,
        session_id=session_id,
        assessment_type="ai",
        score=score,
        passed=False,
    )
    db.add(attempt)
    db.flush()

    streak = check_consecutive_failures(db, child_id, topic_id)

    # Fire notification exactly when threshold is reached (not on 4th, 5th, etc.)
    if streak == STREAK_THRESHOLD:
        from apps.backend.app.services.notification.dispatcher import (
            notify_learning_streak_3_failures,
        )
        from packages.db.models.user import User

        topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
        # child_id references users.id directly — children are User rows with role="child"
        child_user = db.query(User).filter(User.id == child_id).first()
        if child_user and topic:
            notify_learning_streak_3_failures(
                db,
                family_id=child_user.family_id,
                child_name=child_user.display_name or child_user.username,
                topic_name=topic.name_zh or topic.name or topic.topic_key,
                subject=topic.subject,
            )

    return streak


def find_recommended_topic(
    db: Session, child_id: int
) -> LearningTopic | None:
    """Find a locked topic whose hard prereqs are all met — recommended next.

    Returns the first such topic sorted by topic_id (stable ordering),
    or None if no locked topics qualify.
    """
    locked_progresses = (
        db.query(LearningProgress)
        .filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "locked",
        )
        .all()
    )
    for lp in sorted(locked_progresses, key=lambda p: p.topic_id):
        if _all_hard_prereqs_met(db, child_id, lp.topic_id):
            return (
                db.query(LearningTopic)
                .filter(LearningTopic.id == lp.topic_id)
                .first()
            )
    return None
