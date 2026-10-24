"""Tests for practice → progress state machine integration."""
import json

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.practice_progress_integration import (
    update_progress_from_session,
)
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    submit_answer,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_integration",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Integration test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def questions(db: Session, topic):
    qs = []
    for i in range(5):
        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem=f"Q{i}",
            answer_json=json.dumps({"answer": i + 1}),
            difficulty=1,
            bloom_level="apply",
            source="template",
            review_status="approved",
            age_group="mid",
        )
        db.add(q)
        qs.append(q)
    db.flush()
    return qs


def test_high_score_transitions_learning_to_assessing(
    db: Session, topic, questions
):
    """Score >= 0.8: learning → assessing."""
    progress = LearningProgress(
        child_id=1, topic_id=topic.id, mastery_level="learning"
    )
    db.add(progress)
    db.flush()

    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:5]],
    )
    # All correct → score 1.0
    for q in questions[:5]:
        submit_answer(
            db=db,
            session_id=session.id,
            question_id=q.id,
            child_id=1,
            topic_id=topic.id,
            user_answer={"answer": q.answer["answer"]},
            time_spent_seconds=10,
        )
    finish_session(db=db, session_id=session.id, child_id=1)

    result = update_progress_from_session(
        db=db, session_id=session.id, child_id=1
    )
    assert result["mastery_changed"] is True
    assert result["new_mastery_level"] == "assessing"
    assert progress.mastery_level == "assessing"


def test_low_score_does_not_transition(db: Session, topic, questions):
    """Score < 0.5: no state transition, mastery_score updated."""
    progress = LearningProgress(
        child_id=1, topic_id=topic.id, mastery_level="learning"
    )
    db.add(progress)
    db.flush()

    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:4]],
    )
    # All wrong
    for q in questions[:4]:
        submit_answer(
            db=db,
            session_id=session.id,
            question_id=q.id,
            child_id=1,
            topic_id=topic.id,
            user_answer={"answer": 99999},
            time_spent_seconds=10,
        )
    finish_session(db=db, session_id=session.id, child_id=1)

    result = update_progress_from_session(
        db=db, session_id=session.id, child_id=1
    )
    assert result["mastery_changed"] is False
    assert progress.mastery_level == "learning"
