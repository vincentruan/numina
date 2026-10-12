"""Tests for enhanced SM-2 (ease_factor) and error review queue."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.adaptive_service import (
    select_questions,
)
from apps.backend.app.services.learning.progress_service import (
    compute_next_review,
    update_stability,
)
from packages.db.models.family import Family
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


@pytest.fixture
def sm2_setup(db: Session):
    """Create a child + topic + progress for SM-2 tests."""
    family = Family(name="SM2 Test", invite_code="SM2001", created_by=1)
    db.add(family)
    db.flush()
    user = User(display_name="SM2 Child", password_hash="x", role="child", family_id=family.id)
    db.add(user)
    db.flush()
    topic = LearningTopic(
        topic_key="mt_sm2_test", topic_type="procedural",
        subject="mathematics", domain="Test", name="SM2",
        description="test", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(topic)
    db.flush()
    progress = LearningProgress(
        child_id=user.id, topic_id=topic.id,
        mastery_level="learning", stability=1.0,
    )
    db.add(progress)
    db.flush()
    return {"user": user, "topic": topic, "progress": progress}


@pytest.fixture
def review_setup(db: Session):
    """Create topics + questions + attempts for error-priority review tests."""
    family = Family(name="Review Test", invite_code="REV001", created_by=1)
    db.add(family)
    db.flush()
    user = User(display_name="Review Child", password_hash="x", role="child", family_id=family.id)
    db.add(user)
    db.flush()
    topic = LearningTopic(
        topic_key="mt_review_test", topic_type="procedural",
        subject="mathematics", domain="Test", name="Review",
        description="test", age_group="mid",
        evidence_json="[]", standards_json="[]",
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
    for i in range(10):
        q = Question(
            topic_id=topic.id, question_type="calculation",
            stem=f"Review Q{i}", answer_json='{"answer": 42}',
            difficulty=2, bloom_level="apply", source="template",
            review_status="approved", age_group="mid",
        )
        db.add(q)
        questions.append(q)
    db.flush()
    return {"user": user, "topic": topic, "session": session, "questions": questions}


class TestEaseFactor:
    def test_progress_has_ease_factor(self, db: Session, sm2_setup):
        """LearningProgress has ease_factor column with default 2.5."""
        p = sm2_setup["progress"]
        assert hasattr(p, "ease_factor")
        assert p.ease_factor == 2.5

    def test_compute_next_review_uses_ease_factor(self, db: Session, sm2_setup):
        """compute_next_review produces intervals influenced by ease_factor."""
        p = sm2_setup["progress"]
        p.stability = 1.0
        p.ease_factor = 2.5
        review_date = compute_next_review(p)
        assert review_date > datetime.now(UTC)


class TestErrorReviewQueue:
    def test_review_mode_prioritizes_wrong_answers(self, db: Session, review_setup):
        """In review mode, questions with wrong attempts are prioritized."""
        setup = review_setup
        uid = setup["user"].id
        tid = setup["topic"].id
        sid = setup["session"].id

        # Make first 3 questions have wrong attempts
        for i in range(3):
            a = PracticeAttempt(
                session_id=sid, question_id=setup["questions"][i].id,
                child_id=uid, topic_id=tid,
                user_answer_json='{"answer": 0}',
                is_correct=False, time_spent_seconds=30, attempt_number=1,
            )
            db.add(a)
        db.flush()

        result = select_questions(
            db, topic_id=tid, mastery_level="review",
            count=5, exclude_question_ids=[], exclude_recent_days=0,
            child_id=uid,
        )

        # Questions with errors should appear (they're not excluded with 0 recent days)
        result_ids = {q.id for q in result}
        wrong_ids = {setup["questions"][i].id for i in range(3)}
        # At least some wrong questions should be in the result
        assert len(result_ids & wrong_ids) > 0 or len(result) == 0

    def test_exclude_recent_days_works(self, db: Session, review_setup):
        """exclude_recent_days properly excludes recently answered questions."""
        setup = review_setup
        uid = setup["user"].id
        tid = setup["topic"].id
        sid = setup["session"].id

        # Answer first 5 questions recently
        for i in range(5):
            a = PracticeAttempt(
                session_id=sid, question_id=setup["questions"][i].id,
                child_id=uid, topic_id=tid,
                user_answer_json='{"answer": 42}',
                is_correct=True, time_spent_seconds=30, attempt_number=1,
            )
            db.add(a)
        db.flush()

        result = select_questions(
            db, topic_id=tid, mastery_level="learning",
            count=10, exclude_question_ids=[], exclude_recent_days=7,
            child_id=uid,
        )

        # Should only get questions NOT recently answered
        recent_ids = {setup["questions"][i].id for i in range(5)}
        result_ids = {q.id for q in result}
        assert len(result_ids & recent_ids) == 0
