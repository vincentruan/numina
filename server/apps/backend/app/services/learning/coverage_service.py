"""Coverage evaluation service (P7a-min: existence + prerequisite value).

Minimal version: coverage_score = existence (binary 0/1).
Prerequisite value used for prioritization in gap reports.
P7a-full will upgrade to 5-dim weighted model.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic

logger = get_logger(__name__)


def get_prerequisite_value(db: Session, topic_id: int) -> float:
    """Compute normalized prerequisite value for a topic.

    Value = (number of topics that depend on this topic) / (max dependents in subject).
    Returns 0.0 if the topic has no dependents or is the only topic.

    P1-5 fix: uses a single GROUP BY query instead of N individual COUNTs.
    """
    dependent_count = (
        db.query(LearningDependency)
        .filter(LearningDependency.prerequisite_id == topic_id)
        .count()
    )

    if dependent_count == 0:
        return 0.0

    # Get the topic's subject for normalization
    topic = db.get(LearningTopic, topic_id)
    if topic is None or topic.subject is None:
        return 0.0

    # Find all topic IDs in the same subject
    subject_topic_ids = (
        db.query(LearningTopic.id)
        .filter(
            LearningTopic.subject == topic.subject,
            LearningTopic.deprecated.is_(False),
        )
        .all()
    )
    tid_list = [t[0] for t in subject_topic_ids]
    if not tid_list:
        return 0.0

    # P1-5 fix: single GROUP BY query replaces per-topic COUNT loop
    dep_counts = dict(
        db.query(
            LearningDependency.prerequisite_id,
            func.count(LearningDependency.id),
        )
        .filter(LearningDependency.prerequisite_id.in_(tid_list))
        .group_by(LearningDependency.prerequisite_id)
        .all()
    )

    max_dependents = max(dep_counts.values()) if dep_counts else 0
    if max_dependents == 0:
        return 0.0

    return dependent_count / max_dependents


def _batch_compute_existence(
    db: Session, topic_ids: list[int], family_id: int | None = None
) -> dict[int, int]:
    """Batch-load approved question counts per topic in a single GROUP BY query.

    Returns {topic_id: approved_count}.
    """
    q_filter = [
        Question.review_status == "approved",
        Question.topic_id.in_(topic_ids),
    ]
    if family_id is not None:
        q_filter.append(
            (Question.family_id == family_id) | Question.family_id.is_(None)
        )

    rows = (
        db.query(Question.topic_id, func.count(Question.id))
        .filter(*q_filter)
        .group_by(Question.topic_id)
        .all()
    )
    return {topic_id: count for topic_id, count in rows}


def _batch_prerequisite_values(
    db: Session, topic_ids: list[int]
) -> dict[int, float]:
    """Batch-compute prerequisite values for a set of topics in the same subject.

    Returns {topic_id: prerequisite_value} using at most 3 queries total
    instead of O(N) per-topic queries.
    """
    if not topic_ids:
        return {}

    # Get subjects for all topics
    topics = (
        db.query(LearningTopic.id, LearningTopic.subject)
        .filter(LearningTopic.id.in_(topic_ids))
        .all()
    )
    subjects = {t.subject for t in topics if t.subject}

    # Per subject: single GROUP BY for dependent counts
    result: dict[int, float] = {}
    for subject in subjects:
        subject_topic_ids = [t.id for t in topics if t.subject == subject]

        dep_counts = dict(
            db.query(
                LearningDependency.prerequisite_id,
                func.count(LearningDependency.id),
            )
            .filter(LearningDependency.prerequisite_id.in_(subject_topic_ids))
            .group_by(LearningDependency.prerequisite_id)
            .all()
        )

        max_dependents = max(dep_counts.values()) if dep_counts else 0
        for tid in subject_topic_ids:
            count = dep_counts.get(tid, 0)
            result[tid] = count / max_dependents if max_dependents > 0 else 0.0

    return result


def compute_topic_coverage(
    db: Session, topic_id: int, family_id: int | None = None
) -> dict:
    """Compute coverage score for a single topic (P7a-min version).

    Returns dict with:
    - topic_id, existence (0/1), prerequisite_value (0-1), coverage_score (0-1)

    When family_id is provided, scopes Question queries to that family only.
    """
    q_filter = [
        Question.topic_id == topic_id,
        Question.review_status == "approved",
    ]
    if family_id is not None:
        q_filter.append(Question.family_id == family_id)
    approved_count = db.query(Question).filter(*q_filter).count()
    existence = 1.0 if approved_count > 0 else 0.0

    prereq_value = get_prerequisite_value(db, topic_id)

    coverage_score = existence

    return {
        "topic_id": topic_id,
        "existence": existence,
        "prerequisite_value": prereq_value,
        "coverage_score": coverage_score,
        "approved_question_count": approved_count,
    }


def compute_subject_coverage(
    db: Session, subject: str, family_id: int | None = None
) -> dict:
    """Compute subject-level coverage aggregation.

    Returns dict with:
    - subject, total_topics, covered_topics, coverage_rate, avg_prerequisite_value

    When family_id is provided, scopes Question queries to that family only.
    Uses batch queries to avoid N+1 pattern.
    """
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.subject == subject,
            LearningTopic.deprecated.is_(False),
        )
        .all()
    )
    total = len(topics)
    if total == 0:
        return {
            "subject": subject,
            "total_topics": 0,
            "covered_topics": 0,
            "coverage_rate": 0.0,
            "avg_prerequisite_value": 0.0,
        }

    topic_ids = [t.id for t in topics]

    # Batch: single GROUP BY for approved question counts
    existence_map = _batch_compute_existence(db, topic_ids, family_id)

    # Batch: prerequisite values in at most 3 queries
    prereq_map = _batch_prerequisite_values(db, topic_ids)

    covered = sum(1 for tid in topic_ids if existence_map.get(tid, 0) > 0)
    total_prereq = sum(prereq_map.get(tid, 0.0) for tid in topic_ids)

    return {
        "subject": subject,
        "total_topics": total,
        "covered_topics": covered,
        "coverage_rate": covered / total,
        "avg_prerequisite_value": total_prereq / total,
    }


def get_gap_report(
    db: Session,
    subject: str | None = None,
    threshold: float = 0.5,
    limit: int = 100,
    family_id: int | None = None,
) -> list[dict]:
    """Get topics below coverage threshold, sorted by prerequisite value (descending).

    Uses batch queries to avoid N+1 pattern.
    """
    query = db.query(LearningTopic).filter(
        LearningTopic.deprecated.is_(False),
    )
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.all()
    if not topics:
        return []

    topic_ids = [t.id for t in topics]

    # Batch: existence + prerequisite values
    existence_map = _batch_compute_existence(db, topic_ids, family_id)
    prereq_map = _batch_prerequisite_values(db, topic_ids)

    gaps = []
    for topic in topics:
        approved_count = existence_map.get(topic.id, 0)
        existence = 1.0 if approved_count > 0 else 0.0
        if existence < threshold:
            gaps.append(
                {
                    "topic_id": topic.id,
                    "topic_key": topic.topic_key,
                    "name": topic.name,
                    "subject": topic.subject,
                    "domain": topic.domain,
                    "coverage_score": existence,
                    "prerequisite_value": prereq_map.get(topic.id, 0.0),
                }
            )

    gaps.sort(key=lambda x: -x["prerequisite_value"])
    return gaps[:limit]
