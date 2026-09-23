"""Tests for learning topic service."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.topic_service import (
    get_topic_by_id,
    get_topic_graph,
    list_clusters,
    list_subjects,
    list_topics,
)
from packages.db.models.learning.topic import (
    LearningCluster,
    LearningDependency,
    LearningTopic,
)


@pytest.fixture
def sample_topics(db: Session):
    """Create two math topics with a dependency."""
    t1 = LearningTopic(
        topic_key="mt_001",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="Fraction basics",
        description="Intro to fractions",
        age_range_start=8,
        age_range_end=10,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    t2 = LearningTopic(
        topic_key="mt_002",
        topic_type="PROCEDURAL",
        subject="mathematics",
        domain="Fractions",
        name="Fraction addition",
        description="Adding fractions",
        age_range_start=9,
        age_range_end=11,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add_all([t1, t2])
    db.flush()
    dep = LearningDependency(
        topic_id=t2.id,
        prerequisite_id=t1.id,
        strength="hard",
        reason="Must know basics",
    )
    db.add(dep)
    db.flush()
    return t1, t2


@pytest.fixture
def sample_cluster(db: Session):
    """Create a learning cluster."""
    c = LearningCluster(
        subject="mathematics",
        domain="Fractions",
        age_group="mid",
        summary="Learn fractions step by step",
    )
    db.add(c)
    db.flush()
    return c


def test_list_topics_by_subject(db: Session, sample_topics):
    results = list_topics(db, subject="mathematics")
    assert len(results) == 2


def test_list_topics_by_age_group(db: Session, sample_topics):
    results = list_topics(db, age_group="mid")
    assert len(results) == 2


def test_list_topics_by_domain(db: Session, sample_topics):
    results = list_topics(db, domain="Fractions")
    assert len(results) == 2


def test_list_topics_excludes_deprecated(db: Session, sample_topics):
    results = list_topics(db, deprecated=False)
    assert len(results) == 2
    results = list_topics(db, deprecated=True)
    assert len(results) == 0


def test_get_topic_by_id(db: Session, sample_topics):
    t1, _ = sample_topics
    result = get_topic_by_id(db, t1.id)
    assert result is not None
    assert result.topic_key == "mt_001"


def test_get_topic_by_id_not_found(db: Session):
    result = get_topic_by_id(db, 99999)
    assert result is None


def test_get_topic_graph(db: Session, sample_topics):
    _, t2 = sample_topics
    graph = get_topic_graph(db, t2.id)
    assert graph is not None
    assert len(graph["prerequisites"]) == 1
    assert graph["prerequisites"][0].topic_key == "mt_001"
    assert len(graph["dependents"]) == 0


def test_get_topic_graph_not_found(db: Session):
    result = get_topic_graph(db, 99999)
    assert result is None


def test_list_clusters(db: Session, sample_cluster):
    results = list_clusters(db)
    assert len(results) == 1
    assert results[0].subject == "mathematics"


def test_list_clusters_by_subject(db: Session, sample_cluster):
    results = list_clusters(db, subject="mathematics")
    assert len(results) == 1
    results = list_clusters(db, subject="science")
    assert len(results) == 0


def test_list_subjects(db: Session, sample_topics):
    subjects = list_subjects(db)
    assert len(subjects) == 1
    assert subjects[0]["subject"] == "mathematics"
    assert subjects[0]["topic_count"] == 2


def test_list_subjects_empty(db: Session):
    subjects = list_subjects(db)
    assert subjects == []
