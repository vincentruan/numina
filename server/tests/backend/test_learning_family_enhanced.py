"""Tests for enhanced parent learning endpoints (U8)."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.stats import ChildLearningStats
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def parent_children_family(db: Session, client, auth_headers):
    """Create parent auth + two children with stats via API."""
    from packages.db.models.user import User

    # Create two children
    child_ids = []
    for name in ["Kid1", "Kid2"]:
        resp = client.post(
            "/api/v1/family/children",
            headers=auth_headers,
            json={
                "username": f"u8child_{name}",
                "password": "ChildPass1",
                "display_name": name,
                "avatar_color": "#FF5733",
                "pin": ["🐱", "🌟", "🎈", "🐶"],
            },
        )
        assert resp.status_code == 201
        child_ids.append(int(resp.json()["data"]["id"]))

    # Add stats for first child
    child1 = db.query(User).filter(User.id == child_ids[0]).first()
    stats = ChildLearningStats(
        child_id=child_ids[0],
        family_id=child1.family_id,
        cumulative_xp=250,
        level=3,
        learning_streak_days=5,
    )
    db.add(stats)
    db.flush()

    return {"child_ids": child_ids, "client": client, "auth_headers": auth_headers}


@pytest.fixture
def topic_for_sessions(db: Session):
    """Create a topic for session tests."""
    t = LearningTopic(
        topic_key="u8_test_topic",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="U8 Test Topic",
        name_zh="测试知识点",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


class TestListChildrenEnhanced:
    def test_includes_xp_level_streak(self, db: Session, parent_children_family):
        resp = parent_children_family["client"].get(
            "/api/v1/family/learning/children",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

        # First child has stats
        child1_data = next(c for c in data if int(c["child_id"]) == parent_children_family["child_ids"][0])
        assert child1_data["cumulative_xp"] == 250
        assert child1_data["level"] == 3
        assert child1_data["learning_streak_days"] == 5

        # Second child has defaults
        child2_data = next(c for c in data if int(c["child_id"]) == parent_children_family["child_ids"][1])
        assert child2_data["cumulative_xp"] == 0
        assert child2_data["level"] == 1
        assert child2_data["learning_streak_days"] == 0


class TestChildSessionLog:
    def test_returns_session_history(
        self, db: Session, parent_children_family, topic_for_sessions
    ):
        from datetime import UTC, datetime

        child_id = parent_children_family["child_ids"][0]
        session = LearningSession(
            child_id=child_id,
            topic_id=topic_for_sessions.id,
            session_type="tutorial",
            started_at=datetime.now(UTC),
            duration_seconds=300,
            score=0.85,
        )
        db.add(session)
        db.flush()

        resp = parent_children_family["client"].get(
            f"/api/v1/family/learning/children/{child_id}/sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1
        assert data[0]["topic_name"] == "U8 Test Topic"

    def test_rejects_cross_family_access(self, db: Session, parent_children_family):
        resp = parent_children_family["client"].get(
            "/api/v1/family/learning/children/9999999/sessions",
            headers=parent_children_family["auth_headers"],
        )
        assert resp.status_code in (400, 403, 404)
