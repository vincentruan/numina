"""Tests for zone-based recommendation service."""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.zone_service import (
    get_child_age_group,
    get_child_zone,
    get_comfort_zone_age_group,
    get_growth_zone_age_group,
    get_zone_for_topic,
    get_zone_recommended_topic,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def child_with_birthday(db: Session, client, auth_headers):
    """Create a child via API and set birthday for age_group testing."""
    from packages.db.models.user import User

    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "zonechild",
            "password": "ChildPass1",
            "display_name": "Zone Kid",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_id = int(resp.json()["data"]["id"])
    # Set birthday to make child 9 years old → age_group="mid"
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 1, 1)  # ~9 years old in 2026
    db.flush()
    return child_id


@pytest.fixture
def zone_topics(db: Session):
    """Create topics in different age_groups for zone testing."""
    topics = {}
    for age_group in ["low", "mid", "high"]:
        for i in range(5):
            t = LearningTopic(
                topic_key=f"zone_{age_group}_{i}",
                topic_type="CONCEPTUAL",
                subject="mathematics",
                domain="Zone Test",
                name=f"Zone {age_group} topic {i}",
                description="Test",
                age_group=age_group,
                centrality=50.0 - i,
                evidence_json="[]",
                standards_json="[]",
            )
            db.add(t)
            topics.setdefault(age_group, []).append(t)
    db.flush()
    return topics


class TestAgeGroupHelpers:
    def test_growth_zone_matches_child(self):
        assert get_growth_zone_age_group("mid") == "mid"
        assert get_growth_zone_age_group("low") == "low"

    def test_comfort_zone_one_lower(self):
        assert get_comfort_zone_age_group("high") == "mid"
        assert get_comfort_zone_age_group("mid") == "low"
        assert get_comfort_zone_age_group("low") == "low"

    def test_zone_for_topic(self):
        assert get_zone_for_topic("mid", "mid") == "growth"
        assert get_zone_for_topic("low", "mid") == "comfort"
        assert get_zone_for_topic("high", "mid") == "challenge"


class TestGetChildAgeGroup:
    def test_returns_age_group(self, db: Session, child_with_birthday):
        group = get_child_age_group(db, child_with_birthday)
        assert group == "mid"  # 9 years old → mid


class TestGetZoneRecommendedTopic:
    def test_prefers_growth_zone(self, db: Session, child_with_birthday, zone_topics):
        # Create available progress for growth zone topics
        for t in zone_topics["mid"][:2]:
            p = LearningProgress(
                child_id=child_with_birthday,
                topic_id=t.id,
                mastery_level="available",
            )
            db.add(p)
        db.flush()

        topic, zone = get_zone_recommended_topic(db, child_with_birthday)
        assert topic is not None
        assert zone == "growth"
        assert topic.age_group == "mid"

    def test_falls_back_to_comfort(self, db: Session, child_with_birthday, zone_topics):
        # Only comfort zone topics available
        for t in zone_topics["low"][:2]:
            p = LearningProgress(
                child_id=child_with_birthday,
                topic_id=t.id,
                mastery_level="available",
            )
            db.add(p)
        db.flush()

        topic, zone = get_zone_recommended_topic(db, child_with_birthday)
        assert topic is not None
        assert zone == "comfort"

    def test_excludes_mastered(self, db: Session, child_with_birthday, zone_topics):
        # Master all growth zone topics
        for t in zone_topics["mid"]:
            p = LearningProgress(
                child_id=child_with_birthday,
                topic_id=t.id,
                mastery_level="mastered",
            )
            db.add(p)
        # Make comfort zone available
        for t in zone_topics["low"][:1]:
            p = LearningProgress(
                child_id=child_with_birthday,
                topic_id=t.id,
                mastery_level="available",
            )
            db.add(p)
        db.flush()

        topic, zone = get_zone_recommended_topic(db, child_with_birthday)
        assert topic is not None
        assert topic.age_group == "low"  # Fell back to comfort

    def test_sorts_by_centrality(self, db: Session, child_with_birthday, zone_topics):
        for t in zone_topics["mid"]:
            p = LearningProgress(
                child_id=child_with_birthday,
                topic_id=t.id,
                mastery_level="available",
            )
            db.add(p)
        db.flush()

        topic, zone = get_zone_recommended_topic(db, child_with_birthday)
        assert topic is not None
        # Should pick highest centrality (first in the list)
        assert topic.id == zone_topics["mid"][0].id


class TestGetChildZone:
    def test_returns_growth(self, db: Session, child_with_birthday):
        assert get_child_zone(db, child_with_birthday) == "growth"
