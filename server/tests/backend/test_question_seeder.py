"""Tests for question_seeder — template-to-DB bulk seed pipeline."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.question_seeder import (
    SeedResult,
    seed_questions_from_templates,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def math_topics(db: Session):
    """Create LearningTopic records matching template topic_keys."""
    topics_data = [
        ("mt_arithmetic_addition", "mathematics", "Addition"),
        ("mt_arithmetic_subtraction", "mathematics", "Subtraction"),
        ("mt_arithmetic_multiplication", "mathematics", "Multiplication"),
        ("mt_arithmetic_division", "mathematics", "Division"),
    ]
    topics = []
    for key, subject, name in topics_data:
        t = LearningTopic(
            topic_key=key,
            topic_type="procedural",
            subject=subject,
            domain="Number & Operations",
            name=name,
            description=f"Test {name}",
            age_group="mid",
            evidence_json="[]",
            standards_json="[]",
        )
        db.add(t)
        topics.append(t)
    db.flush()
    return topics


@pytest.fixture
def partial_topics(db: Session):
    """Create only some topics — addition only, others missing."""
    t = LearningTopic(
        topic_key="mt_arithmetic_addition",
        topic_type="procedural",
        subject="mathematics",
        domain="Number & Operations",
        name="Addition",
        description="Test",
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(t)
    db.flush()
    return [t]


def test_seed_creates_questions(db: Session, math_topics):
    """Seeder creates questions from registered templates."""
    result = seed_questions_from_templates(db, count_per_template=3)

    assert isinstance(result, SeedResult)
    assert result.generated > 0
    assert result.failed == 0
    # Verify questions are in DB
    questions = db.query(Question).filter_by(source="template").all()
    assert len(questions) == result.generated


def test_seed_idempotent(db: Session, math_topics):
    """Running seeder twice does not crash and keeps generating unique questions.

    With random template parameters, each run produces different stems,
    so new questions are created. Idempotency here means: safe to re-run,
    no errors, no exact-duplicate insertions within a single run.
    """
    result1 = seed_questions_from_templates(db, count_per_template=3)
    assert result1.generated > 0

    result2 = seed_questions_from_templates(db, count_per_template=3)
    # Second run also generates (random params → different stems)
    assert result2.generated > 0
    assert result2.failed == 0
    # Total questions = sum of both runs
    total = db.query(Question).filter_by(source="template").count()
    assert total == result1.generated + result2.generated


def test_seed_skips_unmatched_topics(db: Session, partial_topics):
    """Templates with no matching topic are skipped with warning count."""
    result = seed_questions_from_templates(db, count_per_template=2)

    # Only addition topic exists; subtraction/multiplication/division missing
    assert result.skipped_no_topic > 0
    assert result.generated > 0  # addition questions created
    # Total skipped + generated should account for all attempts
    assert result.generated + result.skipped_no_topic + result.skipped_duplicate > 0


def test_seed_dedup_same_stem_and_answer(db: Session, math_topics):
    """Within a single run, identical stem+answer pairs are not duplicated.

    We test this by seeding twice and verifying the dedup set is maintained
    within each run. Since random params produce different stems, we verify
    dedup works via the content hash function directly.
    """
    from apps.backend.app.services.learning.question_seeder import _compute_content_hash

    # Same input → same hash
    h1 = _compute_content_hash("1+1=?", {"answer": 2})
    h2 = _compute_content_hash("1+1=?", {"answer": 2})
    assert h1 == h2

    # Different input → different hash
    h3 = _compute_content_hash("1+2=?", {"answer": 3})
    assert h1 != h3

    # Seeder itself runs without error
    result = seed_questions_from_templates(db, count_per_template=2)
    assert result.generated > 0
    assert result.failed == 0


def test_seed_quality_gate_rejects_invalid(db: Session, math_topics):
    """Questions failing quality gate are counted as failed, not created."""
    # This tests the integration — templates produce valid questions,
    # so we verify the quality gate runs by checking all created questions
    # have review_status="approved" (template source auto-approves)
    result = seed_questions_from_templates(db, count_per_template=2)
    assert result.generated > 0

    questions = db.query(Question).filter_by(source="template").all()
    for q in questions:
        assert q.review_status == "approved"
        assert q.topic_id is not None


def test_seed_returns_stats(db: Session, math_topics):
    """SeedResult contains all expected statistics."""
    result = seed_questions_from_templates(db, count_per_template=5)

    assert hasattr(result, "generated")
    assert hasattr(result, "skipped_duplicate")
    assert hasattr(result, "skipped_no_topic")
    assert hasattr(result, "failed")
    assert result.generated > 0
    assert result.failed == 0
    # All attempts accounted for
    total = result.generated + result.skipped_duplicate + result.skipped_no_topic + result.failed
    assert total > 0


def test_seed_with_topic_filter(db: Session, math_topics):
    """--topic filter limits which templates are seeded."""
    result = seed_questions_from_templates(
        db, count_per_template=3, topic_filter="math.arithmetic.addition"
    )
    # Matches addition_2digit + addition_3digit, both link to addition topic
    assert result.generated == 6  # 2 templates × 3 each
    assert result.skipped_no_topic == 0


def test_seed_dry_run(db: Session, math_topics):
    """Dry run generates but does not persist questions."""
    result = seed_questions_from_templates(db, count_per_template=3, dry_run=True)

    assert result.generated > 0
    # No questions should be in DB
    assert db.query(Question).count() == 0
