"""Tests for failure streak detection in progress_service."""

import pytest
from sqlalchemy.orm import Session

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
