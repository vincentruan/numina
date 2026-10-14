"""Coverage evaluation service (P7a-min: existence + prerequisite value).

Minimal version: coverage_score = existence (binary 0/1).
Prerequisite value used for prioritization in gap reports.
P7a-full will upgrade to 5-dim weighted model.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningDependency, LearningTopic

logger = get_logger(__name__)


def get_prerequisite_value(db: Session, topic_id: int) -> float:
    """Compute normalized prerequisite value for a topic.

    Value = (number of topics that depend on this topic) / (max dependents in subject).
    Returns 0.0 if the topic has no dependents or is the only topic.
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

    # Find max dependents in same subject for normalization
    subject_topic_ids = (
        db.query(LearningTopic.id)
        .filter(
            LearningTopic.subject == topic.subject,
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )
    tid_list = [t[0] for t in subject_topic_ids]
    if not tid_list:
        return 0.0

    max_dependents = 0
    for tid in tid_list:
        count = (
            db.query(LearningDependency)
            .filter(LearningDependency.prerequisite_id == tid)
            .count()
        )
        if count > max_dependents:
            max_dependents = count

    if max_dependents == 0:
        return 0.0

    return dependent_count / max_dependents


def compute_topic_coverage(
    db: Session, topic_id: int, family_id: int | None = None
) -> dict:
    """Compute coverage score for a single topic (P7a-min version).

    Returns dict with:
    - topic_id, existence (0/1), prerequisite_value (0-1), coverage_score (0-1)

    When family_id is provided, scopes Question queries to that family only.
    """
    # Existence: does this topic have ≥1 approved question?
    q_filter = [
        Question.topic_id == topic_id,
        Question.review_status == "approved",
    ]
    if family_id is not None:
        q_filter.append(Question.family_id == family_id)
    approved_count = db.query(Question).filter(*q_filter).count()
    existence = 1.0 if approved_count > 0 else 0.0

    prereq_value = get_prerequisite_value(db, topic_id)

    # P7a-min: score = existence (the only meaningful dimension at 0.56% coverage)
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
    """
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.subject == subject,
            LearningTopic.deprecated == False,  # noqa: E712
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

    covered = 0
    total_prereq = 0.0
    for t in topics:
        q_filter = [
            Question.topic_id == t.id,
            Question.review_status == "approved",
        ]
        if family_id is not None:
            q_filter.append(Question.family_id == family_id)
        approved = db.query(Question).filter(*q_filter).count()
        if approved > 0:
            covered += 1
        total_prereq += get_prerequisite_value(db, t.id)

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

    Returns list of dicts with topic info and coverage details.
    When family_id is provided, scopes Question queries to that family only.
    """
    query = db.query(LearningTopic).filter(
        LearningTopic.deprecated == False,  # noqa: E712
    )
    if subject:
        query = query.filter(LearningTopic.subject == subject)

    topics = query.all()
    gaps = []

    for topic in topics:
        cov = compute_topic_coverage(db, topic.id, family_id=family_id)
        if cov["coverage_score"] < threshold:
            gaps.append(
                {
                    "topic_id": topic.id,
                    "topic_key": topic.topic_key,
                    "name": topic.name,
                    "subject": topic.subject,
                    "domain": topic.domain,
                    "coverage_score": cov["coverage_score"],
                    "prerequisite_value": cov["prerequisite_value"],
                }
            )

    gaps.sort(key=lambda x: -x["prerequisite_value"])
    return gaps[:limit]
