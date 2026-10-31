"""Bootstrap learning topics, dependencies, and clusters from os-taxonomy.

Idempotent: safe to run on every startup. If topics already exist, the
UPSERT only updates mutable fields. Dependencies and clusters are
inserted only if the edge/group doesn't already exist.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from packages.core.logging import get_logger

logger = get_logger(__name__)

# os-taxonomy subject title -> DB subject slug
_SUBJECT_MAP = {
    "Mathematics": "mathematics",
    "Science": "science",
    "English": "english",
    "History": "history",
    "Personal & Social Development": "personal_social",
    "Life Skills": "life_skills",
    "Computing": "computing",
    "Learning to Learn": "learning_to_learn",
}

SOURCE_OSTAX = "os-taxonomy"


def _normalize_subject(raw: str) -> str:
    return _SUBJECT_MAP.get(raw, raw.lower().replace(" & ", "_").replace(" ", "_"))


def _has_topics(session: Session) -> bool:
    """Return True if the learning_topics table has any os-taxonomy rows."""
    from packages.db.models.learning.topic import LearningTopic

    return (
        session.query(LearningTopic.id)
        .filter(LearningTopic.source_taxonomy == SOURCE_OSTAX)
        .first()
        is not None
    )


def bootstrap_learning_topics(session: Session) -> None:
    """Seed learning topics, dependencies, and clusters if not already present.

    Uses the OsTaxonomyLoader from packages/os_taxonomy which bundles JSON data
    inside the package directory — available in Docker without extra COPY.
    """
    if _has_topics(session):
        logger.debug("Learning topics already seeded, skipping")
        return

    from packages.db.models.learning.topic import (
        LearningCluster,
        LearningDependency,
        LearningTopic,
    )
    from packages.os_taxonomy.loaders.os_taxonomy import OsTaxonomyLoader

    loader = OsTaxonomyLoader()
    topics = loader.load_topics()
    deps = loader.load_dependencies()
    clusters = loader.load_clusters()

    # 1. Upsert topics
    topic_count = 0
    for t in topics:
        existing = (
            session.query(LearningTopic)
            .filter_by(topic_key=t.topic_key, source_taxonomy=t.source_taxonomy)
            .first()
        )
        if existing:
            existing.name = t.name
            existing.name_zh = t.name_zh
            existing.description = t.description
            existing.description_zh = t.description_zh
            existing.age_range_start = t.age_range_start
            existing.age_range_end = t.age_range_end
            existing.centrality = t.centrality
            existing.evidence_json = json.dumps(t.evidence)
            existing.standards_json = json.dumps(t.standards)
            existing.assessment_prompt = t.assessment_prompt
            existing.age_group = t.age_group
        else:
            session.add(
                LearningTopic(
                    topic_key=t.topic_key,
                    topic_type=t.topic_type,
                    subject=_normalize_subject(t.subject),
                    domain=t.domain,
                    name=t.name,
                    name_zh=t.name_zh,
                    description=t.description,
                    description_zh=t.description_zh,
                    age_range_start=t.age_range_start,
                    age_range_end=t.age_range_end,
                    centrality=t.centrality,
                    evidence_json=json.dumps(t.evidence),
                    standards_json=json.dumps(t.standards),
                    assessment_prompt=t.assessment_prompt,
                    age_group=t.age_group,
                    source_taxonomy=t.source_taxonomy,
                )
            )
            topic_count += 1
    session.flush()

    # 2. Insert dependencies (resolve topic_key → id)
    key_map: dict[str, int] = dict(
        session.query(LearningTopic.topic_key, LearningTopic.id)
        .filter(LearningTopic.source_taxonomy == SOURCE_OSTAX)
        .all()
    )

    dep_count = 0
    for d in deps:
        topic_id = key_map.get(d.topic_key)
        prereq_id = key_map.get(d.prerequisite_key)
        if topic_id is None or prereq_id is None:
            continue
        existing = (
            session.query(LearningDependency)
            .filter_by(topic_id=topic_id, prerequisite_id=prereq_id)
            .first()
        )
        if not existing:
            session.add(
                LearningDependency(
                    topic_id=topic_id,
                    prerequisite_id=prereq_id,
                    strength=d.strength,
                    reason=d.reason,
                )
            )
            dep_count += 1
    session.flush()

    # 3. Insert clusters
    cluster_count = 0
    for c in clusters:
        existing = (
            session.query(LearningCluster)
            .filter_by(
                subject=_normalize_subject(c.subject),
                domain=c.domain,
                age_range_start=c.age_range_start,
                source_taxonomy=c.source_taxonomy,
            )
            .first()
        )
        if not existing:
            session.add(
                LearningCluster(
                    subject=_normalize_subject(c.subject),
                    domain=c.domain,
                    age_range_start=c.age_range_start,
                    age_group=c.age_group,
                    summary=c.summary,
                    source_taxonomy=c.source_taxonomy,
                )
            )
            cluster_count += 1
    session.flush()

    logger.info(
        "Learning OS seeded: %d topics, %d dependencies, %d clusters",
        topic_count,
        dep_count,
        cluster_count,
    )
