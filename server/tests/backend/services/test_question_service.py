"""Tests for question CRUD and quality gate."""
import pytest
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError
from apps.backend.app.services.learning.question_service import (
    create_question,
    get_question,
    list_questions,
    validate_question,
)
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session):
    t = LearningTopic(
        topic_key="mt_q_svc",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


def test_create_question(db: Session, topic):
    q = create_question(
        db=db,
        topic_id=topic.id,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        answer={"answer": 95},
        difficulty=1,
        bloom_level="apply",
        source="template",
        age_group="mid",
    )
    assert q.id is not None
    assert q.review_status == "approved"


def test_create_question_invalid_topic(db: Session):
    with pytest.raises(AppError):
        create_question(
            db=db,
            topic_id=999999,
            question_type="calculation",
            stem="Test",
            answer={"answer": 1},
            difficulty=1,
            bloom_level="apply",
            source="template",
            age_group="mid",
        )


def test_validate_question_passes(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="calculation",
        stem="Test",
        answer={"answer": 95},
        age_group="mid",
        db=db,
    )
    assert errors == []


def test_validate_question_empty_stem(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="calculation",
        stem="",
        answer={"answer": 95},
        age_group="mid",
        db=db,
    )
    assert len(errors) > 0
    assert any("stem" in e.lower() for e in errors)


def test_validate_question_multiple_choice_missing_options(db: Session, topic):
    errors = validate_question(
        topic_id=topic.id,
        question_type="multiple_choice",
        stem="Test",
        answer={"key": "A"},
        options=None,
        age_group="mid",
        db=db,
    )
    assert len(errors) > 0


def test_list_questions_by_topic(db: Session, topic):
    create_question(
        db=db,
        topic_id=topic.id,
        question_type="calculation",
        stem="Q1",
        answer={"answer": 1},
        difficulty=1,
        bloom_level="apply",
        source="template",
        age_group="mid",
    )
    create_question(
        db=db,
        topic_id=topic.id,
        question_type="calculation",
        stem="Q2",
        answer={"answer": 2},
        difficulty=2,
        bloom_level="apply",
        source="template",
        age_group="mid",
    )
    qs = list_questions(db=db, topic_id=topic.id)
    assert len(qs) == 2
