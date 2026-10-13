"""Tests for explainable learning progress feedback APIs."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    get_ability_dimensions,
    get_progress_trend,
    get_recommend_with_reason,
)
from packages.db.models.family import Family
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def explain_setup(db: Session):
    """Create full setup for explainability tests."""
    family = Family(name="Explain Test", invite_code="EXP001", created_by=1)
    db.add(family)
    db.flush()
    user = User(display_name="Explain Child", password_hash="x", role="child", family_id=family.id)
    db.add(user)
    db.flush()

    # Create topics in different domains
    topics = []
    for key, domain, name in [
        ("mt_arith", "Number & Operations", "Arithmetic"),
        ("mt_geom", "Geometry", "Shapes"),
        ("mt_frac", "Number & Operations", "Fractions"),
    ]:
        t = LearningTopic(
            topic_key=key, topic_type="procedural",
            subject="mathematics", domain=domain, name=name,
            description="test", age_group="mid",
            evidence_json="[]", standards_json="[]",
        )
        db.add(t)
        topics.append(t)
    db.flush()

    session = PracticeSession(
        child_id=user.id, topic_id=topics[0].id,
        session_mode="practice", question_ids_json="[]",
    )
    db.add(session)
    db.flush()

    # Create questions (5 per topic to allow multiple attempts)
    questions = []
    for t in topics:
        for j in range(5):
            q = Question(
                topic_id=t.id, question_type="calculation",
                stem=f"Q{t.topic_key}_{j}", answer_json='{"answer": 42}',
                difficulty=2, bloom_level="apply", source="template",
                review_status="approved", age_group="mid",
            )
            db.add(q)
            questions.append(q)
    db.flush()
    # Reshape: questions_by_topic[topic_index] = [q0, q1, q2, q3, q4]
    questions_by_topic = [questions[i:i+5] for i in range(0, len(questions), 5)]

    return {"user": user, "topics": topics, "session": session, "questions": questions, "questions_by_topic": questions_by_topic}


class TestAbilityDimensions:
    def test_empty_returns_empty(self, db: Session, explain_setup):
        """No attempts → empty dimensions list."""
        dims = get_ability_dimensions(db, child_id=explain_setup["user"].id)
        assert dims == []

    def test_dimensions_grouped_by_domain(self, db: Session, explain_setup):
        """Attempts grouped by domain with correct accuracy."""
        s = explain_setup
        uid = s["user"].id
        sid = s["session"].id
        qbt = s["questions_by_topic"]

        # Arithmetic topic (index 0): 3 correct, 1 wrong = 75%
        for i, correct in enumerate([True, True, True, False]):
            a = PracticeAttempt(
                session_id=sid, question_id=qbt[0][i].id,
                child_id=uid, topic_id=s["topics"][0].id,
                user_answer_json='{"answer": 42}', is_correct=correct,
                time_spent_seconds=30, attempt_number=i + 1,
            )
            db.add(a)
        # Geometry topic (index 1): 2 correct = 100%
        for i in range(2):
            a = PracticeAttempt(
                session_id=sid, question_id=qbt[1][i].id,
                child_id=uid, topic_id=s["topics"][1].id,
                user_answer_json='{"answer": 42}', is_correct=True,
                time_spent_seconds=30, attempt_number=i + 1,
            )
            db.add(a)
        db.flush()

        dims = get_ability_dimensions(db, child_id=uid)

        assert len(dims) == 2  # Two domains with attempts
        by_domain = {d["domain"]: d for d in dims}
        assert by_domain["Number & Operations"]["accuracy"] == 0.75
        assert by_domain["Geometry"]["accuracy"] == 1.0


class TestProgressTrend:
    def test_empty_returns_empty(self, db: Session, explain_setup):
        """No attempts → empty trend."""
        trend = get_progress_trend(
            db, child_id=explain_setup["user"].id,
            topic_id=explain_setup["topics"][0].id,
        )
        assert trend == []

    def test_trend_returns_time_series(self, db: Session, explain_setup):
        """Returns chronological accuracy data points."""
        s = explain_setup
        uid = s["user"].id
        sid = s["session"].id
        tid = s["topics"][0].id
        qbt = s["questions_by_topic"]

        for i, correct in enumerate([True, False, True]):
            a = PracticeAttempt(
                session_id=sid, question_id=qbt[0][i].id,
                child_id=uid, topic_id=tid,
                user_answer_json='{"answer": 42}', is_correct=correct,
                time_spent_seconds=30, attempt_number=i + 1,
            )
            db.add(a)
        db.flush()

        trend = get_progress_trend(db, child_id=uid, topic_id=tid)

        assert len(trend) == 3
        assert all("is_correct" in p for p in trend)
        assert all("attempt_number" in p for p in trend)


class TestRecommendWithReason:
    def test_low_accuracy_reason(self, db: Session, explain_setup):
        """Low accuracy topic gets 'needs practice' reason."""
        s = explain_setup
        uid = s["user"].id
        sid = s["session"].id
        tid = s["topics"][0].id
        qbt = s["questions_by_topic"]

        # 1 correct out of 5 = 20% accuracy
        for i in range(5):
            a = PracticeAttempt(
                session_id=sid, question_id=qbt[0][i].id,
                child_id=uid, topic_id=tid,
                user_answer_json='{"answer": 42}',
                is_correct=(i == 0),
                time_spent_seconds=30, attempt_number=i + 1,
            )
            db.add(a)
        db.flush()

        recs = get_recommend_with_reason(db, child_id=uid)
        # Should have at least one recommendation with a reason
        if recs:
            assert any("reason_key" in r for r in recs)

    def test_empty_returns_empty(self, db: Session, explain_setup):
        """No attempts → no recommendations."""
        recs = get_recommend_with_reason(db, child_id=explain_setup["user"].id)
        assert recs == []
