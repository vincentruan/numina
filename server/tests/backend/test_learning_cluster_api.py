"""Tests for cluster API and cross-subject bridge endpoints (U1)."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import (
    LearningCluster,
    LearningDependency,
    LearningTopic,
)
from tests.backend.conftest import child_login_two_phase

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic(
    db: Session,
    *,
    key: str,
    subject: str,
    domain: str,
    source_taxonomy: str = "os-taxonomy",
    age_group: str = "mid",
) -> LearningTopic:
    t = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject=subject,
        domain=domain,
        name=key,
        description="",
        age_group=age_group,
        source_taxonomy=source_taxonomy,
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    return t


def _make_cluster(
    db: Session,
    *,
    subject: str,
    domain: str,
    source_taxonomy: str = "os-taxonomy",
) -> LearningCluster:
    c = LearningCluster(
        subject=subject,
        domain=domain,
        age_range_start=6,
        age_group="mid",
        summary=f"{domain} cluster",
        source_taxonomy=source_taxonomy,
    )
    db.add(c)
    return c


@pytest.fixture
def child_auth_headers(client, auth_headers):
    """Create a child user and return two-phase auth headers."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "clusterchild",
            "password": CHILD_PASSWORD,
            "display_name": "Cluster Learner",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    token = child_login_two_phase(client, "clusterchild", CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def seed_data(db: Session):
    """Create topics across two subjects with clusters and cross-subject deps."""
    # Use "beijing" taxonomy because the test child's language defaults to zh-CN
    TAX = "beijing"

    # Math topics + cluster
    math_t1 = _make_topic(db, key="math-add", subject="mathematics", domain="Addition", source_taxonomy=TAX)
    math_t2 = _make_topic(db, key="math-sub", subject="mathematics", domain="Subtraction", source_taxonomy=TAX)
    math_t3 = _make_topic(db, key="math-mul", subject="mathematics", domain="Multiplication", source_taxonomy=TAX)
    _make_cluster(db, subject="mathematics", domain="Addition", source_taxonomy=TAX)
    _make_cluster(db, subject="mathematics", domain="Subtraction", source_taxonomy=TAX)
    _make_cluster(db, subject="mathematics", domain="Multiplication", source_taxonomy=TAX)

    # Science topics + cluster
    sci_t1 = _make_topic(db, key="sci-units", subject="science", domain="Units", source_taxonomy=TAX)
    sci_t2 = _make_topic(db, key="sci-force", subject="science", domain="Forces", source_taxonomy=TAX)
    _make_cluster(db, subject="science", domain="Units", source_taxonomy=TAX)
    _make_cluster(db, subject="science", domain="Forces", source_taxonomy=TAX)

    db.flush()

    # Cross-subject dependency: sci-units depends on math-add (math → science bridge)
    dep = LearningDependency(
        topic_id=sci_t1.id,
        prerequisite_id=math_t1.id,
        strength="hard",
    )
    db.add(dep)
    # Intra-subject dependency (should NOT appear in bridges)
    dep2 = LearningDependency(
        topic_id=math_t2.id,
        prerequisite_id=math_t1.id,
        strength="hard",
    )
    db.add(dep2)
    db.commit()

    return {
        "math_topics": [math_t1, math_t2, math_t3],
        "sci_topics": [sci_t1, sci_t2],
    }


# ---------------------------------------------------------------------------
# GET /clusters
# ---------------------------------------------------------------------------


class TestListClusters:
    def test_returns_all_clusters(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/clusters", headers=child_auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # 3 math + 2 science = 5
        assert len(data) == 5

    def test_filter_by_subject(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/clusters?subject=mathematics",
            headers=child_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        assert all(c["subject"] == "mathematics" for c in data)

    def test_includes_topic_count(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/clusters?subject=mathematics",
            headers=child_auth_headers,
        )
        data = resp.json()["data"]
        counts = {c["domain"]: c["topic_count"] for c in data}
        assert counts["Addition"] == 1
        assert counts["Subtraction"] == 1
        assert counts["Multiplication"] == 1

    def test_empty_for_unknown_subject(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/clusters?subject=art",
            headers=child_auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data == []

    def test_taxonomy_filtering(self, client, child_auth_headers, seed_data, db):
        """Clusters from a different taxonomy should not appear."""
        _make_cluster(db, subject="mathematics", domain="Alien", source_taxonomy="os-taxonomy")
        db.commit()
        resp = client.get(
            "/api/v1/child/learning/clusters", headers=child_auth_headers
        )
        data = resp.json()["data"]
        domains = [c["domain"] for c in data]
        assert "Alien" not in domains
        # beijing clusters from seed_data should appear
        assert "Addition" in domains


# ---------------------------------------------------------------------------
# GET /bridges
# ---------------------------------------------------------------------------


class TestListBridges:
    def test_returns_cross_subject_bridges(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/bridges", headers=child_auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # science/Units → mathematics/Addition (1 edge)
        assert len(data) == 1
        bridge = data[0]
        assert bridge["from_subject"] == "science"
        assert bridge["from_cluster_domain"] == "Units"
        assert bridge["to_subject"] == "mathematics"
        assert bridge["to_cluster_domain"] == "Addition"
        assert bridge["edge_count"] == 1

    def test_filter_by_subject(self, client, child_auth_headers, seed_data):
        resp = client.get(
            "/api/v1/child/learning/bridges?subject=science",
            headers=child_auth_headers,
        )
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["from_subject"] == "science"

    def test_empty_when_no_cross_edges(self, client, child_auth_headers, db):
        """A subject with only intra-subject deps should return no bridges."""
        t1 = _make_topic(db, key="eng-a", subject="english", domain="Grammar", source_taxonomy="beijing")
        t2 = _make_topic(db, key="eng-b", subject="english", domain="Vocab", source_taxonomy="beijing")
        db.flush()
        db.add(
            LearningDependency(topic_id=t2.id, prerequisite_id=t1.id, strength="hard")
        )
        db.commit()
        resp = client.get(
            "/api/v1/child/learning/bridges?subject=english",
            headers=child_auth_headers,
        )
        data = resp.json()["data"]
        assert data == []

    def test_excludes_intra_subject_edges(self, client, child_auth_headers, seed_data):
        """The math→math dependency should not appear in bridges."""
        resp = client.get(
            "/api/v1/child/learning/bridges", headers=child_auth_headers
        )
        data = resp.json()["data"]
        for bridge in data:
            assert bridge["from_subject"] != bridge["to_subject"]
