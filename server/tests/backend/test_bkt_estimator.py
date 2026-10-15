"""Tests for Bayesian Knowledge Tracing (BKT) estimator."""

import json

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    BayesianKnowledgeTracingEstimator,
    RuleBasedMasteryEstimator,
)
from packages.db.models.family import Family
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def bkt_setup(db: Session):
    """Create topic, user, session, and questions for BKT tests."""
    family = Family(name="BKT Test", invite_code="BKT001", created_by=1)
    db.add(family)
    db.flush()

    user = User(display_name="BKT Child", password_hash="x", role="child", family_id=family.id)
    db.add(user)
    db.flush()

    topic = LearningTopic(
        topic_key="mt_bkt_test",
        topic_type="procedural",
        subject="mathematics",
        domain="Test",
        name="BKT Test",
        description="test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    session = PracticeSession(
        child_id=user.id, topic_id=topic.id,
        session_mode="practice", question_ids_json="[]",
    )
    db.add(session)
    db.flush()

    questions = []
    for i in range(60):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"BKT Q{i}",
            answer_json='{"answer": 42}',
            difficulty=2,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        questions.append(q)
    db.flush()

    return {"user": user, "topic": topic, "session": session, "questions": questions}


_attempt_counters: dict = {}


def _add_attempt(db, setup, is_correct):
    """Add an attempt, cycling through questions to avoid UNIQUE constraint."""
    key = (setup["user"].id, setup["topic"].id)
    idx = _attempt_counters.get(key, 0)
    _attempt_counters[key] = idx + 1
    q = setup["questions"][idx % len(setup["questions"])]
    a = PracticeAttempt(
        session_id=setup["session"].id,
        question_id=q.id,
        child_id=setup["user"].id,
        topic_id=setup["topic"].id,
        user_answer_json='{"answer": 42}',
        is_correct=is_correct,
        time_spent_seconds=30,
        attempt_number=1,
    )
    db.add(a)
    db.flush()


class TestBayesianKnowledgeTracingEstimator:
    def test_no_attempts_fallback_to_rulebased(self, db: Session, bkt_setup):
        """With no attempts, BKT falls back to RuleBased."""
        est = BayesianKnowledgeTracingEstimator()
        bkt_score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        rb = RuleBasedMasteryEstimator()
        rb_score = rb.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        # Both should return neutral/low for no data
        assert 0.0 <= bkt_score <= 1.0
        assert bkt_score == rb_score  # Both fallback

    def test_correct_answers_increase_mastery(self, db: Session, bkt_setup):
        """Consecutive correct answers should monotonically increase P(L).

        Standard BKT (no forgetting): P(L) is monotonically non-decreasing
        with correct observations, converging toward 1.0.
        """
        est = BayesianKnowledgeTracingEstimator()
        scores = []
        for _ in range(10):
            _add_attempt(db, bkt_setup, is_correct=True)
            score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
            scores.append(score)

        # P(L) should be monotonically non-decreasing (allow float jitter up to 0.01)
        for i in range(1, len(scores)):
            assert scores[i] >= scores[i - 1] - 0.01
        # Should reach meaningful mastery after 10 correct
        assert scores[-1] > 0.8

    def test_mistake_does_not_zero_mastery(self, db: Session, bkt_setup):
        """A single mistake after correct answers should not zero out mastery."""
        est = BayesianKnowledgeTracingEstimator()

        # 5 correct answers
        for _ in range(5):
            _add_attempt(db, bkt_setup, is_correct=True)

        score_before = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)

        # 1 mistake
        _add_attempt(db, bkt_setup, is_correct=False)

        score_after = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)

        # Mastery should decrease slightly but not to zero
        assert score_after > 0.0
        assert score_after < score_before

    def test_convergence_after_many_correct(self, db: Session, bkt_setup):
        """After many correct attempts, P(L) converges close to 1.0.

        Standard BKT (no forgetting in transition): P(L|correct) increases
        monotonically toward 1.0. After 50 correct answers, should be > 0.95.
        """
        est = BayesianKnowledgeTracingEstimator()

        for _ in range(50):
            _add_attempt(db, bkt_setup, is_correct=True)

        score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        assert score > 0.95

    def test_below_threshold_fallback(self, db: Session, bkt_setup):
        """< 5 attempts → fallback to RuleBased."""
        est = BayesianKnowledgeTracingEstimator()

        for i in range(3):
            _add_attempt(db, bkt_setup, is_correct=(i % 2 == 0))

        bkt_score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        rb = RuleBasedMasteryEstimator()
        rb_score = rb.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)

        # Should fallback to RuleBased
        assert abs(bkt_score - rb_score) < 0.001

    def test_exactly_4_attempts_fallback(self, db: Session, bkt_setup):
        """Exactly 4 attempts → still fallback to RuleBased (boundary, TF-004)."""
        est = BayesianKnowledgeTracingEstimator()

        for i in range(4):
            _add_attempt(db, bkt_setup, is_correct=(i % 2 == 0))

        bkt_score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        rb_score = RuleBasedMasteryEstimator().estimate(
            db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id
        )
        assert abs(bkt_score - rb_score) < 0.001

    def test_exactly_5_attempts_uses_bkt(self, db: Session, bkt_setup):
        """Exactly 5 attempts → BKT forward algorithm (boundary, TF-004)."""
        est = BayesianKnowledgeTracingEstimator()

        for i in range(5):
            _add_attempt(db, bkt_setup, is_correct=(i % 2 == 0))

        bkt_score = est.estimate(db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id)
        rb_score = RuleBasedMasteryEstimator().estimate(
            db, child_id=bkt_setup["user"].id, topic_id=bkt_setup["topic"].id
        )
        # With alternating answers BKT (optimistic, knowledge only grows)
        # diverges from RuleBased — a distinct score proves BKT is active.
        assert abs(bkt_score - rb_score) > 0.001

    def test_default_params(self):
        """BKT default parameters match standard values."""
        est = BayesianKnowledgeTracingEstimator()
        assert est.p_l0 == 0.1
        assert est.p_t == 0.3
        assert est.p_g == 0.25
        assert est.p_s == 0.1
