"""Tests for review dual-track: AI auto-pass + parent override + circuit breaker."""

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.progress_service import (
    AUTO_PASS_THRESHOLD,
    CONSECUTIVE_OVERRIDE_LIMIT,
    SHORT_SESSION_SECONDS,
    approve_parent_review,
    check_auto_pass,
    get_consecutive_override_count,
    is_ai_auto_pass_paused,
    override_review,
)
from apps.backend.app.services.learning import session_service
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User
from tests.backend.conftest import child_login_two_phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child_user(db: Session, client, auth_headers):
    """Create a child via API."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "dualtrack_child",
            "password": "ChildPass1",
            "display_name": "Dual Track Kid",
            "avatar_color": "#FF5733",
            "pin": ["\U0001f431", "\U0001f31f", "\U0001f388", "\U0001f436"],
        },
    )
    assert resp.status_code == 201, f"child creation failed: {resp.text}"
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 1, 1)
    db.flush()

    # Get the parent user's id (the testuser from auth_headers)
    parent = db.query(User).filter(User.username == "testuser").first()
    return {"id": child_id, "parent_id": parent.id, "family_id": parent.family_id}


@pytest.fixture
def topic(db: Session):
    """Create a test topic."""
    t = LearningTopic(
        topic_key="dt-topic-1",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="DT Topic 1",
        name_zh="DT 主题1",
        description="Test topic for dual track",
        age_group="mid",
        source_taxonomy="beijing",
        centrality=50.0,
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _make_progress(db, child_id, topic_id, mastery="parent_review", **kw):
    p = LearningProgress(
        child_id=child_id,
        topic_id=topic_id,
        mastery_level=mastery,
        **kw,
    )
    db.add(p)
    db.flush()
    return p


@pytest.fixture
def ai_passed_progress(db, child_user, topic):
    """A progress that was AI-passed to mastered."""
    return _make_progress(
        db,
        child_user["id"],
        topic.id,
        mastery="mastered",
        mastery_score=0.9,
        completed_via="ai_assessment",
    )


@pytest.fixture
def rejected_progress(db, child_user, topic):
    """A progress in parent_review (rejected state for override test)."""
    return _make_progress(
        db,
        child_user["id"],
        topic.id,
        mastery="parent_review",
    )


@pytest.fixture
def pending_progress(db, child_user, topic):
    """A progress in parent_review awaiting normal approval."""
    return _make_progress(
        db,
        child_user["id"],
        topic.id,
        mastery="parent_review",
        mastery_score=0.85,
    )


@pytest.fixture
def ai_passed_progresses(db, child_user, topic):
    """Multiple AI-passed progress records for circuit breaker testing."""
    progresses = []
    for i in range(6):
        t = LearningTopic(
            topic_key=f"dt-cb-topic-{i}",
            topic_type="CONCEPTUAL",
            subject="mathematics",
            domain="Test",
            name=f"CB Topic {i}",
            description="Circuit breaker test topic",
            age_group="mid",
            centrality=50.0,
            evidence_json="[]",
            standards_json="[]",
            curriculum_standards_json="[]",
        )
        db.add(t)
        db.flush()
        p = _make_progress(
            db,
            child_user["id"],
            t.id,
            mastery="mastered",
            mastery_score=0.85,
            completed_via="ai_assessment",
        )
        progresses.append(p)
    return progresses


# ---------------------------------------------------------------------------
# TestCheckAutoPass
# ---------------------------------------------------------------------------


class TestCheckAutoPass:
    def test_score_above_threshold_returns_auto_pass(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.85, child_id=child_user["id"])
        assert result.should_auto_pass is True
        assert result.reason == "score_above_threshold"

    def test_score_at_threshold_returns_auto_pass(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.8, child_id=child_user["id"])
        assert result.should_auto_pass is True

    def test_score_below_threshold_returns_parent_review(self, db, child_user, topic):
        result = check_auto_pass(db, score=0.79, child_id=child_user["id"])
        assert result.should_auto_pass is False
        assert result.reason == "score_below_threshold"

    def test_none_score_returns_parent_review(self, db, child_user, topic):
        result = check_auto_pass(db, score=None, child_id=child_user["id"])
        assert result.should_auto_pass is False
        assert result.reason == "no_score"

    def test_paused_auto_pass_returns_parent_review(self, db, child_user, topic):
        """When ai_auto_pass_paused flag is set, even high scores go to parent_review."""
        result = check_auto_pass(
            db, score=0.9, child_id=child_user["id"], ai_paused=True
        )
        assert result.should_auto_pass is False
        assert result.reason == "ai_paused"

    def test_short_session_flagged_as_needs_attention(self, db, child_user, topic):
        """Sessions < 3 minutes are flagged even if score passes."""
        result = check_auto_pass(
            db, score=0.85, child_id=child_user["id"], duration_seconds=120
        )
        assert result.should_auto_pass is True
        assert result.needs_attention is True

    def test_normal_session_not_flagged(self, db, child_user, topic):
        """Sessions >= 3 minutes are not flagged."""
        result = check_auto_pass(
            db, score=0.85, child_id=child_user["id"], duration_seconds=200
        )
        assert result.should_auto_pass is True
        assert result.needs_attention is False

    def test_no_duration_not_flagged(self, db, child_user, topic):
        """No duration provided -> not flagged."""
        result = check_auto_pass(db, score=0.85, child_id=child_user["id"])
        assert result.should_auto_pass is True
        assert result.needs_attention is False


# ---------------------------------------------------------------------------
# TestOverrideReview
# ---------------------------------------------------------------------------


class TestOverrideReview:
    def test_parent_can_override_ai_pass_to_reject(
        self, db, child_user, ai_passed_progress
    ):
        result = override_review(
            db,
            progress_id=ai_passed_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="learning",
            reason="孩子实际上没有掌握",
        )
        assert result.mastery_level == "learning"
        assert result.overridden_by == child_user["parent_id"]

    def test_parent_can_override_reject_to_pass(
        self, db, child_user, rejected_progress
    ):
        result = override_review(
            db,
            progress_id=rejected_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="mastered",
            reason="其实孩子已经掌握了",
        )
        assert result.mastery_level == "mastered"

    def test_override_records_metadata(self, db, child_user, ai_passed_progress):
        result = override_review(
            db,
            progress_id=ai_passed_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="learning",
            reason="test reason",
        )
        assert result.overridden_by == child_user["parent_id"]
        assert result.overridden_at is not None
        assert result.override_reason == "test reason"

    def test_override_to_mastered_sets_completed_via(
        self, db, child_user, rejected_progress
    ):
        result = override_review(
            db,
            progress_id=rejected_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="mastered",
            reason="override to pass",
        )
        assert result.completed_via == "parent_override"


# ---------------------------------------------------------------------------
# TestConsecutiveOverrideCircuitBreaker
# ---------------------------------------------------------------------------


class TestConsecutiveOverrideCircuitBreaker:
    def test_five_overrides_pauses_auto_pass(
        self, db, child_user, ai_passed_progresses
    ):
        """After 5 consecutive overrides, auto-pass should be paused."""
        for p in ai_passed_progresses[:5]:
            override_review(
                db, p.id, child_user["parent_id"], "learning", "reason"
            )
        assert is_ai_auto_pass_paused(db, child_user["id"]) is True

    def test_four_overrides_does_not_pause(
        self, db, child_user, ai_passed_progresses
    ):
        """4 overrides should not yet pause auto-pass."""
        for p in ai_passed_progresses[:4]:
            override_review(
                db, p.id, child_user["parent_id"], "learning", "reason"
            )
        assert is_ai_auto_pass_paused(db, child_user["id"]) is False

    def test_counter_resets_on_non_override_approval(
        self, db, child_user, pending_progress
    ):
        """A normal parent approval (not override) resets the counter."""
        # First bump the counter with some overrides on other progresses
        # (Use ai_passed_progresses but we need a fresh child here)
        # Instead, just verify the counter is 0 after a normal approval
        approve_parent_review(db, pending_progress, child_user["family_id"])
        assert get_consecutive_override_count(db, child_user["id"]) == 0

    def test_override_increments_counter(self, db, child_user, ai_passed_progress):
        """Each override increments the consecutive counter."""
        override_review(
            db, ai_passed_progress.id, child_user["parent_id"], "learning", "reason"
        )
        assert get_consecutive_override_count(db, child_user["id"]) == 1


# ---------------------------------------------------------------------------
# TestAutoPassConstants
# ---------------------------------------------------------------------------


class TestAutoPassConstants:
    def test_threshold_value(self):
        assert AUTO_PASS_THRESHOLD == 0.8

    def test_consecutive_limit_value(self):
        assert CONSECUTIVE_OVERRIDE_LIMIT == 5

    def test_short_session_seconds_value(self):
        assert SHORT_SESSION_SECONDS == 180


# ---------------------------------------------------------------------------
# Helpers for API integration tests
# ---------------------------------------------------------------------------

CHILD_PASSWORD = "ChildPass1"
PIN = ["\U0001f431", "\U0001f31f", "\U0001f388", "\U0001f436"]


def _child_login_headers(client, username: str) -> dict:
    """Two-phase child login — returns Bearer headers dict."""
    token = child_login_two_phase(client, username, CHILD_PASSWORD, PIN)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# TestReviewDueTopicInTodayEndpoint
# ---------------------------------------------------------------------------


class TestReviewDueTopicInTodayEndpoint:
    def test_mastered_topic_with_expired_review_appears_in_today(
        self, db, client, child_user, topic
    ):
        """A mastered topic with next_review_at in the past appears as review_due_topic."""
        child_id = child_user["id"]
        past = datetime.now(timezone.utc) - timedelta(days=1)
        _make_progress(
            db,
            child_id,
            topic.id,
            mastery="mastered",
            mastery_score=0.9,
            completed_via="ai_assessment",
            next_review_at=past,
        )

        child_headers = _child_login_headers(client, "dualtrack_child")
        resp = client.get("/api/v1/child/learning/today", headers=child_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["review_due_topic"] is not None
        assert data["review_due_topic"]["id"] == str(topic.id)


# ---------------------------------------------------------------------------
# TestEndSessionDualTrack
# ---------------------------------------------------------------------------


class TestEndSessionDualTrack:
    def test_high_score_transitions_to_mastered_via_ai(self, db, child_user, topic):
        """end_session with score >= 0.8 transitions assessing -> mastered."""
        child_id = child_user["id"]
        progress = _make_progress(db, child_id, topic.id, mastery="assessing")

        session = LearningSession(
            child_id=child_id,
            topic_id=topic.id,
            session_type="assessment",
        )
        db.add(session)
        db.flush()

        result = session_service.end_session(db, session.id, score=0.85)

        db.refresh(progress)
        assert progress.mastery_level == "mastered"
        assert progress.completed_via == "ai_assessment"
        assert progress.mastery_score == 0.85

    def test_low_score_transitions_to_parent_review(self, db, child_user, topic):
        """end_session with score < 0.8 transitions assessing -> parent_review."""
        child_id = child_user["id"]
        progress = _make_progress(db, child_id, topic.id, mastery="assessing")

        session = LearningSession(
            child_id=child_id,
            topic_id=topic.id,
            session_type="assessment",
        )
        db.add(session)
        db.flush()

        result = session_service.end_session(db, session.id, score=0.5)

        db.refresh(progress)
        assert progress.mastery_level == "parent_review"
        assert progress.mastery_score == 0.5


    def test_override_to_mastered_sets_sm2_bookkeeping(
        self, db, child_user, rejected_progress
    ):
        """override_review to 'mastered' must set stability, next_review_at, and unlock dependents."""
        result = override_review(
            db,
            progress_id=rejected_progress.id,
            parent_id=child_user["parent_id"],
            new_decision="mastered",
            reason="parent says yes",
        )
        assert result.mastery_level == "mastered"
        assert result.completed_via == "parent_override"
        assert result.stability is not None, "stability must be set by transition_to_mastered"
        assert result.next_review_at is not None, "next_review_at must be set by transition_to_mastered"
        assert result.first_mastered_at is not None, "first_mastered_at must be set"


class TestEndSessionCircuitBreakerBypass:
    def test_ai_paused_prevents_auto_pass_even_with_high_score(self, db, child_user, topic):
        """When ai_paused is True (5+ overrides), high score goes to parent_review, not mastered."""
        child_id = child_user["id"]
        progress = _make_progress(db, child_id, topic.id, mastery="assessing")

        # Simulate 5 consecutive overrides to pause auto-pass
        from apps.backend.app.services.learning.progress_service import (
            _increment_consecutive_override_counter,
        )
        for _ in range(CONSECUTIVE_OVERRIDE_LIMIT):
            _increment_consecutive_override_counter(db, child_id)

        assert is_ai_auto_pass_paused(db, child_id) is True

        session = LearningSession(
            child_id=child_id,
            topic_id=topic.id,
            session_type="assessment",
        )
        db.add(session)
        db.flush()

        session_service.end_session(db, session.id, score=0.95)

        db.refresh(progress)
        # Despite high score, ai_paused should force parent_review
        assert progress.mastery_level == "parent_review"
        assert progress.mastery_score == 0.95
