"""Tests for Learning OS seed data quality validation (OQ-6)."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.validation import (
    validate_age_ranges,
    validate_badge_dimensions,
    validate_no_dependency_cycles,
)
from packages.db.models.learning.topic import LearningDependency, LearningTopic


@pytest.fixture
def math_topics(db: Session):
    topics = [
        LearningTopic(
            topic_key=f"mt_{i}",
            topic_type="CONCEPTUAL",
            subject="mathematics",
            domain="Test",
            name=f"Math {i}",
            description="Test",
            age_range_start=8,
            age_range_end=10,
            age_group="mid",
            evidence_json="[]",
            standards_json="[]",
        )
        for i in range(3)
    ]
    db.add_all(topics)
    db.flush()
    return topics


# --- Badge dimension validity ---


def test_badge_dimensions_all_valid():
    """All recognized ability dimensions pass."""
    valid_dims = {"numerical_reasoning", "spatial_reasoning", "creative_thinking"}
    result = validate_badge_dimensions(valid_dims)
    assert result == []


def test_badge_dimensions_unknown_dimension():
    """An unrecognized dimension fails validation."""
    invalid_dims = {"numerical_reasoning", "astrology"}
    result = validate_badge_dimensions(invalid_dims)
    assert len(result) == 1
    assert "astrology" in result[0]


def test_badge_dimensions_empty_set_ok():
    """No badges defined at all -> nothing to validate -> passes."""
    result = validate_badge_dimensions(set())
    assert result == []


# --- Age range sanity ---


def test_age_range_valid_passes(db, math_topics):
    """Topics with start < end pass validation."""
    invalid = validate_age_ranges(db)
    assert invalid == []


def test_age_range_invalid_start_gte_end(db):
    """Topic with age_range_start >= age_range_end fails."""
    bad = LearningTopic(
        topic_key="mt_bad_age",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Bad Age",
        description="Test",
        age_range_start=12,
        age_range_end=8,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(bad)
    db.flush()

    invalid = validate_age_ranges(db)
    assert len(invalid) == 1
    assert "mt_bad_age" in invalid[0]


def test_age_range_null_skipped(db):
    """Topics with null age_range values are skipped (not flagged)."""
    nullable = LearningTopic(
        topic_key="mt_null_age",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Null Age",
        description="Test",
        age_range_start=8,
        age_range_end=None,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(nullable)
    db.flush()

    invalid = validate_age_ranges(db)
    assert invalid == []


# --- Dependency cycle detection ---


def test_no_cycles_in_acyclic_graph(db, math_topics):
    """Linear chain A -> B -> C has no cycles."""
    db.add(
        LearningDependency(
            topic_id=math_topics[1].id,
            prerequisite_id=math_topics[0].id,
            strength="strong",
        )
    )
    db.add(
        LearningDependency(
            topic_id=math_topics[2].id,
            prerequisite_id=math_topics[1].id,
            strength="strong",
        )
    )
    db.flush()

    assert validate_no_dependency_cycles(db) == []


def test_cycle_detected(db, math_topics):
    """A -> B -> A is a cycle."""
    db.add(
        LearningDependency(
            topic_id=math_topics[1].id,
            prerequisite_id=math_topics[0].id,
            strength="strong",
        )
    )
    db.add(
        LearningDependency(
            topic_id=math_topics[0].id,
            prerequisite_id=math_topics[1].id,
            strength="strong",
        )
    )
    db.flush()

    cycles = validate_no_dependency_cycles(db)
    assert len(cycles) > 0


def test_self_loop_detected(db, math_topics):
    """A -> A is a cycle (self-loop)."""
    db.add(
        LearningDependency(
            topic_id=math_topics[0].id,
            prerequisite_id=math_topics[0].id,
            strength="strong",
        )
    )
    db.flush()

    cycles = validate_no_dependency_cycles(db)
    assert len(cycles) > 0


def test_no_topics_no_cycles(db):
    """Empty topic table has no cycles."""
    assert validate_no_dependency_cycles(db) == []
