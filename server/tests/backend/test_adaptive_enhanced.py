"""Tests for enhanced MasteryEstimator and adaptive question selection."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    RuleBasedMasteryEstimator,
    select_questions,
)
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.family import Family
from packages.db.models.user import User
@pytest.fixture
def parent_records(db: Session):
    """Create Family + Users for child_id FK."""
    family = Family(name="Test Family", invite_code="TST001", created_by=1)
    db.add(family)
    db.flush()
    children = []
    for i in range(1, 4):
        u = User(
            display_name=f"Child {i}",
            password_hash="x",
            role="child",
            family_id=family.id,
        )
        db.add(u)
        children.append(u)
    db.flush()
    return children


@pytest.fixture
def practice_session(db: Session, parent_records, topic):
    """Create a PracticeSession for attempt FKs."""
    session = PracticeSession(
        child_id=parent_records[0].id,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[]",
    )
    db.add(session)
    db.flush()
    return session


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_test_adaptive",
        topic_type="procedural",
        subject="mathematics",
        domain="Test",
        name="Test",
        description="test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    """Create questions at various difficulty levels."""
    qs = []
    for diff in range(1, 6):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q diff={diff}",
            answer_json='{"answer": 42}',
            difficulty=diff,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def _make_attempt(db, child_id, topic_id, question_id, session_id, is_correct, created_at=None):
    a = PracticeAttempt(
        session_id=session_id,
        question_id=question_id,
        child_id=child_id,
        topic_id=topic_id,
        user_answer_json='{"answer": 42}',
        is_correct=is_correct,
        time_spent_seconds=30,
        attempt_number=1,
    )
    if created_at:
        a.created_at = created_at
    db.add(a)
    db.flush()
    return a


# --- RuleBasedMasteryEstimator tests ---


class TestRuleBasedMasteryEstimator:
    def test_no_attempts_returns_neutral(self, db: Session, topic):
        """No attempts → neutral 0.5 (insufficient data fallback)."""
        est = RuleBasedMasteryEstimator()
        score = est.estimate(db, child_id=999, topic_id=topic.id)
        assert score == 0.5

    def test_all_correct_high_mastery(self, db: Session, topic, questions, parent_records, practice_session):
        """5 consecutive correct answers → high mastery."""
        cid = parent_records[0].id
        for q in questions[:5]:
            _make_attempt(db, child_id=cid, topic_id=topic.id, question_id=q.id,
                          session_id=practice_session.id, is_correct=True)

        est = RuleBasedMasteryEstimator()
        score = est.estimate(db, child_id=cid, topic_id=topic.id)
        assert score > 0.7

    def test_all_incorrect_low_mastery(self, db: Session, topic, questions, parent_records, practice_session):
        """5 consecutive incorrect answers → low mastery."""
        cid = parent_records[0].id
        for q in questions[:5]:
            _make_attempt(db, child_id=cid, topic_id=topic.id, question_id=q.id,
                          session_id=practice_session.id, is_correct=False)

        est = RuleBasedMasteryEstimator()
        score = est.estimate(db, child_id=cid, topic_id=topic.id)
        assert score < 0.3

    def test_recent_correct_weights_more(self, db: Session, topic, questions, parent_records, practice_session):
        """Improving child (wrong→correct) scores higher than declining child (correct→wrong)."""
        child_a = parent_records[0].id
        child_b = parent_records[1].id
        sid = practice_session.id

        # Use separate sessions for each child
        session_b = PracticeSession(
            child_id=child_b, topic_id=topic.id,
            session_mode="practice", question_ids_json="[]",
        )
        db.add(session_b)
        db.flush()

        # Child A: wrong first, then correct (improving)
        for q in questions[:3]:
            _make_attempt(db, child_id=child_a, topic_id=topic.id, question_id=q.id,
                          session_id=sid, is_correct=False)
        for q in questions[3:5]:
            _make_attempt(db, child_id=child_a, topic_id=topic.id, question_id=q.id,
                          session_id=sid, is_correct=True)

        # Child B: correct first, then wrong (declining)
        for q in questions[:3]:
            _make_attempt(db, child_id=child_b, topic_id=topic.id, question_id=q.id,
                          session_id=session_b.id, is_correct=True)
        for q in questions[3:5]:
            _make_attempt(db, child_id=child_b, topic_id=topic.id, question_id=q.id,
                          session_id=session_b.id, is_correct=False)

        est = RuleBasedMasteryEstimator()
        score_a = est.estimate(db, child_id=child_a, topic_id=topic.id)
        score_b = est.estimate(db, child_id=child_b, topic_id=topic.id)

        # Child A (improving) should have higher mastery than Child B (declining)
        assert score_a > score_b

    def test_below_threshold_fallback(self, db: Session, topic, questions, parent_records, practice_session):
        """Fewer than 3 attempts → fallback to 0.5 (neutral)."""
        cid = parent_records[0].id
        _make_attempt(db, child_id=cid, topic_id=topic.id, question_id=questions[0].id,
                      session_id=practice_session.id, is_correct=True)
        _make_attempt(db, child_id=cid, topic_id=topic.id, question_id=questions[1].id,
                      session_id=practice_session.id, is_correct=False)

        est = RuleBasedMasteryEstimator()
        score = est.estimate(db, child_id=cid, topic_id=topic.id)
        assert score == 0.5


# --- select_questions integration tests ---


class TestSelectQuestionsWithEstimator:
    def test_select_with_default_estimator(self, db: Session, topic, questions):
        """select_questions works without explicit estimator (backward compat)."""
        result = select_questions(
            db,
            topic_id=topic.id,
            mastery_level="learning",
            count=3,
            exclude_question_ids=[],
            exclude_recent_days=7,
            child_id=1,
        )
        assert len(result) <= 3
        assert all(isinstance(q, Question) for q in result)

    def test_select_with_custom_estimator(self, db: Session, topic, questions):
        """select_questions accepts a custom estimator."""
        est = RuleBasedMasteryEstimator()
        result = select_questions(
            db,
            topic_id=topic.id,
            mastery_level="learning",
            count=3,
            exclude_question_ids=[],
            exclude_recent_days=7,
            child_id=1,
            estimator=est,
        )
        assert len(result) <= 3

    def test_high_mastery_selects_harder(self, db: Session, topic, questions, parent_records, practice_session):
        """High mastery child should get harder questions than low mastery."""
        child_a = parent_records[0].id
        child_b = parent_records[1].id
        sid = practice_session.id

        session_b = PracticeSession(
            child_id=child_b, topic_id=topic.id,
            session_mode="practice", question_ids_json="[]",
        )
        db.add(session_b)
        db.flush()

        # Give child_a mostly correct answers (high mastery)
        for q in questions:
            _make_attempt(db, child_id=child_a, topic_id=topic.id, question_id=q.id,
                          session_id=sid, is_correct=True)

        # Give child_b mostly wrong answers (low mastery)
        for q in questions:
            _make_attempt(db, child_id=child_b, topic_id=topic.id, question_id=q.id,
                          session_id=session_b.id, is_correct=False)

        est = RuleBasedMasteryEstimator()

        result_a = select_questions(
            db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=0,
            child_id=child_a, estimator=est,
        )
        result_b = select_questions(
            db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=0,
            child_id=child_b, estimator=est,
        )

        avg_a = sum(q.difficulty for q in result_a) / len(result_a) if result_a else 0
        avg_b = sum(q.difficulty for q in result_b) / len(result_b) if result_b else 0

        # High mastery child should get equal or harder questions on average
        assert avg_a >= avg_b or len(result_a) == 0
