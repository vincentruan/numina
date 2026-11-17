"""Tests for misconception-aware adaptive question selection (#214 U3)."""

import json

import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(db: Session) -> LearningTopic:
    t = LearningTopic(
        topic_key="mt_boost_test", topic_type="concept",
        subject="mathematics", domain="arithmetic",
        name="Boost test", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def diagnostic_question(db: Session, topic: LearningTopic) -> Question:
    q = Question(
        topic_id=topic.id, question_type="calculation",
        stem="Diagnostic Q", stem_zh="诊断题",
        answer_json=json.dumps({"answer": "1"}),
        difficulty=5,  # intentionally outside typical range
        bloom_level="apply", source="test", age_group="mid",
        review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


@pytest.fixture
def misconception_with_diagnostic(
    db: Session, topic: LearningTopic, diagnostic_question: Question
) -> Misconception:
    m = Misconception(
        topic_id=topic.id, sequence=0,
        error_pattern_json=json.dumps(
            {"match_type": "symbolic", "expected_wrong": "2/7"}
        ),
        description="Test misconception",
        age_group="mid",
        diagnostic_question_id=diagnostic_question.id,
        review_status="approved",
        category="concept_confusion",
    )
    db.add(m)
    db.flush()
    return m


@pytest.fixture
def regular_question(db: Session, topic: LearningTopic) -> Question:
    q = Question(
        topic_id=topic.id, question_type="calculation",
        stem="Regular Q", stem_zh="普通题",
        answer_json=json.dumps({"answer": "3"}),
        difficulty=2, bloom_level="apply",
        source="test", age_group="mid", review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


class TestSelectQuestionsMisconceptionBoost:
    def test_no_boost_when_misconception_ids_none(
        self, db, topic, regular_question
    ):
        """Without misconception_ids, behavior is unchanged (backward compat)."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=7,
            child_id=1, misconception_ids=None,
        )
        assert len(result) == 1
        assert result[0].id == regular_question.id

    def test_empty_misconception_ids_no_boost(
        self, db, topic, regular_question
    ):
        """Empty set behaves like None."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=7,
            child_id=1, misconception_ids=set(),
        )
        assert len(result) == 1
        assert result[0].id == regular_question.id

    def test_diagnostic_question_boosted_to_front(
        self, db, topic, misconception_with_diagnostic,
        diagnostic_question, regular_question
    ):
        """Diagnostic question for a detected misconception is boosted first."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=7,
            child_id=1,
            misconception_ids={misconception_with_diagnostic.id},
        )
        assert len(result) == 2
        # The diagnostic question is boosted to position 0.
        assert result[0].id == diagnostic_question.id

    def test_diagnostic_question_injected_outside_difficulty_range(
        self, db, topic, misconception_with_diagnostic,
        diagnostic_question
    ):
        """Diagnostic question outside the child's difficulty range is still injected."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        # mastery_level="available" → difficulty range 1-2. The diagnostic
        # question has difficulty=5 — it should still be injected.
        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="available",
            count=5, exclude_question_ids=[], exclude_recent_days=7,
            child_id=1,
            misconception_ids={misconception_with_diagnostic.id},
        )
        ids = [q.id for q in result]
        assert diagnostic_question.id in ids

    def test_no_boost_when_diagnostic_question_id_null(
        self, db, topic, regular_question
    ):
        """Misconception without linked diagnostic question → no boost."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        m = Misconception(
            topic_id=topic.id, sequence=0,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "x"}),
            description="No diag question",
            age_group="mid",
            diagnostic_question_id=None,
            review_status="approved",
            category="concept_confusion",
        )
        db.add(m)
        db.flush()

        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="learning",
            count=5, exclude_question_ids=[], exclude_recent_days=7,
            child_id=1, misconception_ids={m.id},
        )
        assert len(result) == 1
        assert result[0].id == regular_question.id

    def test_diagnostic_question_in_exclusion_set_not_boosted(
        self, db, topic, misconception_with_diagnostic,
        diagnostic_question, regular_question
    ):
        """Diagnostic already in exclude_set is skipped."""
        from apps.backend.app.services.learning.adaptive_service import (
            select_questions,
        )
        result = select_questions(
            db=db, topic_id=topic.id, mastery_level="learning",
            count=5,
            exclude_question_ids=[diagnostic_question.id],
            exclude_recent_days=7,
            child_id=1,
            misconception_ids={misconception_with_diagnostic.id},
        )
        ids = [q.id for q in result]
        assert diagnostic_question.id not in ids
        assert regular_question.id in ids
