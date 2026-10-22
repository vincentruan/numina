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
# GET /map — navigation index (subject/domain/age_group joined in)
# ---------------------------------------------------------------------------


class TestMapNavigationIndex:
    def test_map_carries_subject_domain_age_group(
        self, client, child_auth_headers, db
    ):
        """The map index lets the client build tabs without topic detail."""

        from packages.db.models.learning.progress import LearningProgress

        t = _make_topic(
            db, key="idx-topic", subject="mathematics", domain="Addition",
            source_taxonomy="beijing",
        )
        db.flush()
        from apps.backend.app.models.user import User

        child = db.query(User).filter(User.username == "clusterchild").first()
        db.add(
            LearningProgress(
                child_id=child.id, topic_id=t.id, mastery_level="available"
            )
        )
        db.commit()

        resp = client.get("/api/v1/child/learning/map", headers=child_auth_headers)
        assert resp.status_code == 200
        rows = resp.json()["data"]
        target = next(r for r in rows if r["topic_id"] == str(t.id))
        assert target["subject"] == "mathematics"
        assert target["domain"] == "Addition"
        assert target["age_group"] == "mid"


class TestClusterRowCollapse:
    """clusters.json stores 183 rows over only 82 (subject, domain, age_group)
    tuples. The endpoint must return one row per match key, or the client
    renders duplicate territories whose nodes can only land in the first."""

    def test_collapses_rows_sharing_a_match_key(self, client, child_auth_headers, db):
        # Three stored rows, same (subject, domain, age_group) — as the seeder
        # produces when several clusters.json entries bucket into one age_group.
        for start in (5, 8, 11):
            db.add(
                LearningCluster(
                    subject="mathematics",
                    domain="Addition",
                    age_range_start=start,
                    age_group="low",
                    summary=f"ages {start}+",
                    source_taxonomy="beijing",
                )
            )
        db.commit()

        resp = client.get(
            "/api/v1/child/learning/clusters?subject=mathematics",
            headers=child_auth_headers,
        )
        assert resp.status_code == 200
        rows = [r for r in resp.json()["data"] if r["domain"] == "Addition"]
        assert len(rows) == 1, "colliding rows must collapse to one territory"
        # The representative starts at the earliest age the territory covers.
        assert rows[0]["age_range_start"] == 5

    def test_collapsed_count_is_the_key_total_once(
        self, client, child_auth_headers, db
    ):
        db.add(
            LearningCluster(
                subject="mathematics", domain="Addition", age_range_start=5,
                age_group="low", summary="a", source_taxonomy="beijing",
            )
        )
        db.add(
            LearningCluster(
                subject="mathematics", domain="Addition", age_range_start=8,
                age_group="low", summary="b", source_taxonomy="beijing",
            )
        )
        t = _make_topic(
            db, key="collapse-topic", subject="mathematics", domain="Addition",
            source_taxonomy="beijing", age_group="low",
        )
        db.flush()
        from apps.backend.app.models.user import User  # noqa: F401  (ensure mapper)
        db.commit()
        assert t.id

        resp = client.get(
            "/api/v1/child/learning/clusters?subject=mathematics",
            headers=child_auth_headers,
        )
        rows = [r for r in resp.json()["data"] if r["domain"] == "Addition"]
        assert len(rows) == 1
        # Counted once for the key, not repeated per stored row.
        assert rows[0]["topic_count"] == 1


class TestMapIndex:
    """The slim /map/index payload the cluster map actually loads."""

    def _seed_progress(self, db, child_username="clusterchild"):
        from apps.backend.app.models.user import User
        from packages.db.models.learning.progress import LearningProgress

        t = _make_topic(
            db, key="slim-topic", subject="mathematics", domain="Addition",
            source_taxonomy="beijing",
        )
        other = _make_topic(
            db, key="slim-topic-other-tax", subject="mathematics", domain="Addition",
            source_taxonomy="os-taxonomy",
        )
        db.flush()
        child = db.query(User).filter(User.username == child_username).first()
        db.add(LearningProgress(child_id=child.id, topic_id=t.id, mastery_level="learning"))
        db.add(LearningProgress(child_id=child.id, topic_id=other.id, mastery_level="available"))
        db.commit()
        return t

    def test_rows_carry_map_fields(self, client, child_auth_headers, db):
        t = self._seed_progress(db)
        resp = client.get(
            "/api/v1/child/learning/map/index", headers=child_auth_headers
        )
        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert len(rows) == 1, "other-taxonomy progress must be filtered out"
        row = rows[0]
        assert row["topic_id"] == str(t.id)
        assert row["mastery_level"] == "learning"
        assert row["subject"] == "mathematics"
        assert row["domain"] == "Addition"
        assert row["age_group"] == "mid"
        assert "next_review_at" in row

    def test_payload_omits_heavy_fields(self, client, child_auth_headers, db):
        """The slim index must not carry the fields that blow the 3G budget."""
        self._seed_progress(db)
        resp = client.get(
            "/api/v1/child/learning/map/index", headers=child_auth_headers
        )
        row = resp.json()["data"][0]
        for heavy in ("ability_dimensions_score", "evidence", "id", "child_id"):
            assert heavy not in row

    def test_is_smaller_than_full_map(self, client, child_auth_headers, db):
        self._seed_progress(db)
        slim = client.get(
            "/api/v1/child/learning/map/index", headers=child_auth_headers
        )
        full = client.get("/api/v1/child/learning/map", headers=child_auth_headers)
        assert slim.status_code == 200 and full.status_code == 200
        assert len(slim.content) < len(full.content)


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

    def test_response_includes_source_type(self, client, child_auth_headers, seed_data):
        """Bridge response should include source_type and max_confidence fields."""
        resp = client.get(
            "/api/v1/child/learning/bridges", headers=child_auth_headers
        )
        data = resp.json()["data"]
        assert len(data) >= 1
        bridge = data[0]
        assert "source_type" in bridge
        assert "max_confidence" in bridge
        assert bridge["source_type"] in ("explicit", "inferred", "mixed")
        assert isinstance(bridge["max_confidence"], float)

    def test_explicit_bridge_source_type(self, client, child_auth_headers, db):
        """Explicit-only edges should report source_type='explicit'."""
        t1 = _make_topic(
            db, key="exp-a", subject="science", domain="Units",
            source_taxonomy="beijing",
        )
        t2 = _make_topic(
            db, key="exp-b", subject="mathematics", domain="Addition",
            source_taxonomy="beijing",
        )
        db.flush()
        db.add(
            LearningDependency(
                topic_id=t1.id, prerequisite_id=t2.id, strength="hard",
                source_type="explicit",
            )
        )
        db.commit()
        resp = client.get(
            "/api/v1/child/learning/bridges?subject=science",
            headers=child_auth_headers,
        )
        data = resp.json()["data"]
        matching = [
            b for b in data
            if b["from_subject"] == "science" and b["to_subject"] == "mathematics"
        ]
        assert len(matching) == 1
        assert matching[0]["source_type"] == "explicit"
        assert matching[0]["max_confidence"] == 1.0

    def test_inferred_bridge_source_type(self, client, child_auth_headers, db):
        """Inferred-only edges should report source_type='inferred' with confidence."""
        t1 = _make_topic(
            db, key="inf-a", subject="science", domain="Energy",
            source_taxonomy="beijing",
        )
        t2 = _make_topic(
            db, key="inf-b", subject="history", domain="Ancient Egypt",
            source_taxonomy="beijing",
        )
        db.flush()
        db.add(
            LearningDependency(
                topic_id=t1.id, prerequisite_id=t2.id, strength="soft",
                source_type="inferred", confidence=0.72,
            )
        )
        db.commit()
        resp = client.get(
            "/api/v1/child/learning/bridges?subject=science",
            headers=child_auth_headers,
        )
        data = resp.json()["data"]
        matching = [
            b for b in data
            if b["from_subject"] == "science" and b["to_subject"] == "history"
        ]
        assert len(matching) == 1
        assert matching[0]["source_type"] == "inferred"
        assert matching[0]["max_confidence"] == pytest.approx(0.72)
