"""Adaptive question selection engine."""

import random
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import Float as sa_Float
from sqlalchemy import Integer as sa_Integer
from sqlalchemy import func as sa_func
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

    Uses the standard BKT model with per-topic belief state tracking.
    Per-skill parameters (P(L0), P(T), P(G), P(S)) are fitted from data
    via bkt_calibration.get_bkt_parameters() — topics with sufficient
    attempt data get custom parameters; others use defaults.

    Falls back to RuleBasedMasteryEstimator when fewer than MIN_ATTEMPTS
    observations are available (< 5).
    """

    MIN_ATTEMPTS = 5

    def __init__(
        self,
        p_l0: float | None = None,
        p_t: float | None = None,
        p_g: float | None = None,
        p_s: float | None = None,
    ):
        # Store global defaults (used when per-skill params unavailable)
        self.default_p_l0 = p_l0 if p_l0 is not None else 0.1
        self.default_p_t = p_t if p_t is not None else 0.3
        self.default_p_g = p_g if p_g is not None else 0.25
        self.default_p_s = p_s if p_s is not None else 0.1

    def _get_params_for_topic(self, db: Session, topic_id: int) -> tuple[float, float, float, float]:
        """Get BKT parameters for a topic, preferring per-skill fitted values."""
        from apps.backend.app.services.learning.bkt_calibration import (
            get_bkt_parameters,
        )

        params = get_bkt_parameters(db, topic_id)
        if params.is_fitted:
            return params.p_l0, params.p_t, params.p_g, params.p_s
        # Use defaults
        return self.default_p_l0, self.default_p_t, self.default_p_g, self.default_p_s

    def estimate(self, db: Session, child_id: int, topic_id: int) -> float:
        """Estimate mastery via Bayesian belief state update.

        Iterates through attempts chronologically, applying Bayes' rule
        after each observation, then projecting forward with P(T).
        Uses per-skill calibrated parameters when available.
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

        # Get per-skill parameters (fitted or defaults)
        p_l0, p_t, p_g, p_s = self._get_params_for_topic(db, topic_id)

        # BKT forward algorithm
        p_l = p_l0
        for attempt in attempts:
            # Bayesian update: P(L|observation)
            if attempt.is_correct:
                p_l_given_obs = (
                    p_l * (1 - p_s)
                    / (p_l * (1 - p_s) + (1 - p_l) * p_g)
                )
            else:
                p_l_given_obs = (
                    p_l * p_s
                    / (p_l * p_s + (1 - p_l) * (1 - p_g))
                )
            # Transition: P(L_{n+1}) = P(L|obs) + (1 - P(L|obs)) * P(T)
            # Standard BKT: knowledge can only grow, never unlearn
            p_l = p_l_given_obs + (1 - p_l_given_obs) * p_t

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
       Uses COALESCE(empirical_difficulty, difficulty) — empirical_difficulty
       replaces author difficulty when sufficient attempt data exists (≥10 attempts).
    5. Exclude recently answered questions (last N days) — except review mode
    6. Random sample up to count
    """
    # Derive effective mode: explicit session_mode takes precedence;
    # fallback to mastery_level for backward compatibility (callers that
    # pass mastery_level="review" without session_mode still get review behavior).
    effective_mode = session_mode if session_mode != "practice" else mastery_level

    if effective_mode == "challenge":
        min_diff, max_diff = 4, 5
    elif estimator is not None:
        mastery_score = estimator.estimate(db, child_id=child_id, topic_id=topic_id)
        min_diff, max_diff = _mastery_score_to_difficulty(mastery_score)
    else:
        min_diff, max_diff = get_difficulty_range(mastery_level)

    # Recent question IDs for this child
    # Review mode: do NOT exclude recently-answered questions — the whole
    # point of review is to re-ask questions the child already saw.
    if effective_mode == "review":
        recent_ids: set[int] = set()
    else:
        cutoff = datetime.now(UTC) - timedelta(days=exclude_recent_days)
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

    # Use empirical_difficulty when available, fall back to author difficulty.
    # COALESCE returns the first non-null value, so questions with ≥10 attempts
    # (where empirical_difficulty is computed) use data-driven difficulty.
    effective_difficulty = sa_func.coalesce(
        Question.empirical_difficulty, Question.difficulty
    )

    query = db.query(Question).filter(
        Question.topic_id == topic_id,
        effective_difficulty >= min_diff,
        effective_difficulty <= max_diff,
        Question.review_status == "approved",
    )

    if exclude_set:
        query = query.filter(~Question.id.in_(exclude_set))

    candidates = query.all()

    # Review mode: prioritize questions the child previously answered wrong.
    if effective_mode == "review" and candidates:
        wrong_ids = {
            row.question_id
            for row in db.query(PracticeAttempt.question_id)
            .filter(
                PracticeAttempt.child_id == child_id,
                PracticeAttempt.topic_id == topic_id,
                PracticeAttempt.is_correct == False,  # noqa: E712
            )
            .all()
        }
        wrong_candidates = [q for q in candidates if q.id in wrong_ids]
        other_candidates = [q for q in candidates if q.id not in wrong_ids]
        random.shuffle(wrong_candidates)
        random.shuffle(other_candidates)
        candidates = wrong_candidates + other_candidates

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


# --- Prerequisite backtrace diagnosis (issue #213) ---

# Threshold for "stuck" detection. Applied uniformly to both estimator scales;
# the BKT-eligible (5+ attempts) class ranks before the rule-based (3-4 attempts)
# class — a recommendation backed by more evidence is safer to show a child.
DIAGNOSIS_MASTERY_THRESHOLD = 0.60
DIAGNOSIS_CONFIG_VERSION = "v1"

# Mastery levels a diagnosis candidate must not be in: mastered ends the search
# for a gap, and locked would make the card's action fail to start a session.
NON_CANDIDATE_MASTERY_LEVELS = frozenset({"mastered", "locked"})


def diagnose_weak_prerequisites(
    db: Session,
    topic_id: int,
    child_id: int,
    lookback_topic_ids: list[int] | None = None,
) -> list[dict]:
    """Depth-2 prerequisite backtrace for a child stuck on a topic.

    Returns qualified weak prerequisites (≥3 attempts, BKT below threshold,
    mastery_level neither mastered nor locked, topic not deprecated, has
    practiceable questions, not a direct prerequisite of the target).
    Ranked BKT-class first then rule-based, mastery ascending within each
    class, depth descending within ties. Deduped by topic id at minimum depth.

    ``lookback_topic_ids`` names direct prerequisites the child is weak on:
    the child already sees them on the page, so they, and their own
    prerequisites, are not reported. ``depth`` counts layers beyond the
    target's direct prerequisites (depth 1 = a prerequisite of a
    prerequisite).

    Writes one DiagnosisImpression row per qualified candidate before returning.
    Returns an empty list when the target itself does not meet the trigger
    (≥3 attempts AND estimate below threshold).
    """
    from collections import deque

    from packages.db.models.learning.diagnosis_impression import DiagnosisImpression
    from packages.db.models.learning.progress import LearningProgress
    from packages.db.models.learning.topic import LearningDependency

    estimator = BayesianKnowledgeTracingEstimator()

    # Gate: the target itself must be stuck, i.e. have enough attempts and a
    # low enough estimate. Both estimator classes share the threshold.
    target_attempts = (
        db.query(PracticeAttempt)
        .filter_by(child_id=child_id, topic_id=topic_id)
        .count()
    )
    if target_attempts < RuleBasedMasteryEstimator.MIN_SAMPLE_SIZE:
        return []
    if estimator.estimate(db, child_id, topic_id) >= DIAGNOSIS_MASTERY_THRESHOLD:
        return []

    # Build the upstream adjacency (hard edges only) and the set of the
    # target's direct prerequisites, which the page already shows.
    edges = (
        db.query(LearningDependency.topic_id, LearningDependency.prerequisite_id)
        .filter_by(strength="hard")
        .all()
    )
    topic_prereqs: dict[int, list[int]] = {}
    for topic_ref, prereq_ref in edges:
        topic_prereqs.setdefault(topic_ref, []).append(prereq_ref)

    direct_prereq_ids: set[int] = {
        prereq_ref for topic_ref, prereq_ref in edges if topic_ref == topic_id
    }

    # BFS upstream over hard edges, so a cycle terminates and a topic reached
    # by several paths is kept at its minimum hop count. Reported depth counts
    # layers beyond the target's direct prerequisites, which the page already
    # shows: a prerequisite of a prerequisite is depth 1.
    lookback_ids = list(dict.fromkeys(lookback_topic_ids or []))
    skip_ids: set[int] = set(lookback_ids)
    hops: dict[int, int] = {topic_id: 0}
    queue: deque[tuple[int, int]] = deque()
    for p in topic_prereqs.get(topic_id, []):
        if p in hops:
            continue
        hops[p] = 1
        queue.append((p, 1))
    while queue:
        current, hop = queue.popleft()
        if hop >= 3:
            continue
        for p in topic_prereqs.get(current, []):
            if p in hops:
                continue
            hops[p] = hop + 1
            queue.append((p, hop + 1))

    candidate_map: dict[int, int] = {
        tid: hop - 1
        for tid, hop in hops.items()
        if tid != topic_id and hop >= 2 and tid not in skip_ids
    }
    if not candidate_map:
        return []

    # Load all candidate topics once.
    candidate_ids = list(candidate_map.keys())
    candidate_topics = {
        t.id: t
        for t in db.query(LearningTopic)
        .filter(LearningTopic.id.in_(candidate_ids))
        .all()
    }

    # Batch the per-candidate lookups so the loop costs no per-topic queries.
    progress_levels = {
        p.topic_id: p.mastery_level
        for p in db.query(LearningProgress)
        .filter(
            LearningProgress.child_id == child_id,
            LearningProgress.topic_id.in_(candidate_ids),
        )
        .all()
    }
    attempts_by_topic: dict[int, list[bool]] = {}
    for attempt in (
        db.query(PracticeAttempt.topic_id, PracticeAttempt.is_correct)
        .filter(
            PracticeAttempt.child_id == child_id,
            PracticeAttempt.topic_id.in_(candidate_ids),
        )
        .all()
    ):
        attempts_by_topic.setdefault(attempt.topic_id, []).append(attempt.is_correct)
    topics_with_questions = {
        q.topic_id
        for q in db.query(Question.topic_id)
        .filter(
            Question.topic_id.in_(candidate_ids),
            Question.review_status == "approved",
        )
        .distinct()
        .all()
    }

    results: list[dict] = []
    for cand_id, depth in candidate_map.items():
        topic = candidate_topics.get(cand_id)
        if topic is None or topic.deprecated:
            continue
        if cand_id in direct_prereq_ids or cand_id in skip_ids:
            continue

        # No progress row yet means the topic is available, not mastered.
        mastery_level = progress_levels.get(cand_id, "available")
        if mastery_level in NON_CANDIDATE_MASTERY_LEVELS:
            continue

        outcomes = attempts_by_topic.get(cand_id, [])
        attempt_count = len(outcomes)
        if attempt_count < RuleBasedMasteryEstimator.MIN_SAMPLE_SIZE:
            continue
        accuracy = sum(1 for correct in outcomes if correct) / attempt_count

        mastery = estimator.estimate(db, child_id, cand_id)
        if mastery >= DIAGNOSIS_MASTERY_THRESHOLD:
            continue

        # The card's action must be able to start a session for this topic.
        if cand_id not in topics_with_questions:
            continue

        results.append(
            {
                "topic_id": cand_id,
                "topic_name": topic.name,
                "topic_name_zh": topic.name_zh,
                "depth": depth,
                "bkt_mastery": mastery,
                "sample_size": attempt_count,
                "mastery_level": mastery_level,
                "accuracy": accuracy,
            }
        )

    # More attempts means a better-evidenced recommendation, so BKT-scored
    # candidates come first. Then weakest mastery, then the deeper (more
    # root-cause) prerequisite.
    bkt_min_attempts = BayesianKnowledgeTracingEstimator.MIN_ATTEMPTS
    results.sort(
        key=lambda r: (
            r["sample_size"] < bkt_min_attempts,
            r["bkt_mastery"],
            -r["depth"],
        )
    )

    # Write one DiagnosisImpression row per qualified candidate.
    for r in results:
        db.add(
            DiagnosisImpression(
                child_id=child_id,
                target_topic_id=topic_id,
                recommended_topic_id=r["topic_id"],
                bkt_mastery=r["bkt_mastery"],
                sample_size=r["sample_size"],
                config_version=DIAGNOSIS_CONFIG_VERSION,
            )
        )
    db.flush()  # the router commits; flush surfaces constraint errors here

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
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label(
                "correct"
            ),
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


def get_progress_trend(db: Session, child_id: int, topic_id: int) -> list[dict]:
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


def get_recommend_with_reason(db: Session, child_id: int, limit: int = 5) -> list[dict]:
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
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Integer)).label(
                "correct"
            ),
        )
        .join(PracticeAttempt, PracticeAttempt.topic_id == LearningTopic.id)
        .filter(PracticeAttempt.child_id == child_id)
        .group_by(LearningTopic.id)
        .order_by(
            sa_func.sum(sa_func.cast(PracticeAttempt.is_correct, sa_Float))
            / sa_func.count(PracticeAttempt.id)
        )
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

        results.append(
            {
                "topic_id": row.id,
                "topic_name": row.name,
                "topic_name_zh": row.name_zh,
                "domain": row.domain,
                "total_attempts": row.total,
                "accuracy": accuracy,
                "reason_key": reason_key,
            }
        )

    return results
