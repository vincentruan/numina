"""Tests for Phase 5 practice service additions: weak topics, history, detail."""

import json

import pytest
from datetime import UTC, datetime, timedelta
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic
from packages.db.models.learning.question import Question
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt
from packages.db.models.learning.progress import LearningProgress
from apps.backend.app.services.learning.practice_service import (
    get_weak_topics,
    list_sessions,
    get_session_detail,
)


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_p5_svc",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Addition",
        name_zh="加法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def question(db: Session, topic):
    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="1 + 1 = ?",
        answer_json='{"answer": 2}',
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    db.add(q)
    db.flush()
    return q


@pytest.fixture
def session_with_attempts(db: Session, topic, question):
    """Create a completed session with one correct attempt."""
    s = PracticeSession(
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json=json.dumps([question.id]),
        source="adaptive",
        started_at=datetime.now(UTC) - timedelta(hours=1),
        ended_at=datetime.now(UTC),
        total_score=1.0,
        completed_count=1,
    )
    db.add(s)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s.id,
        question_id=question.id,
        child_id=1,
        topic_id=topic.id,
        user_answer_json='{"answer": 2}',
        is_correct=True,
        time_spent_seconds=10,
        attempt_number=1,
    ))
    db.flush()
    return s


def test_get_weak_topics_returns_accuracy(db: Session, topic, session_with_attempts):
    """get_weak_topics returns topics with correct accuracy stats."""
    weak = get_weak_topics(db, child_id=1, limit=10, min_attempts=1)
    assert len(weak) >= 1
    w = weak[0]
    assert w["topic_id"] == topic.id
    assert w["total_attempts"] == 1
    assert w["correct_attempts"] == 1
    assert w["accuracy"] == 1.0
    assert w["topic_name"] == "Addition"
    assert w["topic_name_zh"] == "加法"


def test_get_weak_topics_min_attempts_filter(db: Session, topic, session_with_attempts):
    """get_weak_topics respects min_attempts threshold."""
    # With min_attempts=5, the topic with only 1 attempt should be excluded
    weak = get_weak_topics(db, child_id=1, limit=10, min_attempts=5)
    assert len(weak) == 0


def test_get_weak_topics_sorted_by_accuracy(db: Session, topic, question):
    """Topics with lower accuracy come first."""
    # Create a second topic with worse accuracy
    topic2 = LearningTopic(
        topic_key="mt_p5_svc2",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Subtraction",
        name_zh="减法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic2)
    db.flush()

    q2 = Question(
        topic_id=topic2.id,
        question_type="calculation",
        stem="5 - 3 = ?",
        answer_json='{"answer": 2}',
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    db.add(q2)
    db.flush()

    # Add 3 correct attempts on topic1 (across different sessions to avoid UQ)
    for i in range(3):
        s = PracticeSession(
            child_id=1, topic_id=topic.id, session_mode="practice",
            question_ids_json=json.dumps([question.id]), source="adaptive",
        )
        db.add(s)
        db.flush()
        db.add(PracticeAttempt(
            session_id=s.id, question_id=question.id, child_id=1,
            topic_id=topic.id, user_answer_json='{"answer": 2}',
            is_correct=True, time_spent_seconds=10, attempt_number=1,
        ))

    # Add 3 wrong attempts on topic2 (each in its own session)
    for i in range(3):
        s2 = PracticeSession(
            child_id=1, topic_id=topic2.id, session_mode="practice",
            question_ids_json=json.dumps([q2.id]), source="adaptive",
        )
        db.add(s2)
        db.flush()
        db.add(PracticeAttempt(
            session_id=s2.id, question_id=q2.id, child_id=1,
            topic_id=topic2.id, user_answer_json='{"answer": 99}',
            is_correct=False, time_spent_seconds=5, attempt_number=1,
        ))
    db.flush()

    weak = get_weak_topics(db, child_id=1, limit=10, min_attempts=3)
    assert len(weak) == 2
    # Weakest (0% accuracy) should come first
    assert weak[0]["topic_id"] == topic2.id
    assert weak[0]["accuracy"] == 0.0
    assert weak[1]["topic_id"] == topic.id
    assert weak[1]["accuracy"] == 1.0


def test_get_weak_topics_enriches_mastery_level(db: Session, topic, session_with_attempts):
    """get_weak_topics includes mastery_level from LearningProgress."""
    progress = LearningProgress(
        child_id=1, topic_id=topic.id, mastery_level="learning"
    )
    db.add(progress)
    db.flush()

    weak = get_weak_topics(db, child_id=1, limit=10, min_attempts=1)
    assert weak[0]["mastery_level"] == "learning"


def test_list_sessions_returns_ordered(db: Session, topic, session_with_attempts):
    """list_sessions returns sessions ordered by started_at DESC."""
    sessions = list_sessions(db, child_id=1, limit=10)
    assert len(sessions) >= 1
    assert sessions[0].id == session_with_attempts.id


def test_list_sessions_pagination(db: Session, topic, question):
    """list_sessions respects limit and offset."""
    # Create 3 sessions
    session_ids = []
    for i in range(3):
        s = PracticeSession(
            child_id=1,
            topic_id=topic.id,
            session_mode="practice",
            question_ids_json=json.dumps([question.id]),
            source="adaptive",
            started_at=datetime.now(UTC) - timedelta(hours=i),
        )
        db.add(s)
        db.flush()
        session_ids.append(s.id)

    page1 = list_sessions(db, child_id=1, limit=2, offset=0)
    assert len(page1) == 2
    # Most recent first
    assert page1[0].id == session_ids[0]

    page2 = list_sessions(db, child_id=1, limit=2, offset=2)
    assert len(page2) == 1


def test_get_session_detail_includes_attempts(db: Session, topic, session_with_attempts):
    """get_session_detail returns session with attempt details."""
    detail = get_session_detail(
        db, session_id=session_with_attempts.id, child_id=1
    )
    assert detail is not None
    assert detail["id"] == session_with_attempts.id
    assert detail["topic_name"] == "Addition"
    assert detail["topic_name_zh"] == "加法"
    assert len(detail["attempts"]) == 1
    assert detail["attempts"][0]["is_correct"] is True
    assert detail["attempts"][0]["question_stem"] == "1 + 1 = ?"
    assert detail["attempts"][0]["question_type"] == "calculation"


def test_get_session_detail_wrong_child(db: Session, topic, session_with_attempts):
    """get_session_detail returns None for wrong child_id (ownership check)."""
    detail = get_session_detail(db, session_id=session_with_attempts.id, child_id=999)
    assert detail is None


def test_get_session_detail_nonexistent(db: Session):
    """get_session_detail returns None for non-existent session."""
    detail = get_session_detail(db, session_id=999999, child_id=1)
    assert detail is None
