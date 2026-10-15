"""Tests for coverage stats API and question dedup."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.question_service import (
    check_duplicate,
    get_coverage_stats,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topics_for_coverage(db: Session):
    """Create a set of topics across different subjects."""
    topics_data = [
        ("mt_math_1", "mathematics", "Arithmetic"),
        ("mt_math_2", "mathematics", "Geometry"),
        ("mt_sci_1", "science", "Physics"),
        ("mt_sci_2", "science", "Biology"),
        ("mt_eng_1", "english", "Grammar"),
    ]
    topics = []
    for key, subject, name in topics_data:
        t = LearningTopic(
            topic_key=key,
            topic_type="conceptual",
            subject=subject,
            domain=name,
            name=name,
            description="test",
            age_group="mid",
            evidence_json="[]",
            standards_json="[]",
        )
        db.add(t)
        topics.append(t)
    db.flush()
    return topics


def _make_question(db: Session, topic_id: int, stem: str, difficulty: int = 1) -> Question:
    """Helper to create a question directly."""
    import json
    from apps.backend.app.services.learning.question_seeder import _compute_content_hash

    answer = {"answer": 42}
    q = Question(
        topic_id=topic_id,
        question_type="calculation",
        stem=stem,
        answer_json=json.dumps(answer),
        difficulty=difficulty,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
        content_hash=_compute_content_hash(stem, answer),
    )
    db.add(q)
    db.flush()
    return q


def test_coverage_empty_db(db: Session, topics_for_coverage):
    """Empty question bank returns zero coverage."""
    stats = get_coverage_stats(db)

    assert stats["total_topics"] == 5
    assert stats["covered_topics"] == 0
    assert stats["coverage_rate"] == 0.0
    assert stats["by_difficulty"] == {}


def test_coverage_with_questions(db: Session, topics_for_coverage):
    """Coverage correctly counts topics with questions."""
    # Add questions to 2 of 5 topics
    _make_question(db, topics_for_coverage[0].id, "1+1=?")
    _make_question(db, topics_for_coverage[0].id, "2+2=?")
    _make_question(db, topics_for_coverage[2].id, "Force=?")

    stats = get_coverage_stats(db)

    assert stats["total_topics"] == 5
    assert stats["covered_topics"] == 2
    assert abs(stats["coverage_rate"] - 0.4) < 0.01


def test_coverage_by_difficulty(db: Session, topics_for_coverage):
    """Difficulty distribution is correct."""
    _make_question(db, topics_for_coverage[0].id, "q1", difficulty=1)
    _make_question(db, topics_for_coverage[0].id, "q2", difficulty=1)
    _make_question(db, topics_for_coverage[0].id, "q3", difficulty=3)
    _make_question(db, topics_for_coverage[0].id, "q4", difficulty=5)

    stats = get_coverage_stats(db)

    assert stats["by_difficulty"]["1"] == 2
    assert stats["by_difficulty"]["3"] == 1
    assert stats["by_difficulty"]["5"] == 1


def test_coverage_by_subject(db: Session, topics_for_coverage):
    """Per-subject coverage is computed correctly."""
    # mathematics: topic 0 has questions, topic 1 does not
    _make_question(db, topics_for_coverage[0].id, "q1")
    # science: topic 2 has questions, topic 3 does not
    _make_question(db, topics_for_coverage[2].id, "q2")

    stats = get_coverage_stats(db)

    by_subject = {s["subject"]: s for s in stats["by_subject"]}
    assert by_subject["mathematics"]["total"] == 2
    assert by_subject["mathematics"]["covered"] == 1
    assert by_subject["science"]["total"] == 2
    assert by_subject["science"]["covered"] == 1
    assert by_subject["english"]["total"] == 1
    assert by_subject["english"]["covered"] == 0


def test_check_duplicate_detects_match(db: Session, topics_for_coverage):
    """check_duplicate returns True for matching stem+answer."""
    import json
    _make_question(db, topics_for_coverage[0].id, "What is 1+1?")

    assert check_duplicate(db, "What is 1+1?", {"answer": 42}) is True


def test_check_duplicate_no_match(db: Session, topics_for_coverage):
    """check_duplicate returns False for different stem+answer."""
    _make_question(db, topics_for_coverage[0].id, "What is 1+1?")

    assert check_duplicate(db, "What is 2+2?", {"answer": 42}) is False


def test_check_duplicate_same_stem_different_answer(db: Session, topics_for_coverage):
    """Same stem but different answer is NOT a duplicate."""
    import json
    q = Question(
        topic_id=topics_for_coverage[0].id,
        question_type="calculation",
        stem="What is X?",
        answer_json=json.dumps({"answer": 10}),
        difficulty=1,
        bloom_level="apply",
        source="template",
        review_status="approved",
        age_group="mid",
    )
    db.add(q)
    db.flush()

    assert check_duplicate(db, "What is X?", {"answer": 20}) is False
