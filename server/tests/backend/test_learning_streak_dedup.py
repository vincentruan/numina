"""Tests for notification dedup fix — structured child_id/topic_id + auto-resolve on pass."""

import pytest
from datetime import UTC, datetime

from apps.backend.app.services.learning.progress_service import (
    STREAK_THRESHOLD,
    check_consecutive_failures,
    resolve_streak_reminder_on_pass,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_streak_3_failures,
)
from packages.db.models.learning.session import LearningAssessmentAttempt
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.reminder import Reminder
from packages.db.models.user import User


@pytest.fixture
def child(db):
    user = User(
        id=100, family_id=1, username="child1",
        display_name="Alice", role="child",
        password_hash="fake-hash",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture
def topic(db):
    t = LearningTopic(
        topic_key="dedup_test",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Subtraction",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def _make_attempt(db, child_id, topic_id, passed):
    attempt = LearningAssessmentAttempt(
        child_id=child_id, topic_id=topic_id,
        session_id=None, assessment_type="ai",
        score=0.0 if not passed else 1.0,
        passed=passed,
    )
    db.add(attempt)
    db.flush()
    return attempt


def test_structured_dedup_uses_child_topic_ids(db, child, topic):
    """notify_learning_streak_3_failures stores child_id and topic_id on Reminder."""
    for _ in range(3):
        _make_attempt(db, child.id, topic.id, passed=False)

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminder = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
    ).first()
    assert reminder is not None
    assert reminder.child_id == child.id
    assert reminder.topic_id == topic.id


def test_pass_resolves_active_streak_reminder(db, child, topic):
    """When a child passes, active streak reminders for that child+topic are resolved."""
    reminder = Reminder(
        id=999,
        family_id=child.family_id,
        reminder_type="learning_streak_3_failures",
        title="Test",
        body="Test",
        severity="warning",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    )
    db.add(reminder)
    db.flush()

    count = resolve_streak_reminder_on_pass(db, child.id, topic.id)
    assert count == 1

    db.expire_all()
    resolved = db.query(Reminder).filter(Reminder.id == 999).first()
    assert resolved.status == "resolved"
    assert resolved.resolved_at is not None


def test_full_retrigger_sequence(db, child, topic):
    """3 fails → notification → pass resolves → 3 more fails → new notification."""
    # Phase 1: 3 failures → notification
    for _ in range(3):
        _make_attempt(db, child.id, topic.id, passed=False)

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminders_1 = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(reminders_1) == 1

    # Phase 2: pass → auto-resolve
    _make_attempt(db, child.id, topic.id, passed=True)
    resolve_streak_reminder_on_pass(db, child.id, topic.id)
    db.flush()

    active_after_pass = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(active_after_pass) == 0

    # Phase 3: 3 more failures → new notification
    for _ in range(3):
        _make_attempt(db, child.id, topic.id, passed=False)

    streak = check_consecutive_failures(db, child.id, topic.id)
    assert streak == STREAK_THRESHOLD

    notify_learning_streak_3_failures(db, child_id=child.id, topic_id=topic.id)
    db.flush()

    reminders_2 = db.query(Reminder).filter_by(
        reminder_type="learning_streak_3_failures",
        status="active",
        child_id=child.id,
        topic_id=topic.id,
    ).all()
    assert len(reminders_2) == 1
    assert reminders_2[0].id != reminders_1[0].id
