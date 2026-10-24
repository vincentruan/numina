"""Tests for practice session management service."""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    get_session,
    submit_answer,
)
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_practice_svc",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Practice topic",
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
            answer_json=f'{{"answer": {i + 1}}}',
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


@pytest.fixture
def progress(db: Session, topic):
    p = LearningProgress(
        child_id=1,
        topic_id=topic.id,
        mastery_level="learning",
    )
    db.add(p)
    db.flush()
    return p


def test_create_session(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:3]],
    )
    assert session.id is not None
    assert session.child_id == 1
    assert session.question_ids == [
        questions[0].id,
        questions[1].id,
        questions[2].id,
    ]
    assert session.completed_count == 0


def test_submit_answer(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    attempt = submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": questions[0].answer["answer"]},
        time_spent_seconds=10,
    )
    assert attempt.is_correct is True


def test_submit_answer_wrong(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    attempt = submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": 99999},
        time_spent_seconds=10,
    )
    assert attempt.is_correct is False


def test_submit_duplicate_raises(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": 1},
        time_spent_seconds=10,
    )
    with pytest.raises(AppError):
        submit_answer(
            db=db,
            session_id=session.id,
            question_id=questions[0].id,
            child_id=1,
            topic_id=topic.id,
            user_answer={"answer": 2},
            time_spent_seconds=5,
        )


def test_finish_session_calculates_score(db: Session, topic, questions, progress):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[q.id for q in questions[:4]],
    )
    # 3 correct, 1 wrong → score = 0.75
    for i in range(4):
        correct_answer = questions[i].answer["answer"]
        user_answer = correct_answer if i < 3 else 99999
        submit_answer(
            db=db,
            session_id=session.id,
            question_id=questions[i].id,
            child_id=1,
            topic_id=topic.id,
            user_answer={"answer": user_answer},
            time_spent_seconds=10,
        )

    result = finish_session(db=db, session_id=session.id, child_id=1)
    assert result["total_score"] == 0.75
    assert result["correct_count"] == 3
    assert result["total_count"] == 4
    assert session.ended_at is not None


def test_finish_session_already_ended_raises(db: Session, topic, questions):
    session = create_session(
        db=db,
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids=[questions[0].id],
    )
    submit_answer(
        db=db,
        session_id=session.id,
        question_id=questions[0].id,
        child_id=1,
        topic_id=topic.id,
        user_answer={"answer": 1},
        time_spent_seconds=10,
    )
    finish_session(db=db, session_id=session.id, child_id=1)
    with pytest.raises(AppError):
        finish_session(db=db, session_id=session.id, child_id=1)
