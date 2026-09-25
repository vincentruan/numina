"""Seed data quality validation for Learning OS."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic

logger = logging.getLogger(__name__)

# Known ability dimensions — must match translation.py ABILITY_DIMENSIONS
_KNOWN_ABILITY_DIMENSIONS = {
    "numerical_reasoning",
    "spatial_reasoning",
    "verbal_reasoning",
    "scientific_inquiry",
    "computational_thinking",
    "social_emotional",
    "creative_thinking",
    "physical_kinesthetic",
    "memory_recall",
    "metacognition",
}


def validate_badge_dimensions(badge_dimensions: set[str]) -> list[str]:
    """Verify all badge dimensions are recognized ability dimensions.

    The badge model (LiteracyBadgeDefinition) uses a `dimension` field
    storing ability dimension names (e.g., "numerical_reasoning"), NOT
    topic subjects. This check ensures badge dimensions are valid.

    Returns:
        List of error messages (empty = all good).
    """
    errors = []
    for dim in sorted(badge_dimensions):
        if dim not in _KNOWN_ABILITY_DIMENSIONS:
            errors.append(
                f"Badge dimension '{dim}' is not a recognized ability dimension"
            )
    return errors


def validate_age_ranges(db: Session) -> list[str]:
    """Verify age_range_start < age_range_end for all topics where both are non-null.

    Skips topics where either age_range_start or age_range_end is null.

    Returns:
        List of error messages (empty = all good).
    """
    invalid = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.age_range_start.isnot(None),
            LearningTopic.age_range_end.isnot(None),
            LearningTopic.age_range_start >= LearningTopic.age_range_end,
        )
        .all()
    )
    return [
        f"Topic '{t.topic_key}' has age_range_start={t.age_range_start} >= age_range_end={t.age_range_end}"
        for t in invalid
    ]
