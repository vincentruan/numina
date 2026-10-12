"""Tests for adaptive question selection service."""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    RuleBasedMasteryEstimator,
    get_difficulty_range,
    select_questions,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_adaptive_test",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Addition",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    """Create 10 questions across difficulties 1-5."""
    qs = []
    for i in range(10):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i+1}",
            answer_json='{"answer": 1}',
            difficulty=(i % 5) + 1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def test_get_difficulty_range_for_learning():
    assert get_difficulty_range("learning") == (1, 2)
    assert get_difficulty_range("available") == (1, 2)


def test_get_difficulty_range_for_assessing():
    assert get_difficulty_range("assessing") == (2, 3)


def test_get_difficulty_range_for_mastered():
    assert get_difficulty_range("mastered") == (3, 4)


def test_get_difficulty_range_for_review():
    assert get_difficulty_range("review") == (1, 2)


def test_select_questions_returns_correct_count(db: Session, topic, questions):
    selected = select_questions(
        db=db,
        topic_id=topic.id,
        mastery_level="learning",
        count=3,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=1,
    )
    assert len(selected) == 3
    for q in selected:
        assert q.difficulty in (1, 2)


def test_select_questions_excludes_recent(db: Session, topic, questions):
    """Questions answered in last N days are excluded."""
    selected = select_questions(
        db=db,
        topic_id=topic.id,
        mastery_level="learning",
        count=5,
        exclude_question_ids=[q.id for q in questions[:2]],
        exclude_recent_days=7,
        child_id=1,
    )
    assert all(q.id not in [questions[0].id, questions[1].id] for q in selected)


def test_select_questions_returns_empty_when_none_available(db: Session, topic):
    """Returns empty list when no questions match."""
    empty_topic = LearningTopic(
        topic_key="mt_empty",
        topic_type="concept",
        subject="mathematics",
        domain="empty",
        name="Empty",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(empty_topic)
    db.flush()

    selected = select_questions(
        db=db,
        topic_id=empty_topic.id,
        mastery_level="learning",
        count=5,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=1,
    )
    assert selected == []


def test_mastery_estimator_basic(db: Session, topic):
    estimator = RuleBasedMasteryEstimator()
    score = estimator.estimate(db=db, child_id=1, topic_id=topic.id)
    assert score == 0.0
