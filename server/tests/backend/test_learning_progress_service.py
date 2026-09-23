"""Tests for learning progress service — state machine + spaced repetition."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.progress_service import (
    VALID_TRANSITIONS,
    can_start_learning,
    compute_next_review,
    get_child_progress_overview,
    get_or_create_progress,
    recheck_prerequisites,
    transition_to_learning,
    transition_to_mastered,
    unlock_dependent_topics,
    update_stability,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic


@pytest.fixture
def topic(db: Session):
    """Create a standalone learning topic (no prerequisites)."""
    t = LearningTopic(
        topic_key="mt_test",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Test topic",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def topic_with_prereq(db: Session):
    """Create two topics where the second requires the first."""
    t1 = LearningTopic(
        topic_key="mt_prereq",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Prerequisite topic",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    t2 = LearningTopic(
        topic_key="mt_dependent",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Dependent topic",
        description="Test",
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
        reason="Must know prerequisite",
    )
    db.add(dep)
    db.flush()
    return t1, t2


@pytest.fixture
def child_user(client, auth_headers):
    """Create a child user and return their ID."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "learnchild",
            "password": "ChildPass1",
            "display_name": "Learner",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201
    child = resp.json()["data"]
    return {"id": child["id"]}


def test_get_or_create_progress_creates_available(db, child_user, topic):
    """Topic with no prerequisites starts as available."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    assert p.mastery_level == "available"


def test_get_or_create_progress_creates_locked_when_prereqs_not_met(db, child_user, topic_with_prereq):
    """Topic with unmet hard prerequisites starts as locked."""
    _, t2 = topic_with_prereq
    p = get_or_create_progress(db, child_user["id"], t2.id)
    assert p.mastery_level == "locked"


def test_get_or_create_progress_returns_existing(db, child_user, topic):
    """Calling twice returns the same progress record."""
    p1 = get_or_create_progress(db, child_user["id"], topic.id)
    p2 = get_or_create_progress(db, child_user["id"], topic.id)
    assert p1.id == p2.id


def test_transition_to_learning(db, child_user, topic):
    """available -> learning is a valid transition."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    assert p.mastery_level == "available"
    result = transition_to_learning(db, p)
    assert result.mastery_level == "learning"
    assert result.last_practice_at is not None


def test_transition_to_learning_invalid(db, child_user, topic):
    """locked -> learning is not valid."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "locked"
    db.flush()
    with pytest.raises(AppError) as exc_info:
        transition_to_learning(db, p)
    assert "invalid_state_transition" in str(exc_info.value)


def test_transition_to_mastered(db, child_user, topic):
    """assessing -> mastered is valid and updates stability/review."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "assessing"
    db.flush()
    result = transition_to_mastered(db, p, score=0.9, completed_via="ai_assessment")
    assert result.mastery_level == "mastered"
    assert result.mastery_score == 0.9
    assert result.completed_via == "ai_assessment"
    assert result.first_mastered_at is not None
    assert result.stability is not None
    assert result.next_review_at is not None


def test_can_start_learning(db, child_user, topic):
    p = get_or_create_progress(db, child_user["id"], topic.id)
    assert can_start_learning(p) is True
    p.mastery_level = "locked"
    assert can_start_learning(p) is False


def test_compute_next_review_first_time():
    """First review should be ~3 days out (stability=1.0 → 3*1.0=3)."""
    p = LearningProgress(stability=1.0)
    before = datetime.now(UTC)
    dt = compute_next_review(p)
    # dt is between 3 and 4 days from before (function uses now() >= before)
    assert timedelta(days=3) <= (dt - before) < timedelta(days=4)


def test_compute_next_review_high_stability():
    """Higher stability → longer interval."""
    p = LearningProgress(stability=3.0)
    before = datetime.now(UTC)
    dt = compute_next_review(p)
    # dt is between 9 and 10 days from before
    assert timedelta(days=9) <= (dt - before) < timedelta(days=10)


def test_update_stability_increases_on_high_score():
    p = LearningProgress(stability=1.0)
    new_s = update_stability(p, 0.9)
    assert new_s == 1.3


def test_update_stability_decreases_on_low_score():
    p = LearningProgress(stability=2.0)
    new_s = update_stability(p, 0.5)
    assert new_s == 1.2  # 2.0 * 0.6


def test_update_stability_ceiling():
    p = LearningProgress(stability=9.0)
    new_s = update_stability(p, 0.9)
    assert new_s == 10.0  # capped at 10.0


def test_update_stability_floor():
    p = LearningProgress(stability=1.0)
    new_s = update_stability(p, 0.3)
    assert new_s == 1.0  # floor at 1.0


def test_get_child_progress_overview(db, child_user, topic):
    p = get_or_create_progress(db, child_user["id"], topic.id)
    overview = get_child_progress_overview(db, child_user["id"])
    assert overview["available"] == 1
    assert overview["locked"] == 0

    # Transition to learning
    transition_to_learning(db, p)
    overview = get_child_progress_overview(db, child_user["id"])
    assert overview["learning"] == 1
    assert overview["available"] == 0


def test_valid_transitions_coverage():
    """All expected mastery levels have defined transitions."""
    expected_levels = {"locked", "available", "learning", "assessing", "parent_review", "mastered", "review"}
    assert set(VALID_TRANSITIONS.keys()) == expected_levels

def test_review_to_mastered_invalid(db, child_user, topic):
    """review -> mastered is NOT valid (must go review -> learning -> assessing -> mastered)."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "review"
    db.flush()
    with pytest.raises(AppError) as exc_info:
        transition_to_mastered(db, p, score=0.95, completed_via="ai_assessment")
    assert "invalid_state_transition" in str(exc_info.value)


def test_review_to_learning(db, child_user, topic):
    """review -> learning is a valid transition (fail → re-learn)."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "review"
    db.flush()
    result = transition_to_learning(db, p)
    assert result.mastery_level == "learning"


def test_mastered_to_learning_is_valid(db, child_user, topic):
    """mastered -> learning is valid (re-study after mastery)."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "mastered"
    db.flush()
    result = transition_to_learning(db, p)
    assert result.mastery_level == "learning"


def test_recheck_prerequisites_unlocks_when_prereqs_met(db, child_user, topic_with_prereq):
    """recheck_prerequisites unlocks a locked topic once prerequisites are mastered."""
    t1, t2 = topic_with_prereq
    # Create locked progress for t2
    p = get_or_create_progress(db, child_user["id"], t2.id)
    assert p.mastery_level == "locked"

    # Master the prerequisite t1
    p1 = get_or_create_progress(db, child_user["id"], t1.id)
    p1.mastery_level = "mastered"
    db.flush()

    # Recheck should unlock t2
    result = recheck_prerequisites(db, child_user["id"], t2.id)
    assert result.mastery_level == "available"


def test_recheck_prerequisites_stays_locked_when_prereqs_not_met(db, child_user, topic_with_prereq):
    """recheck_prerequisites keeps topic locked when prerequisites are not yet mastered."""
    _, t2 = topic_with_prereq
    p = get_or_create_progress(db, child_user["id"], t2.id)
    assert p.mastery_level == "locked"

    # Prereq not mastered → stays locked
    result = recheck_prerequisites(db, child_user["id"], t2.id)
    assert result.mastery_level == "locked"


def test_unlock_dependent_topics(db, child_user, topic_with_prereq):
    """unlock_dependent_topics unlocks topics whose hard prereq was just mastered."""
    t1, t2 = topic_with_prereq
    # Create locked progress for t2
    get_or_create_progress(db, child_user["id"], t2.id)

    # Master t1 via transition_to_mastered from "assessing" state
    p1 = get_or_create_progress(db, child_user["id"], t1.id)
    p1.mastery_level = "assessing"
    db.flush()
    transition_to_mastered(db, p1, score=0.9, completed_via="ai_assessment")

    # Now unlock dependents
    unlocked = unlock_dependent_topics(db, child_user["id"], t1.id)
    assert len(unlocked) == 1
    assert unlocked[0].topic_id == t2.id
    assert unlocked[0].mastery_level == "available"


def test_invalid_completed_via_raises(db, child_user, topic):
    """transition_to_mastered rejects invalid completed_via values."""
    p = get_or_create_progress(db, child_user["id"], topic.id)
    p.mastery_level = "assessing"
    db.flush()
    with pytest.raises(ValueError, match="Invalid completed_via"):
        transition_to_mastered(db, p, score=0.9, completed_via="bogus")


def test_get_child_progress_overview_includes_all_states(db, child_user, topic):
    """Overview includes assessing and parent_review keys (default 0)."""
    get_or_create_progress(db, child_user["id"], topic.id)
    overview = get_child_progress_overview(db, child_user["id"])
    assert "assessing" in overview
    assert "parent_review" in overview
    assert overview["assessing"] == 0
    assert overview["parent_review"] == 0
