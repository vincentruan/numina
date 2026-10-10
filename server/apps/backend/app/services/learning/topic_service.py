"""Knowledge graph query functions for learning topics."""

from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import (
    LearningCluster,
    LearningDependency,
    LearningTopic,
)

#: Valid values for ``LearningTopic.source_taxonomy``.
SOURCE_TAXONOMY_BEIJING = "beijing"
SOURCE_TAXONOMY_OS = "os-taxonomy"


def locale_to_source_taxonomy(language: str | None) -> str:
    """Map user language to taxonomy source.

    zh-CN -> "beijing"; en-US or any other / None -> "os-taxonomy".
    """
    return SOURCE_TAXONOMY_BEIJING if language == "zh-CN" else SOURCE_TAXONOMY_OS


def list_topics(
    db: Session,
    subject: str | None = None,
    domain: str | None = None,
    age_group: str | None = None,
    deprecated: bool = False,
    search: str | None = None,
    limit: int | None = None,
    source_taxonomy: str | None = None,
) -> list[LearningTopic]:
    """List topics with optional filters, ordered by subject/domain/centrality.

    ``deprecated`` defaults to False so callers get non-deprecated topics
    unless they explicitly request deprecated ones.
    """
    q = db.query(LearningTopic).filter(LearningTopic.deprecated == deprecated)
    if source_taxonomy:
        q = q.filter(LearningTopic.source_taxonomy == source_taxonomy)
    if subject:
        q = q.filter(LearningTopic.subject == subject)
    if domain:
        q = q.filter(LearningTopic.domain == domain)
    if age_group:
        q = q.filter(LearningTopic.age_group == age_group)
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (LearningTopic.name.ilike(pattern))
            | (LearningTopic.name_zh.ilike(pattern))
            | (LearningTopic.domain.ilike(pattern))
        )
    q = q.order_by(LearningTopic.subject, LearningTopic.domain, LearningTopic.centrality.desc().nullslast())
    if limit:
        q = q.limit(limit)
    return q.all()


def get_topic_by_id(
    db: Session, topic_id: int, deprecated: bool = False
) -> LearningTopic | None:
    """Get a single topic by ID, or None if not found."""
    return (
        db.query(LearningTopic)
        .filter(LearningTopic.id == topic_id, LearningTopic.deprecated == deprecated)
        .first()
    )


def list_topics_by_ids(
    db: Session,
    topic_ids: list[int],
    source_taxonomy: str | None = None,
) -> list[LearningTopic]:
    """Fetch multiple topics by ID list, preserving input order."""
    q = db.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids))
    if source_taxonomy:
        q = q.filter(LearningTopic.source_taxonomy == source_taxonomy)
    topics = q.all()
    # Preserve input order
    by_id = {t.id: t for t in topics}
    return [by_id[tid] for tid in topic_ids if tid in by_id]


def get_topic_graph(
    db: Session,
    topic_id: int,
    source_taxonomy: str | None = None,
) -> dict | None:
    """Get a topic with its prerequisites and dependents.

    Prerequisites and dependents are restricted to the same source taxonomy
    when provided. Returns dict with keys: topic, prerequisites, dependents.
    Returns None if topic not found.
    """
    topic = get_topic_by_id(db, topic_id)
    if not topic:
        return None

    prereq_rows = (
        db.query(
            LearningDependency.prerequisite_id,
            LearningDependency.review_status,
        )
        .filter(LearningDependency.topic_id == topic_id)
        .all()
    )
    dep_rows = (
        db.query(
            LearningDependency.topic_id,
            LearningDependency.review_status,
        )
        .filter(LearningDependency.prerequisite_id == topic_id)
        .all()
    )

    prereq_ids = [row.prerequisite_id for row in prereq_rows]
    dep_ids = [row.topic_id for row in dep_rows]

    prereq_q = db.query(LearningTopic).filter(LearningTopic.id.in_(prereq_ids))
    dep_q = db.query(LearningTopic).filter(LearningTopic.id.in_(dep_ids))
    if source_taxonomy:
        prereq_q = prereq_q.filter(LearningTopic.source_taxonomy == source_taxonomy)
        dep_q = dep_q.filter(LearningTopic.source_taxonomy == source_taxonomy)

    prereq_topics = {t.id: t for t in (prereq_q.all() if prereq_ids else [])}
    dep_topics = {t.id: t for t in (dep_q.all() if dep_ids else [])}

    prerequisites = [
        {"topic": prereq_topics[row.prerequisite_id], "review_status": row.review_status}
        for row in prereq_rows
        if row.prerequisite_id in prereq_topics
    ]
    dependents = [
        {"topic": dep_topics[row.topic_id], "review_status": row.review_status}
        for row in dep_rows
        if row.topic_id in dep_topics
    ]

    return {"topic": topic, "prerequisites": prerequisites, "dependents": dependents}


def list_clusters(
    db: Session,
    subject: str | None = None,
    source_taxonomy: str | None = None,
) -> list[LearningCluster]:
    """List learning clusters, optionally filtered by subject/taxonomy."""
    q = db.query(LearningCluster)
    if subject:
        q = q.filter(LearningCluster.subject == subject)
    if source_taxonomy:
        q = q.filter(LearningCluster.source_taxonomy == source_taxonomy)
    return q.order_by(LearningCluster.subject, LearningCluster.domain).all()


def list_subjects(
    db: Session, source_taxonomy: str | None = None
) -> list[dict]:
    """List all non-deprecated subjects with their topic counts."""
    q = (
        db.query(
            LearningTopic.subject,
            sa_func.count(LearningTopic.id).label("topic_count"),
        )
        .filter(LearningTopic.deprecated == False)  # noqa: E712
    )
    if source_taxonomy:
        q = q.filter(LearningTopic.source_taxonomy == source_taxonomy)
    rows = q.group_by(LearningTopic.subject).order_by(LearningTopic.subject).all()
    return [{"subject": r.subject, "topic_count": r.topic_count} for r in rows]
