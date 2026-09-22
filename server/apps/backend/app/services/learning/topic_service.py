"""Knowledge graph query functions for learning topics."""

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import (
    LearningCluster,
    LearningDependency,
    LearningTopic,
)


def list_topics(
    db: Session,
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    deprecated: bool = False,
) -> list[LearningTopic]:
    """List topics with optional filters, ordered by subject/domain/centrality."""
    q = db.query(LearningTopic).filter(LearningTopic.deprecated == deprecated)
    if subject:
        q = q.filter(LearningTopic.subject == subject)
    if domain:
        q = q.filter(LearningTopic.domain == domain)
    if age_group:
        q = q.filter(LearningTopic.age_group == age_group)
    return q.order_by(LearningTopic.subject, LearningTopic.domain, LearningTopic.centrality.desc().nullslast()).all()


def get_topic_by_id(db: Session, topic_id: int) -> LearningTopic | None:
    """Get a single topic by ID, or None if not found."""
    return db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()


def get_topic_graph(db: Session, topic_id: int) -> dict | None:
    """Get a topic with its prerequisites and dependents.

    Returns dict with keys: topic, prerequisites, dependents.
    Returns None if topic not found.
    """
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None

    prereq_ids = [
        row.prerequisite_id
        for row in db.query(LearningDependency.prerequisite_id)
        .filter(LearningDependency.topic_id == topic_id)
        .all()
    ]
    dep_ids = [
        row.topic_id
        for row in db.query(LearningDependency.topic_id)
        .filter(LearningDependency.prerequisite_id == topic_id)
        .all()
    ]

    prerequisites = (
        db.query(LearningTopic).filter(LearningTopic.id.in_(prereq_ids)).all()
        if prereq_ids
        else []
    )
    dependents = (
        db.query(LearningTopic).filter(LearningTopic.id.in_(dep_ids)).all()
        if dep_ids
        else []
    )

    return {"topic": topic, "prerequisites": prerequisites, "dependents": dependents}


def list_clusters(db: Session, subject: str | None = None) -> list[LearningCluster]:
    """List learning clusters, optionally filtered by subject."""
    q = db.query(LearningCluster)
    if subject:
        q = q.filter(LearningCluster.subject == subject)
    return q.order_by(LearningCluster.subject, LearningCluster.domain).all()


def list_subjects(db: Session) -> list[dict]:
    """List all non-deprecated subjects with their topic counts."""
    rows = (
        db.query(
            LearningTopic.subject,
            sa_func.count(LearningTopic.id).label("topic_count"),
        )
        .filter(LearningTopic.deprecated == False)  # noqa: E712
        .group_by(LearningTopic.subject)
        .order_by(LearningTopic.subject)
        .all()
    )
    return [{"subject": r.subject, "topic_count": r.topic_count} for r in rows]
