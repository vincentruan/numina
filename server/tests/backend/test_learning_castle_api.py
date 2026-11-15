"""Tests for GET /child/learning/castle/index (U2)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic
from tests.backend.conftest import child_login_two_phase

PIN = ["🐱", "🌟", "🎈", "🐶"]
CHILD_PASSWORD = "ChildPass1"

CASTLE_URL = "/api/v1/child/learning/castle/index"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_topic(
    db: Session,
    *,
    key: str,
    subject: str,
    domain: str,
    age_range_start: int = 6,
    age_range_end: int = 10,
    age_group: str = "mid",
    source_taxonomy: str = "os-taxonomy",
    centrality: float = 50.0,
) -> LearningTopic:
    t = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject=subject,
        domain=domain,
        name=key,
        name_zh=f"中文{key}",
        description="",
        age_range_start=age_range_start,
        age_range_end=age_range_end,
        age_group=age_group,
        centrality=centrality,
        source_taxonomy=source_taxonomy,
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def castle_child(db: Session, client, auth_headers):
    """Create a 9-year-old child and log in; returns (child_id, headers)."""
    from packages.db.models.user import User

    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "castleapi",
            "password": CHILD_PASSWORD,
            "display_name": "Castle API Kid",
            "avatar_color": "#FF5733",
            "pin": PIN,
        },
    )
    assert resp.status_code == 201
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 6, 1)
    db.flush()

    token = child_login_two_phase(client, "castleapi", CHILD_PASSWORD, PIN)
    return child_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def castle_topics(db: Session):
    """Two in-range maths topics + one out-of-range topic."""
    t1 = _make_topic(db, key="api_castle_m1", subject="mathematics", domain="Algebra")
    t2 = _make_topic(db, key="api_castle_m2", subject="mathematics", domain="Geometry")
    t3 = _make_topic(
        db,
        key="api_castle_out",
        subject="science",
        domain="OutOfRange",
        age_range_start=2,
        age_range_end=3,
    )
    db.flush()
    return {"in_range": [t1, t2], "out_of_range": [t3]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCastleIndexEndpoint:
    def test_zero_progress_returns_200_with_towers(
        self, client, castle_child, castle_topics
    ):
        """Zero-progress child gets 200 + tower skeletons, never 404."""
        _, headers = castle_child
        resp = client.get(CASTLE_URL, headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["towers"]) > 0
        assert data["windows"] == []
        assert data["streak_days"] >= 0

    def test_response_envelope_and_shape(self, client, castle_child, castle_topics):
        """Response has {data} envelope with expected keys."""
        _, headers = castle_child
        resp = client.get(CASTLE_URL, headers=headers)
        body = resp.json()
        assert "data" in body
        data = body["data"]
        assert set(data.keys()) == {"towers", "windows", "streak_days"}

        tower = data["towers"][0]
        assert {
            "subject",
            "mastered_count",
            "learning_count",
            "review_due_count",
            "total_count",
            "floors",
        } <= set(tower.keys())
        floor = tower["floors"][0]
        assert {
            "domain",
            "mastered_count",
            "learning_count",
            "review_due_count",
            "total_count",
        } <= set(floor.keys())

    def test_topic_id_serialized_as_string(
        self, client, db, castle_child, castle_topics
    ):
        """Window topic_id is a string (snowflake serialization)."""
        child_id, headers = castle_child
        t = castle_topics["in_range"][0]
        db.add(
            LearningProgress(
                child_id=child_id,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=30),
                next_review_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.flush()

        resp = client.get(CASTLE_URL, headers=headers)
        windows = resp.json()["data"]["windows"]
        assert len(windows) >= 1
        assert isinstance(windows[0]["topic_id"], str)
        assert windows[0]["topic_id"] == str(t.id)

    def test_review_due_floor_count(self, client, db, castle_child, castle_topics):
        """An overdue mastered topic increments review_due_count."""
        child_id, headers = castle_child
        t = castle_topics["in_range"][0]
        db.add(
            LearningProgress(
                child_id=child_id,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=30),
                next_review_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.flush()

        resp = client.get(CASTLE_URL, headers=headers)
        towers = resp.json()["data"]["towers"]
        math = next(t for t in towers if t["subject"] == "mathematics")
        assert math["review_due_count"] == 1

    def test_window_carries_subject_and_domain(
        self, client, db, castle_child, castle_topics
    ):
        """Each window's subject/domain matches an existing tower/floor."""
        child_id, headers = castle_child
        t = castle_topics["in_range"][0]
        db.add(
            LearningProgress(
                child_id=child_id,
                topic_id=t.id,
                mastery_level="mastered",
                first_mastered_at=datetime.now(UTC) - timedelta(days=30),
                next_review_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
        db.flush()

        data = client.get(CASTLE_URL, headers=headers).json()["data"]
        subject_domains = {
            (tower["subject"], floor["domain"])
            for tower in data["towers"]
            for floor in tower["floors"]
        }
        for w in data["windows"]:
            assert (w["subject"], w["domain"]) in subject_domains

    def test_other_taxonomy_excluded(self, client, db, castle_child):
        """Topics from another taxonomy do not appear."""
        child_id, headers = castle_child
        # Pin the child to en-US so the effective taxonomy is os-taxonomy even
        # after a beijing row exists (zh-CN maps to beijing and would flip).
        from packages.db.models.user import User

        db.query(User).filter(User.id == child_id).update({"language": "en-US"})
        _make_topic(
            db,
            key="api_castle_beijing",
            subject="mathematics",
            domain="BeijingDomain",
            source_taxonomy="beijing",
        )
        db.flush()

        data = client.get(CASTLE_URL, headers=headers).json()["data"]
        domains = [f["domain"] for t in data["towers"] for f in t["floors"]]
        assert "BeijingDomain" not in domains

    def test_requires_child_auth(self, client):
        """Non-child callers are rejected."""
        resp = client.get(CASTLE_URL)
        assert resp.status_code in (401, 403)

    def test_streak_days_matches_stats(self, client, castle_child, castle_topics):
        """streak_days is present and consistent with the stats endpoint."""
        _, headers = castle_child
        castle = client.get(CASTLE_URL, headers=headers).json()["data"]
        stats = client.get("/api/v1/child/learning/stats", headers=headers).json()[
            "data"
        ]
        assert castle["streak_days"] == stats["learning_streak_days"]
