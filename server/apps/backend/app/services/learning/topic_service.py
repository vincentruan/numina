"""Knowledge graph query functions for learning topics."""

from typing import Literal

from sqlalchemy import exists, or_
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
SourceTaxonomy = Literal["beijing", "os-taxonomy"]


def _locale_to_source_taxonomy(language: str | None) -> SourceTaxonomy:
    """Map user language to taxonomy source.

    zh-CN -> "beijing"; en-US or any other / None -> "os-taxonomy".
    """
    return SOURCE_TAXONOMY_BEIJING if language == "zh-CN" else SOURCE_TAXONOMY_OS


#: Public alias — retained for backward compatibility with tests.
locale_to_source_taxonomy = _locale_to_source_taxonomy


def get_effective_source_taxonomy(db: Session, language: str | None) -> SourceTaxonomy:
    """Return the taxonomy to actually use, falling back to os-taxonomy when
    the locale-mapped taxonomy has no seeded data.

    Calls :func:`_locale_to_source_taxonomy` first, then issues a single
    existence probe (``EXISTS … OR EXISTS …``) against topics and clusters.
    If neither table has rows for the mapped taxonomy and it is not already
    ``os-taxonomy``, returns ``SOURCE_TAXONOMY_OS`` as fallback.
    """
    mapped = _locale_to_source_taxonomy(language)
    if mapped == SOURCE_TAXONOMY_OS:
        return mapped
    has_data = db.query(
        or_(
            exists().where(LearningTopic.source_taxonomy == mapped),
            exists().where(LearningCluster.source_taxonomy == mapped),
        )
    ).scalar()
    return mapped if has_data else SOURCE_TAXONOMY_OS


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
        .order_by(LearningDependency.id)
        .all()
    )
    dep_rows = (
        db.query(
            LearningDependency.topic_id,
            LearningDependency.review_status,
        )
        .filter(LearningDependency.prerequisite_id == topic_id)
        .order_by(LearningDependency.id)
        .all()
    )

    prereq_ids = [row.prerequisite_id for row in prereq_rows]
    dep_ids = [row.topic_id for row in dep_rows]

    prereq_topics = {t.id: t for t in list_topics_by_ids(db, prereq_ids, source_taxonomy)}
    dep_topics = {t.id: t for t in list_topics_by_ids(db, dep_ids, source_taxonomy)}

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


def get_cross_subject_bridges(
    db: Session,
    source_taxonomy: str,
    subject: str | None = None,
) -> list[dict]:
    """Compute cross-subject bridge edges between cluster domains.

    Joins ``learning_dependencies`` with ``learning_topics`` twice (for topic
    and prerequisite) and filters where the two topics belong to different
    subjects.  Results are grouped by ``(subject, domain)`` pairs so each row
    represents a bridge between two cluster areas.
    """
    from sqlalchemy.orm import aliased

    TopicAlias = aliased(LearningTopic)
    PrereqAlias = aliased(LearningTopic)

    from_domain = TopicAlias.domain.label("from_cluster_domain")
    from_subject = TopicAlias.subject.label("from_subject")
    to_domain = PrereqAlias.domain.label("to_cluster_domain")
    to_subject = PrereqAlias.subject.label("to_subject")

    query = (
        db.query(
            from_domain,
            from_subject,
            to_domain,
            to_subject,
            sa_func.count().label("edge_count"),
        )
        .join(
            LearningDependency,
            LearningDependency.topic_id == TopicAlias.id,
        )
        .join(
            PrereqAlias,
            LearningDependency.prerequisite_id == PrereqAlias.id,
        )
        .filter(TopicAlias.subject != PrereqAlias.subject)
        .filter(TopicAlias.source_taxonomy == source_taxonomy)
        .filter(PrereqAlias.source_taxonomy == source_taxonomy)
        .group_by(from_domain, from_subject, to_domain, to_subject)
    )
    if subject:
        query = query.filter(TopicAlias.subject == subject)
    rows = query.all()
    return [
        {
            "from_cluster_domain": r.from_cluster_domain,
            "from_subject": r.from_subject,
            "to_cluster_domain": r.to_cluster_domain,
            "to_subject": r.to_subject,
            "edge_count": r.edge_count,
        }
        for r in rows
    ]


def list_clusters_with_topic_counts(
    db: Session,
    subject: str | None = None,
    source_taxonomy: str | None = None,
) -> list[dict]:
    """List clusters enriched with topic counts via GROUP BY.

    Falls back to os-taxonomy clusters when the requested taxonomy has no
    cluster rows (e.g. zh-CN user with Beijing topics but os-taxonomy seed
    clusters).
    """
    effective_taxonomy = source_taxonomy
    if source_taxonomy and source_taxonomy != SOURCE_TAXONOMY_OS:
        # Probe whether any clusters exist for the requested taxonomy.
        has_clusters = db.query(
            exists().where(LearningCluster.source_taxonomy == source_taxonomy)
        ).scalar()
        if not has_clusters:
            effective_taxonomy = SOURCE_TAXONOMY_OS

    topic_count_q = (
        db.query(
            LearningTopic.subject,
            LearningTopic.domain,
            LearningTopic.age_group,
            sa_func.count(LearningTopic.id).label("topic_count"),
        )
        .filter(LearningTopic.deprecated.is_(False))
    )
    if effective_taxonomy:
        topic_count_q = topic_count_q.filter(
            LearningTopic.source_taxonomy == effective_taxonomy
        )
    topic_count_q = topic_count_q.group_by(
        LearningTopic.subject, LearningTopic.domain, LearningTopic.age_group
    )
    counts = {
        (r.subject, r.domain, r.age_group): r.topic_count for r in topic_count_q.all()
    }

    clusters = list_clusters(db, subject=subject, source_taxonomy=effective_taxonomy)

    # ``learning_clusters`` is unique on (subject, domain, age_range_start), so
    # one territory can be stored several times — clusters.json has 183 rows
    # but only 82 distinct (subject, domain, age_group) tuples. Topics are
    # grouped by that 3-key, so every row of a colliding key reports the same
    # topic_count and the client cannot tell them apart; matching by the key
    # then leaves all but the first row with no nodes at all.
    #
    # Collapse to one row per 3-key here so the contract is unique by
    # construction. The representative keeps the lowest age_range_start (the
    # entry the territory begins at) and the count for the key, counted once.
    collapsed: dict[tuple[str, str | None, str], dict] = {}
    for c in clusters:
        key = (c.subject, c.domain, c.age_group)
        count = counts.get(key, 0)
        existing = collapsed.get(key)
        if existing is None:
            collapsed[key] = {
                "id": c.id,
                "subject": c.subject,
                "domain": c.domain,
                "age_range_start": c.age_range_start,
                "age_group": c.age_group,
                "summary": c.summary,
                "topic_count": count,
            }
            continue
        start = c.age_range_start
        if start is not None and (
            existing["age_range_start"] is None or start < existing["age_range_start"]
        ):
            existing["age_range_start"] = start
            existing["summary"] = c.summary or existing["summary"]
        elif not existing["summary"] and c.summary:
            existing["summary"] = c.summary

    return list(collapsed.values())


def list_subjects(
    db: Session, source_taxonomy: str | None = None
) -> list[dict]:
    """List all non-deprecated subjects with their topic counts."""
    q = (
        db.query(
            LearningTopic.subject,
            sa_func.count(LearningTopic.id).label("topic_count"),
        )
        .filter(LearningTopic.deprecated.is_(False))
    )
    if source_taxonomy:
        q = q.filter(LearningTopic.source_taxonomy == source_taxonomy)
    rows = q.group_by(LearningTopic.subject).order_by(LearningTopic.subject).all()
    return [{"subject": r.subject, "topic_count": r.topic_count} for r in rows]
