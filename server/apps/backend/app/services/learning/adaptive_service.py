"""Adaptive question selection engine."""

import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt
from packages.db.models.learning.question import Question

logger = get_logger(__name__)

# Mastery level → (min_difficulty, max_difficulty)
DIFFICULTY_MAP: dict[str, tuple[int, int]] = {
    "available": (1, 2),
    "learning": (1, 2),
    "assessing": (2, 3),
    "mastered": (3, 4),
    "review": (1, 2),
}


def get_difficulty_range(mastery_level: str) -> tuple[int, int]:
    """Get (min, max) difficulty for a mastery level."""
    return DIFFICULTY_MAP.get(mastery_level, (1, 3))


def select_questions(
    db: Session,
    topic_id: int,
    mastery_level: str,
    count: int,
    exclude_question_ids: list[int],
    exclude_recent_days: int,
    child_id: int,
) -> list[Question]:
    """Select questions for a practice session.

    Strategy:
    1. Filter by topic, difficulty range, review_status=approved
    2. Exclude recently answered questions (last N days)
    3. Exclude explicitly excluded IDs
    4. Random sample up to count
    """
    min_diff, max_diff = get_difficulty_range(mastery_level)
    cutoff = datetime.now(UTC) - timedelta(days=exclude_recent_days)

    # Recent question IDs for this child
    recent_ids = {
        row.question_id
        for row in db.query(PracticeAttempt.question_id)
        .filter(
            PracticeAttempt.child_id == child_id,
            PracticeAttempt.topic_id == topic_id,
            PracticeAttempt.created_at >= cutoff,
        )
        .all()
    }

    exclude_set = set(exclude_question_ids) | recent_ids

    query = db.query(Question).filter(
        Question.topic_id == topic_id,
        Question.difficulty >= min_diff,
        Question.difficulty <= max_diff,
        Question.review_status == "approved",
    )

    if exclude_set:
        query = query.filter(~Question.id.in_(exclude_set))

    candidates = query.all()

    random.shuffle(candidates)
    return candidates[:count]


class MasteryEstimator(Protocol):
    """Protocol for knowledge mastery estimation."""

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Return 0.0-1.0 mastery estimate."""
        ...


class RuleBasedMasteryEstimator:
    """Simple mastery estimate based on recent attempt accuracy."""

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Estimate mastery as ratio of correct attempts in last 10 tries."""
        attempts = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .order_by(PracticeAttempt.created_at.desc())
            .limit(10)
            .all()
        )
        if not attempts:
            return 0.0
        correct = sum(1 for a in attempts if a.is_correct)
        return correct / len(attempts)
