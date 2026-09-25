"""Tests for Learning OS seed data quality validation (OQ-6)."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.validation import (
    validate_age_ranges,
    validate_badge_dimensions,
)
from packages.db.models.learning.topic import LearningTopic


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
