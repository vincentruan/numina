"""Seed data quality validation for Learning OS."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from packages.db.models.learning.topic import LearningTopic

logger = logging.getLogger(__name__)


def validate_badge_subjects(badge_subjects: set[str], db: Session) -> list[str]:
    """Verify all badge subjects exist as LearningTopic.subject values.

    The badge model (LiteracyBadgeDefinition) uses a `dimension` field
    storing subject slugs (e.g., "mathematics", "science") that must match
    actual LearningTopic.subject values in the seed data.

    Returns:
        List of error messages (empty = all good).
    """
    existing_subjects = {
        row[0]
        for row in db.query(LearningTopic.subject).distinct().all()
        if row[0]
    }
    errors = []
    for subj in sorted(badge_subjects):
        if subj not in existing_subjects:
            errors.append(
                f"Badge subject '{subj}' does not match any LearningTopic.subject"
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
