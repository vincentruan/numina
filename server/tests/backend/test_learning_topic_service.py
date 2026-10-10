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
    assert graph["prerequisites"][0]["topic"].topic_key == "mt_001"
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


# ── review_status on graph edges ─────────────────────────────────────────────


@pytest.fixture
def review_status_topics(db: Session):
    """Three topics: one reviewed prereq, one machine prereq, one os-taxonomy (None)."""
    t_main = LearningTopic(
        topic_key="mt_main",
        topic_type="PROCEDURAL",
        subject="mathematics",
        domain="Fractions",
        name="Main topic",
        description="Has multiple prereqs",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    t_reviewed = LearningTopic(
        topic_key="mt_reviewed",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="Reviewed prereq",
        description="Human-reviewed",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    t_machine = LearningTopic(
        topic_key="mt_machine",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="Machine prereq",
        description="AI-generated",
        age_group="mid",
        source_taxonomy="beijing",
        evidence_json="[]",
        standards_json="[]",
    )
    t_os = LearningTopic(
        topic_key="mt_os",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="OS taxonomy prereq",
        description="No review status",
        age_group="mid",
        source_taxonomy="os-taxonomy",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add_all([t_main, t_reviewed, t_machine, t_os])
    db.flush()

    # Edges with different review_status values
    db.add(
        LearningDependency(
            topic_id=t_main.id,
            prerequisite_id=t_reviewed.id,
            review_status="reviewed",
            strength="hard",
            reason="Must know first",
        )
    )
    db.add(
        LearningDependency(
            topic_id=t_main.id,
            prerequisite_id=t_machine.id,
            review_status="machine",
            strength="soft",
            reason="Suggested",
        )
    )
    db.add(
        LearningDependency(
            topic_id=t_main.id,
            prerequisite_id=t_os.id,
            review_status=None,  # os-taxonomy edges carry no review status
            strength="hard",
            reason="Foundation",
        )
    )
    db.flush()
    return t_main, t_reviewed, t_machine, t_os


def test_graph_exposes_reviewed_edge_status(db: Session, review_status_topics):
    """A prerequisite edge with review_status='reviewed' returns that value."""
    t_main, t_reviewed, _, _ = review_status_topics
    graph = get_topic_graph(db, t_main.id)
    assert graph is not None

    reviewed_edge = next(
        e for e in graph["prerequisites"] if e["topic"].topic_key == "mt_reviewed"
    )
    assert reviewed_edge["review_status"] == "reviewed"


def test_graph_exposes_machine_edge_status(db: Session, review_status_topics):
    """A machine-generated edge returns review_status='machine'."""
    t_main, _, t_machine, _ = review_status_topics
    graph = get_topic_graph(db, t_main.id)

    machine_edge = next(
        e for e in graph["prerequisites"] if e["topic"].topic_key == "mt_machine"
    )
    assert machine_edge["review_status"] == "machine"


def test_graph_exposes_null_review_status_for_os_taxonomy(
    db: Session, review_status_topics
):
    """An os-taxonomy edge with no review_status returns None."""
    t_main, _, _, t_os = review_status_topics
    graph = get_topic_graph(db, t_main.id)

    os_edge = next(e for e in graph["prerequisites"] if e["topic"].topic_key == "mt_os")
    assert os_edge["review_status"] is None


def test_graph_edge_ordering_matches_fixture(db: Session, review_status_topics):
    """Edge ordering preserves the dependency query order."""
    t_main, t_reviewed, t_machine, t_os = review_status_topics
    graph = get_topic_graph(db, t_main.id)

    # The order should match the insertion order in the fixture
    edge_keys = [e["topic"].topic_key for e in graph["prerequisites"]]
    assert edge_keys == ["mt_reviewed", "mt_machine", "mt_os"]


def test_graph_source_taxonomy_filter_excludes_cross_source_edges(
    db: Session, review_status_topics
):
    """source_taxonomy filter excludes edges from other taxonomies."""
    t_main, _, _, _ = review_status_topics

    # Filter to beijing only — should exclude the os-taxonomy edge
    graph_bj = get_topic_graph(db, t_main.id, source_taxonomy="beijing")
    assert graph_bj is not None
    edge_keys = [e["topic"].topic_key for e in graph_bj["prerequisites"]]
    assert "mt_os" not in edge_keys
    assert "mt_reviewed" in edge_keys
    assert "mt_machine" in edge_keys

    # Filter to os-taxonomy only — should exclude beijing edges
    graph_os = get_topic_graph(db, t_main.id, source_taxonomy="os-taxonomy")
    assert graph_os is not None
    edge_keys_os = [e["topic"].topic_key for e in graph_os["prerequisites"]]
    assert edge_keys_os == ["mt_os"]


def test_graph_ae3_mixed_review_statuses(db: Session, review_status_topics):
    """AE3: A topic with reviewed + machine prereqs returns both with distinct statuses."""
    t_main, _, _, _ = review_status_topics
    graph = get_topic_graph(db, t_main.id)

    assert len(graph["prerequisites"]) == 3

    statuses = {
        e["topic"].topic_key: e["review_status"] for e in graph["prerequisites"]
    }
    assert statuses["mt_reviewed"] == "reviewed"
    assert statuses["mt_machine"] == "machine"
    assert statuses["mt_os"] is None

    # Verify distinct statuses
    assert len({statuses["mt_reviewed"], statuses["mt_machine"]}) == 2
