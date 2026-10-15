"""Tests for question and practice ORM models."""
import pytest

from packages.db.models.learning.question import Question, QuestionKnowledgePoint
from packages.db.models.learning.practice import PracticeSession, PracticeAttempt
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic(packages_db):
    t = LearningTopic(
        topic_key="mt_test_math",
        topic_type="concept",
        subject="mathematics",
        domain="arithmetic",
        name="Two-digit addition",
        name_zh="两位数加法",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    packages_db.add(t)
    packages_db.flush()
    return t


def test_question_creation(packages_db, topic):
    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="37 + 58 = ?",
        stem_zh="计算：37 + 58 = ?",
        answer_json='{"answer": 95}',
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    packages_db.add(q)
    packages_db.flush()
    assert q.id is not None
    assert q.topic_id == topic.id
    assert q.times_used == 0


def test_question_json_accessors(packages_db, topic):
    q = Question(
        topic_id=topic.id,
        question_type="multiple_choice",
        stem="Which is prime?",
        options_json='[{"key":"A","text":"4"},{"key":"B","text":"7"}]',
        answer_json='{"key": "B"}',
        difficulty=2,
        bloom_level="understand",
        source="human_created",
        review_status="approved",
        age_group="mid",
    )
    packages_db.add(q)
    packages_db.flush()
    assert q.options == [{"key": "A", "text": "4"}, {"key": "B", "text": "7"}]
    assert q.answer == {"key": "B"}


def test_practice_session_creation(packages_db, topic):
    s = PracticeSession(
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[1,2,3]",
        source="adaptive",
    )
    packages_db.add(s)
    packages_db.flush()
    assert s.id is not None
    assert s.question_ids == [1, 2, 3]


def test_practice_attempt_creation(packages_db, topic):
    s = PracticeSession(
        child_id=1,
        topic_id=topic.id,
        session_mode="practice",
        question_ids_json="[1]",
        source="adaptive",
    )
    packages_db.add(s)
    packages_db.flush()
    a = PracticeAttempt(
        session_id=s.id,
        question_id=1,
        child_id=1,
        topic_id=topic.id,
        user_answer_json='{"answer": 95}',
        is_correct=True,
        time_spent_seconds=15,
        attempt_number=1,
    )
    packages_db.add(a)
    packages_db.flush()
    assert a.id is not None
    assert a.user_answer == {"answer": 95}
