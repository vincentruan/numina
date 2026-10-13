"""Adaptive question selection engine."""

import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import Float as sa_Float
from sqlalchemy import Integer as sa_Integer
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic

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


def _mastery_score_to_difficulty(score: float) -> tuple[int, int]:
    """Map 0.0-1.0 mastery score to difficulty range.

    Low mastery → easy questions, high mastery → harder questions.
    """
    if score < 0.3:
        return (1, 2)
    elif score < 0.7:
        return (1, 3)
    elif score < 0.85:
        return (2, 4)
    else:
        return (3, 5)


class MasteryEstimator(Protocol):
    """Protocol for knowledge mastery estimation."""

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Return 0.0-1.0 mastery estimate."""
        ...


class RuleBasedMasteryEstimator:
    """Mastery estimate based on time-decay weighted recent accuracy.

    Recent correct answers count more than older ones (exponential decay).
    Falls back to 0.5 (neutral) when fewer than MIN_SAMPLE_SIZE attempts exist.
    """

    MIN_SAMPLE_SIZE = 3
    DECAY_FACTOR = 0.8
    MAX_ATTEMPTS = 10

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Estimate mastery as time-decay weighted accuracy.

        Weight formula: weight_i = DECAY_FACTOR ^ (n - 1 - i)
        where i is the attempt index (0=oldest) and n is total attempts.
        Most recent attempt gets weight 1.0, previous gets 0.8, etc.
        """
        attempts = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .order_by(PracticeAttempt.created_at.desc())
            .limit(self.MAX_ATTEMPTS)
            .all()
        )
        if len(attempts) < self.MIN_SAMPLE_SIZE:
            return 0.5  # Neutral fallback for insufficient data

        # Reverse to chronological order for decay weighting
        attempts = list(reversed(attempts))
        n = len(attempts)
        total_weight = 0.0
        weighted_correct = 0.0

        for i, attempt in enumerate(attempts):
            weight = self.DECAY_FACTOR ** (n - 1 - i)
            total_weight += weight
            if attempt.is_correct:
                weighted_correct += weight

        return weighted_correct / total_weight if total_weight > 0 else 0.0


class BayesianKnowledgeTracingEstimator:
    """Bayesian Knowledge Tracing (BKT) mastery estimator.

    Uses the standard BKT model with per-topic belief state tracking:
    - P(L₀): initial probability of knowing (default 0.1)
    - P(T): probability of learning on each attempt (default 0.3)
    - P(G): probability of guessing correctly when not knowing (default 0.25)
    - P(S): probability of slipping (wrong answer when knowing) (default 0.1)

    Falls back to RuleBasedMasteryEstimator when fewer than MIN_ATTEMPTS
    observations are available (< 5).
    """

    MIN_ATTEMPTS = 5

    def __init__(
        self,
        p_l0: float = 0.1,
        p_t: float = 0.3,
        p_g: float = 0.25,
        p_s: float = 0.1,
    ):
        self.p_l0 = p_l0
        self.p_t = p_t
        self.p_g = p_g
        self.p_s = p_s

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Estimate mastery via Bayesian belief state update.

        Iterates through attempts chronologically, applying Bayes' rule
        after each observation, then projecting forward with P(T).
        """
        attempts = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=topic_id)
            .order_by(PracticeAttempt.created_at.asc())
            .all()
        )

        if len(attempts) < self.MIN_ATTEMPTS:
            # Insufficient data — fallback to rule-based
            return RuleBasedMasteryEstimator().estimate(db, child_id, topic_id)

        # BKT forward algorithm
        p_l = self.p_l0
        for attempt in attempts:
            # Bayesian update: P(L|observation)
            if attempt.is_correct:
                p_l_given_obs = (
                    p_l * (1 - self.p_s)
                    / (p_l * (1 - self.p_s) + (1 - p_l) * self.p_g)
                )
            else:
                p_l_given_obs = (
                    p_l * self.p_s
                    / (p_l * self.p_s + (1 - p_l) * (1 - self.p_g))
                )
            # Transition: P(L_{n+1}) = P(L|obs) + (1 - P(L|obs)) * P(T)
            # Standard BKT: knowledge can only grow, never unlearn
            p_l = p_l_given_obs + (1 - p_l_given_obs) * self.p_t

        return p_l


def select_questions(
    db: Session,
    topic_id: int,
    mastery_level: str,
    count: int,
    exclude_question_ids: list[int],
    exclude_recent_days: int,
    child_id: int,
    estimator: MasteryEstimator | None = None,
    session_mode: str = "practice",
) -> list[Question]:
    """Select questions for a practice session.

    Strategy:
    1. If estimator provided, use it to get dynamic mastery score → difficulty range
    2. Otherwise, fall back to static mastery_level → difficulty mapping
    3. session_mode adjusts difficulty and selection:
       - "practice": normal adaptive selection
       - "review": prioritize previously-wrong questions (relax exclusion window)
       - "challenge": force harder questions (difficulty 4-5)
    4. Filter by topic, difficulty range, review_status=approved
    5. Exclude recently answered questions (last N days) — except review mode
    6. Random sample up to count
    """
    if session_mode == "challenge":
        min_diff, max_diff = 4, 5
    elif estimator is not None:
        mastery_score = estimator.estimate(db, child_id=child_id, topic_id=topic_id)
        min_diff, max_diff = _mastery_score_to_difficulty(mastery_score)
    else:
        min_diff, max_diff = get_difficulty_range(mastery_level)

    # Review mode: include recently-answered questions (relax exclusion)
    if session_mode == "review":
        cutoff = datetime.now(UTC) - timedelta(days=1)  # only exclude today's
    else:
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


# --- Phase 5b: Prerequisite weak practice ---


def find_weak_prerequisites(
    db: Session, topic_id: int, child_id: int
) -> list[dict]:
    """Find prerequisite topics that are weak (not mastered) for the child.

    Uses existing get_unmet_prerequisites() to find unmet prereqs,
    then enriches with accuracy data from PracticeAttempt.
    """
    from apps.backend.app.services.learning.progress_service import (
        get_unmet_prerequisites,
    )
    from packages.db.models.learning.progress import LearningProgress

    unmet = get_unmet_prerequisites(db, topic_id=topic_id, child_id=child_id)

    results = []
    for prereq in unmet:
        attempts = (
            db.query(PracticeAttempt)
            .filter_by(child_id=child_id, topic_id=prereq.id)
            .all()
        )
        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct) if attempts else 0
        accuracy = correct / total if total > 0 else 0.0

        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=prereq.id)
            .first()
        )

        results.append({
            "topic_id": prereq.id,
            "topic_name": prereq.name,
            "topic_name_zh": prereq.name_zh,
            "mastery_level": progress.mastery_level if progress else "available",
            "total_attempts": total,
            "accuracy": accuracy,
        })

    # Sort by accuracy ASC (weakest first)
    results.sort(key=lambda r: r["accuracy"])
    return results


# --- Phase 6d: Explainable learning progress ---


def get_ability_dimensions(db: Session, child_id: int) -> list[dict]:
    """Get per-domain accuracy breakdown for a child.

    Returns list of {domain, total_attempts, correct_count, accuracy}.
    """
    from sqlalchemy import func as sa_func

    rows = (
        db.query(
            LearningTopic.domain,
            sa_func.count(PracticeAttempt.id).label("total"),
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label("correct"),
        )
        .join(PracticeAttempt, PracticeAttempt.topic_id == LearningTopic.id)
        .filter(PracticeAttempt.child_id == child_id)
        .group_by(LearningTopic.domain)
        .all()
    )

    return [
        {
            "domain": row.domain,
            "total_attempts": row.total,
            "correct_count": row.correct or 0,
            "accuracy": (row.correct or 0) / row.total if row.total > 0 else 0.0,
        }
        for row in rows
    ]


def get_progress_trend(
    db: Session, child_id: int, topic_id: int
) -> list[dict]:
    """Get chronological attempt history for a child+topic.

    Returns list of {attempt_number, is_correct, created_at}.
    """
    attempts = (
        db.query(PracticeAttempt)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .order_by(PracticeAttempt.created_at.asc())
        .all()
    )

    return [
        {
            "attempt_number": a.attempt_number,
            "is_correct": a.is_correct,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in attempts
    ]


def get_recommend_with_reason(
    db: Session, child_id: int, limit: int = 5
) -> list[dict]:
    """Get practice recommendations with explainable reasons.

    Each recommendation includes a 'reason' field explaining why
    this topic is recommended.
    """
    from sqlalchemy import func as sa_func

    # Get topics with attempts, ordered by accuracy (weakest first)
    rows = (
        db.query(
            LearningTopic.id,
            LearningTopic.name,
            LearningTopic.name_zh,
            LearningTopic.domain,
            sa_func.count(PracticeAttempt.id).label("total"),
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label("correct"),
        )
        .join(PracticeAttempt, PracticeAttempt.topic_id == LearningTopic.id)
        .filter(PracticeAttempt.child_id == child_id)
        .group_by(LearningTopic.id)
        .order_by(sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Float)) / sa_func.count(PracticeAttempt.id))
        .limit(limit)
        .all()
    )

    results = []
    for row in rows:
        accuracy = (row.correct or 0) / row.total if row.total > 0 else 0.0

        # Generate explainable reason key for frontend i18n
        if accuracy < 0.5:
            reason_key = "low_accuracy"
        elif accuracy < 0.7:
            reason_key = "medium_accuracy"
        else:
            reason_key = "high_accuracy"

        results.append({
            "topic_id": row.id,
            "topic_name": row.name,
            "topic_name_zh": row.name_zh,
            "domain": row.domain,
            "total_attempts": row.total,
            "accuracy": accuracy,
            "reason_key": reason_key,
        })

    return results
