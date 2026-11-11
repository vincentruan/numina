"""Empirical difficulty calculator — computes actual question difficulty from PracticeAttempt data.

The empirical difficulty flywheel: aggregate accuracy, response time, and retry
signals from practice attempts to derive a data-driven difficulty estimate.
This complements (and when sufficient data exists, replaces) author-specified difficulty.

Algorithm:
    empirical_difficulty = accuracy_weight * accuracy_factor
                       + time_weight * time_factor
                       + retry_weight * retry_factor

    Mapped to 1-5 scale to align with author-specified difficulty.

Minimum sample guard:
    At least MIN_SAMPLE_SIZE (10) attempts required before computing.
    Below this threshold, returns None (caller falls back to author difficulty).
"""

from dataclasses import dataclass

from sqlalchemy import Integer as sa_Integer
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt
from packages.db.models.learning.question import Question

logger = get_logger(__name__)

# Minimum attempts before empirical difficulty is computed
MIN_SAMPLE_SIZE = 10

# Weights for the three factors (sum to 1.0)
ACCURACY_WEIGHT = 0.50  # Lower accuracy → harder question
TIME_WEIGHT = 0.30  # Longer time → harder question
RETRY_WEIGHT = 0.20  # More retries → harder question

# Scale bounds for normalization
DIFFICULTY_MIN = 1.0
DIFFICULTY_MAX = 5.0

# Time normalization: median time (seconds) that maps to "medium" difficulty
# Questions answered in ~30s are "medium", much faster = easy, much slower = hard
TIME_BASELINE_SECONDS = 30
TIME_MIN_FACTOR = 0.5  # Fast answers (≤15s) → easy signal
TIME_MAX_FACTOR = 2.0  # Slow answers (≥60s) → hard signal


@dataclass
class DifficultySignals:
    """Raw signals extracted from practice attempts."""

    attempt_count: int
    accuracy: float  # 0.0 - 1.0 (higher = easier)
    median_time_seconds: float | None
    retry_rate: float  # 0.0 - 1.0 (higher = harder)


def compute_question_signals(db: Session, question_id: int) -> DifficultySignals | None:
    """Extract difficulty signals for a single question.

    Returns None if fewer than MIN_SAMPLE_SIZE attempts exist.
    """
    # Aggregate stats for this question
    row = (
        db.query(
            sa_func.count(PracticeAttempt.id).label("total"),
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label("correct"),
            sa_func.avg(PracticeAttempt.time_spent_seconds).label("avg_time"),
            sa_func.sum(sa_func.cast(PracticeAttempt.is_retry, sa_Integer)).label("retry_count"),
        )
        .filter(PracticeAttempt.question_id == question_id)
        .first()
    )

    if row is None or row.total < MIN_SAMPLE_SIZE:
        return None

    total = row.total
    correct = row.correct or 0
    retry_count = row.retry_count or 0

    # Compute median time (separate query for median)
    # Use AVG as approximation for median (SQLite lacks MEDIAN)
    median_time = row.avg_time

    accuracy = correct / total if total > 0 else 0.5
    retry_rate = retry_count / total if total > 0 else 0.0

    return DifficultySignals(
        attempt_count=total,
        accuracy=accuracy,
        median_time_seconds=median_time,
        retry_rate=retry_rate,
    )


def signals_to_difficulty(signals: DifficultySignals) -> float:
    """Convert raw signals to a 1-5 difficulty score.

    Formula:
    - accuracy_factor: 1 - accuracy (low accuracy → high difficulty)
    - time_factor: normalized median time, clamped to [0, 1]
    - retry_factor: retry rate (more retries → higher difficulty)
    """
    # Accuracy factor: 0.0 (all correct = easy) to 1.0 (all wrong = hard)
    accuracy_factor = 1.0 - signals.accuracy

    # Time factor: normalize around baseline
    if signals.median_time_seconds is not None and signals.median_time_seconds > 0:
        time_ratio = signals.median_time_seconds / TIME_BASELINE_SECONDS
        # Clamp to [TIME_MIN_FACTOR, TIME_MAX_FACTOR], then normalize to [0, 1]
        clamped = max(TIME_MIN_FACTOR, min(TIME_MAX_FACTOR, time_ratio))
        time_factor = (clamped - TIME_MIN_FACTOR) / (TIME_MAX_FACTOR - TIME_MIN_FACTOR)
    else:
        time_factor = 0.5  # Neutral if no time data

    # Retry factor: direct mapping (0.0 = no retries, 1.0 = all retries)
    retry_factor = signals.retry_rate

    # Weighted combination → 0.0 (easiest) to 1.0 (hardest)
    raw_score = (
        ACCURACY_WEIGHT * accuracy_factor
        + TIME_WEIGHT * time_factor
        + RETRY_WEIGHT * retry_factor
    )

    # Map to 1-5 scale
    difficulty = DIFFICULTY_MIN + raw_score * (DIFFICULTY_MAX - DIFFICULTY_MIN)

    # Round to 2 decimal places
    return round(difficulty, 2)


def calculate_empirical_difficulty(db: Session, question_id: int) -> float | None:
    """Calculate empirical difficulty for a single question.

    Returns:
        float (1.0-5.0) if ≥MIN_SAMPLE_SIZE attempts exist, None otherwise.
    """
    signals = compute_question_signals(db, question_id)
    if signals is None:
        return None
    return signals_to_difficulty(signals)


def batch_update_empirical_difficulty(db: Session) -> dict:
    """Batch update empirical_difficulty for all questions with sufficient data.

    Returns stats dict with counts of updated/skipped questions.
    """
    # Find all questions with ≥MIN_SAMPLE_SIZE attempts
    question_ids_with_data = (
        db.query(
            PracticeAttempt.question_id,
            sa_func.count(PracticeAttempt.id).label("total"),
        )
        .group_by(PracticeAttempt.question_id)
        .having(sa_func.count(PracticeAttempt.id) >= MIN_SAMPLE_SIZE)
        .all()
    )

    updated = 0
    skipped = 0

    for row in question_ids_with_data:
        question_id = row.question_id
        new_difficulty = calculate_empirical_difficulty(db, question_id)

        if new_difficulty is None:
            skipped += 1
            continue

        question = db.get(Question, question_id)
        if question is None:
            skipped += 1
            continue

        old_difficulty = question.empirical_difficulty
        question.empirical_difficulty = new_difficulty

        if old_difficulty != new_difficulty:
            logger.debug(
                "Question %s empirical_difficulty: %s → %s (attempts=%s)",
                question_id,
                old_difficulty,
                new_difficulty,
                row.total,
            )

        updated += 1

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to commit empirical difficulty updates")
        raise

    logger.info(
        "Empirical difficulty batch update complete: updated=%d, skipped=%d",
        updated,
        skipped,
    )

    return {"updated": updated, "skipped": skipped, "total_questions": len(question_ids_with_data)}


def get_difficulty_stats(db: Session) -> dict:
    """Get summary statistics on empirical difficulty coverage.

    Returns dict with:
    - total_questions: count of all questions
    - with_empirical: count with empirical_difficulty set
    - coverage_pct: percentage with empirical data
    - avg_empirical: average empirical difficulty (if any)
    """
    total = db.query(Question).count()
    with_empirical = (
        db.query(Question)
        .filter(Question.empirical_difficulty.isnot(None))
        .count()
    )

    avg_row = (
        db.query(sa_func.avg(Question.empirical_difficulty).label("avg"))
        .filter(Question.empirical_difficulty.isnot(None))
        .first()
    )
    avg_empirical = avg_row.avg if avg_row and avg_row.avg is not None else None

    coverage_pct = (with_empirical / total * 100) if total > 0 else 0.0

    return {
        "total_questions": total,
        "with_empirical": with_empirical,
        "coverage_pct": round(coverage_pct, 1),
        "avg_empirical": round(avg_empirical, 2) if avg_empirical else None,
    }
