"""Tests for child learning stats service — XP, level, streak."""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.stats_service import (
    DAILY_XP_CAP,
    _compute_level,
    award_xp,
    get_level_info,
    get_or_create_stats,
    update_streak,
)


@pytest.fixture
def child_and_family(db: Session, client, auth_headers):
    """Create a child via API and return child_id + family_id."""
    from packages.db.models.user import User

    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "statschild",
            "password": "ChildPass1",
            "display_name": "Stats Kid",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child_data = resp.json()["data"]
    child_id = int(child_data["id"])

    # Get family_id from the user record
    child_user = db.query(User).filter(User.id == child_id).first()
    return {"child_id": child_id, "family_id": child_user.family_id}


class TestGetOrCreateStats:
    def test_creates_with_defaults(self, db: Session, child_and_family):
        stats = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        assert stats.cumulative_xp == 0
        assert stats.level == 1
        assert stats.learning_streak_days == 0
        assert stats.current_zone == "growth"
        assert stats.onboarding_completed is False

    def test_returns_existing(self, db: Session, child_and_family):
        s1 = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        s1.cumulative_xp = 50
        db.flush()
        s2 = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        assert s2.id == s1.id
        assert s2.cumulative_xp == 50


class TestComputeLevel:
    def test_level_1_at_zero(self):
        assert _compute_level(0) == 1

    def test_level_2_at_100(self):
        assert _compute_level(100) == 2

    def test_level_3_at_300(self):
        assert _compute_level(300) == 3

    def test_level_7_at_5000(self):
        assert _compute_level(5000) == 7

    def test_level_7_above_5000(self):
        assert _compute_level(10000) == 7

    def test_level_between_thresholds(self):
        assert _compute_level(250) == 2  # Between 100 and 300


class TestGetLevelInfo:
    def test_level_1_info(self):
        info = get_level_info(1)
        assert info["name_zh"] == "种子"
        assert info["name_en"] == "Seed"
        assert info["emoji"] == "🌱"
        assert info["next_threshold"] == 100

    def test_max_level_no_next(self):
        info = get_level_info(7)
        assert info["name_zh"] == "大师"
        assert info["next_threshold"] is None


class TestAwardXP:
    def test_basic_award(self, db: Session, child_and_family):
        result = award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=30)
        assert result["xp_awarded"] == 30
        assert result["leveled_up"] is False
        assert result["new_level"] == 1

    def test_level_up_on_threshold(self, db: Session, child_and_family):
        award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=90)
        result = award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=20)
        assert result["leveled_up"] is True
        assert result["new_level"] == 2

    def test_daily_cap_enforced(self, db: Session, child_and_family):
        # Award up to the cap
        r1 = award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=80)
        assert r1["xp_awarded"] == 80
        # Try to exceed cap
        r2 = award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=50)
        assert r2["xp_awarded"] == 20  # Only 20 remaining of 100 cap
        assert r2["daily_cap_reached"] is True

    def test_zero_xp_when_cap_reached(self, db: Session, child_and_family):
        award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=DAILY_XP_CAP)
        result = award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=10)
        assert result["xp_awarded"] == 0
        assert result["daily_cap_reached"] is True

    def test_streak_updated_on_award(self, db: Session, child_and_family):
        award_xp(db, child_and_family["child_id"], child_and_family["family_id"], xp_amount=10)
        stats = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        assert stats.learning_streak_days == 1
        assert stats.last_learning_date == date.today()


class TestUpdateStreak:
    def test_first_day_streak(self, db: Session, child_and_family):
        streak = update_streak(db, child_and_family["child_id"], child_and_family["family_id"])
        assert streak == 1

    def test_consecutive_day_increments(self, db: Session, child_and_family):
        stats = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        stats.last_learning_date = date.today() - timedelta(days=1)
        stats.learning_streak_days = 3
        db.flush()

        streak = update_streak(db, child_and_family["child_id"], child_and_family["family_id"])
        assert streak == 4

    def test_same_day_no_change(self, db: Session, child_and_family):
        stats = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        stats.last_learning_date = date.today()
        stats.learning_streak_days = 5
        db.flush()

        streak = update_streak(db, child_and_family["child_id"], child_and_family["family_id"])
        assert streak == 5  # Unchanged

    def test_gap_resets_streak(self, db: Session, child_and_family):
        stats = get_or_create_stats(db, child_and_family["child_id"], child_and_family["family_id"])
        stats.last_learning_date = date.today() - timedelta(days=3)
        stats.learning_streak_days = 10
        db.flush()

        streak = update_streak(db, child_and_family["child_id"], child_and_family["family_id"])
        assert streak == 1  # Reset
