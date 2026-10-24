"""Tests for Phase 5b: prerequisite weak practice."""

import json
import pytest
from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic, LearningDependency
from packages.db.models.learning.question import Question
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt
from packages.db.models.learning.progress import LearningProgress
from apps.backend.app.services.learning.adaptive_service import (
    find_weak_prerequisites,
)


@pytest.fixture
def parent_topic(db: Session):
    t = LearningTopic(
        topic_key="mt_p5_parent",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Multi-digit Addition",
        name_zh="多位数加法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def prereq_topic(db: Session):
    t = LearningTopic(
        topic_key="mt_p5_prereq",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Single-digit Addition",
        name_zh="一位数加法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def dependency(db: Session, parent_topic, prereq_topic):
    d = LearningDependency(
        topic_id=parent_topic.id,
        prerequisite_id=prereq_topic.id,
        strength="hard",
    )
    db.add(d)
    db.flush()
    return d


def test_find_weak_prerequisites_returns_unmet(
    db: Session, parent_topic, prereq_topic, dependency
):
    """Unmet prerequisite with non-mastered progress is returned."""
    progress = LearningProgress(
        child_id=1,
        topic_id=prereq_topic.id,
        mastery_level="learning",
    )
    db.add(progress)
    db.flush()

    weak_prereqs = find_weak_prerequisites(
        db, topic_id=parent_topic.id, child_id=1
    )
    assert len(weak_prereqs) == 1
    assert weak_prereqs[0]["topic_id"] == prereq_topic.id
    assert weak_prereqs[0]["topic_name"] == "Single-digit Addition"
    assert weak_prereqs[0]["mastery_level"] == "learning"


def test_find_weak_prerequisites_enriches_accuracy(
    db: Session, parent_topic, prereq_topic, dependency
):
    """Accuracy data from PracticeAttempt is included."""
    progress = LearningProgress(
        child_id=1,
        topic_id=prereq_topic.id,
        mastery_level="learning",
    )
    db.add(progress)

    q = Question(
        topic_id=prereq_topic.id,
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

    # 1 correct, 1 wrong → accuracy 0.5 (separate sessions for UQ constraint)
    s1 = PracticeSession(
        child_id=1, topic_id=prereq_topic.id, session_mode="practice",
        question_ids_json=json.dumps([q.id]), source="adaptive",
    )
    db.add(s1)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s1.id, question_id=q.id, child_id=1,
        topic_id=prereq_topic.id, user_answer_json='{"answer": 2}',
        is_correct=True, time_spent_seconds=10, attempt_number=1,
    ))

    s2 = PracticeSession(
        child_id=1, topic_id=prereq_topic.id, session_mode="practice",
        question_ids_json=json.dumps([q.id]), source="adaptive",
    )
    db.add(s2)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s2.id, question_id=q.id, child_id=1,
        topic_id=prereq_topic.id, user_answer_json='{"answer": 3}',
        is_correct=False, time_spent_seconds=8, attempt_number=1,
    ))
    db.flush()

    weak_prereqs = find_weak_prerequisites(
        db, topic_id=parent_topic.id, child_id=1
    )
    assert len(weak_prereqs) == 1
    assert weak_prereqs[0]["total_attempts"] == 2
    assert weak_prereqs[0]["accuracy"] == 0.5


def test_find_weak_prerequisites_empty_when_mastered(
    db: Session, parent_topic, prereq_topic, dependency
):
    """Mastered prerequisites are not returned."""
    progress = LearningProgress(
        child_id=1,
        topic_id=prereq_topic.id,
        mastery_level="mastered",
    )
    db.add(progress)
    db.flush()

    weak_prereqs = find_weak_prerequisites(
        db, topic_id=parent_topic.id, child_id=1
    )
    assert len(weak_prereqs) == 0


def test_find_weak_prerequisites_sorted_by_accuracy(
    db: Session, parent_topic
):
    """Multiple weak prereqs sorted by accuracy ASC."""
    # Create two prereq topics (no pre-existing dependency fixture)
    prereq1 = LearningTopic(
        topic_key="mt_p5_pr1", topic_type="concept", subject="mathematics",
        domain="arithmetic", name="Prereq1", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    prereq2 = LearningTopic(
        topic_key="mt_p5_pr2", topic_type="concept", subject="mathematics",
        domain="arithmetic", name="Prereq2", age_group="mid",
        evidence_json="[]", standards_json="[]",
    )
    db.add_all([prereq1, prereq2])
    db.flush()

    db.add(LearningDependency(
        topic_id=parent_topic.id, prerequisite_id=prereq1.id, strength="hard"
    ))
    db.add(LearningDependency(
        topic_id=parent_topic.id, prerequisite_id=prereq2.id, strength="hard"
    ))
    db.flush()

    # prereq1: 0% accuracy (worse), prereq2: 50% accuracy
    # prereq1 — 2 wrong attempts (separate sessions)
    db.add(LearningProgress(
        child_id=1, topic_id=prereq1.id, mastery_level="learning"
    ))
    q1 = Question(
        topic_id=prereq1.id, question_type="calculation",
        stem="Q1", answer_json='{"answer": 1}',
        difficulty=1, bloom_level="apply", source="template",
        review_status="approved", age_group="mid",
    )
    db.add(q1)
    db.flush()

    for attempt_idx in range(2):
        s1 = PracticeSession(
            child_id=1, topic_id=prereq1.id, session_mode="practice",
            question_ids_json=json.dumps([q1.id]), source="adaptive",
        )
        db.add(s1)
        db.flush()
        db.add(PracticeAttempt(
            session_id=s1.id, question_id=q1.id, child_id=1,
            topic_id=prereq1.id, user_answer_json='{"answer": 99}',
            is_correct=False, time_spent_seconds=5, attempt_number=1,
        ))

    # prereq2 — 1 correct + 1 wrong (separate sessions)
    db.add(LearningProgress(
        child_id=1, topic_id=prereq2.id, mastery_level="learning"
    ))
    q2 = Question(
        topic_id=prereq2.id, question_type="calculation",
        stem="Q2", answer_json='{"answer": 1}',
        difficulty=1, bloom_level="apply", source="template",
        review_status="approved", age_group="mid",
    )
    db.add(q2)
    db.flush()

    s2_correct = PracticeSession(
        child_id=1, topic_id=prereq2.id, session_mode="practice",
        question_ids_json=json.dumps([q2.id]), source="adaptive",
    )
    db.add(s2_correct)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s2_correct.id, question_id=q2.id, child_id=1,
        topic_id=prereq2.id, user_answer_json='{"answer": 1}',
        is_correct=True, time_spent_seconds=5, attempt_number=1,
    ))

    s2_wrong = PracticeSession(
        child_id=1, topic_id=prereq2.id, session_mode="practice",
        question_ids_json=json.dumps([q2.id]), source="adaptive",
    )
    db.add(s2_wrong)
    db.flush()
    db.add(PracticeAttempt(
        session_id=s2_wrong.id, question_id=q2.id, child_id=1,
        topic_id=prereq2.id, user_answer_json='{"answer": 99}',
        is_correct=False, time_spent_seconds=5, attempt_number=1,
    ))
    db.flush()

    weak_prereqs = find_weak_prerequisites(
        db, topic_id=parent_topic.id, child_id=1
    )
    assert len(weak_prereqs) == 2
    # Weakest first
    assert weak_prereqs[0]["topic_id"] == prereq1.id
    assert weak_prereqs[0]["accuracy"] == 0.0
    assert weak_prereqs[1]["topic_id"] == prereq2.id
    assert weak_prereqs[1]["accuracy"] == 0.5
