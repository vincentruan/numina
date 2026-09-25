"""Tests for failure streak detection in progress_service."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.models.reminder import Reminder
from apps.backend.app.services.learning.progress_service import (
    check_consecutive_failures,
    get_or_create_progress,
    record_failed_assessment,
)
from packages.db.models.learning.session import LearningAssessmentAttempt
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_streak", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Streak Test", description="Test",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def child(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "streakchild", "password": "ChildPass1",
        "display_name": "Streak Kid", "pin": ["\U0001f431", "\U0001f431", "\U0001f431", "\U0001f431"],
    })
    assert resp.status_code == 201, f"Failed to create child: {resp.status_code} {resp.text}"
    return resp.json()["data"]


def test_check_consecutive_failures_below_threshold(db, child, topic):
    """1-2 consecutive failures do not trigger."""
    for _ in range(2):
        attempt = LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.4,
        )
        db.add(attempt)
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 2


def test_check_consecutive_failures_at_threshold(db, child, topic):
    """Exactly 3 consecutive failures triggers."""
    for _ in range(3):
        attempt = LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        )
        db.add(attempt)
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 3


def test_check_consecutive_failures_interrupted_by_pass(db, child, topic):
    """A passing attempt breaks the streak."""
    # 2 failures
    for _ in range(2):
        db.add(LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        ))
    # 1 pass
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic.id,
        assessment_type="ai", passed=True, score=0.9,
    ))
    # 1 more failure
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic.id,
        assessment_type="ai", passed=False, score=0.4,
    ))
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 1


def test_check_consecutive_failures_different_topics_isolated(db, child, topic):
    """Failures on different topics don't count toward the same streak."""
    topic2 = LearningTopic(
        topic_key="mt_streak2", topic_type="CONCEPTUAL", subject="mathematics",
        domain="Test", name="Other Topic", description="Test",
        age_group="mid", evidence_json="[]", standards_json="[]",
    )
    db.add(topic2)
    db.flush()

    # 2 failures on topic 1
    for _ in range(2):
        db.add(LearningAssessmentAttempt(
            child_id=int(child["id"]), topic_id=topic.id,
            assessment_type="ai", passed=False, score=0.3,
        ))
    # 1 failure on topic 2
    db.add(LearningAssessmentAttempt(
        child_id=int(child["id"]), topic_id=topic2.id,
        assessment_type="ai", passed=False, score=0.3,
    ))
    db.flush()

    assert check_consecutive_failures(db, int(child["id"]), topic.id) == 2
    assert check_consecutive_failures(db, int(child["id"]), topic2.id) == 1


def test_record_failed_assessment_returns_streak_count(db, child, topic):
    get_or_create_progress(db, int(child["id"]), topic.id)

    count1 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.4)
    assert count1 == 1  # not triggered yet

    count2 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)
    assert count2 == 2

    count3 = record_failed_assessment(db, int(child["id"]), topic.id, None, 0.2)
    assert count3 == 3  # streak! notification should fire


def test_streak_notification_fires_at_threshold(db, child, topic):
    """Notification fires when streak reaches exactly 3."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    # First 2 failures — no notification
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.4)
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    reminders_before = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()

    # 3rd failure — notification should fire
    record_failed_assessment(db, int(child["id"]), topic.id, None, 0.2)

    reminders_after = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()

    assert reminders_after == reminders_before + 1


def test_streak_notification_not_duplicated_on_4th_failure(db, child, topic):
    """4th consecutive failure does NOT fire a duplicate notification."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    for _ in range(4):
        record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    count = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()
    assert count == 1  # exactly 1, not 2


def test_streak_notification_content_includes_child_and_topic(db, child, topic):
    """Notification body includes child name, topic name, and subject."""
    get_or_create_progress(db, int(child["id"]), topic.id)

    for _ in range(3):
        record_failed_assessment(db, int(child["id"]), topic.id, None, 0.3)

    reminder = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).first()
    assert reminder is not None
    assert "Streak Kid" in reminder.title or "Streak Kid" in reminder.body


def test_streak_notification_retriggers_after_pass_breaks_streak(db, child, topic):
    """After a pass breaks the streak, a new 3-failure streak fires another notification."""
    get_or_create_progress(db, int(child["id"]), topic.id)
    cid = int(child["id"])

    # First streak of 3 → notification fires
    for _ in range(3):
        record_failed_assessment(db, cid, topic.id, None, 0.3)

    count_after_first = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()
    assert count_after_first == 1

    # Resolve the first notification (simulating parent acknowledging it)
    reminder = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
    ).first()
    reminder.status = "resolved"
    db.flush()

    # A pass breaks the streak
    db.add(LearningAssessmentAttempt(
        child_id=cid, topic_id=topic.id,
        assessment_type="ai", passed=True, score=0.9,
    ))
    db.flush()

    # New streak of 3 → second notification fires
    for _ in range(3):
        record_failed_assessment(db, cid, topic.id, None, 0.2)

    count_after_second = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures"
    ).count()
    assert count_after_second == 2
