"""Tests for PracticeAttempt.misconception_id (issue #214)."""

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def misconception(db: Session) -> Misconception:
    topic = LearningTopic(
        topic_key="test_mc_topic", topic_type="concept",
        subject="mathematics", domain="arithmetic",
        name="Test", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(topic)
    db.flush()
    m = Misconception(
        topic_id=topic.id, sequence=0,
        error_pattern_json="{}", description="test",
        age_group="mid", review_status="approved",
        category="concept_confusion",
    )
    db.add(m)
    db.flush()
    return m


def test_practice_attempt_accepts_null_misconception(db: Session):
    """PracticeAttempt can be created without a misconception (backward compat)."""
    session = PracticeSession(
        child_id=1, topic_id=1, session_mode="practice",
        question_ids_json="[1]",
    )
    db.add(session)
    db.flush()
    attempt = PracticeAttempt(
        session_id=session.id, question_id=1, child_id=1, topic_id=1,
        user_answer_json="{}", is_correct=False,
    )
    db.add(attempt)
    db.flush()
    assert attempt.misconception_id is None


def test_practice_attempt_accepts_misconception(db: Session, misconception):
    """PracticeAttempt persists a misconception_id reference."""
    session = PracticeSession(
        child_id=1, topic_id=1, session_mode="practice",
        question_ids_json="[1]",
    )
    db.add(session)
    db.flush()
    attempt = PracticeAttempt(
        session_id=session.id, question_id=1, child_id=1, topic_id=1,
        user_answer_json="{}", is_correct=False,
        misconception_id=misconception.id,
    )
    db.add(attempt)
    db.flush()
    assert attempt.misconception_id == misconception.id


def test_composite_index_exists(db: Session):
    """The (child_id, topic_id, misconception_id) index supports the boost query."""
    from sqlalchemy import inspect
    insp = inspect(db.bind)
    indexes = insp.get_indexes("practice_attempts")
    names = {idx["name"] for idx in indexes}
    assert "ix_practice_attempt_child_topic_misconception" in names
