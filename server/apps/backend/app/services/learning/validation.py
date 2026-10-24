"""Seed data quality validation for Learning OS."""

from __future__ import annotations

from sqlalchemy.orm import Session

from apps.backend.app.services.literacy_badge import (
    ALL_DIMENSIONS as LITERACY_DIMENSIONS,
)
from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)


def validate_badge_subjects(badge_subjects: set[str], db: Session) -> list[str]:
    """Verify all badge subjects exist as LearningTopic.subject values.

    The badge model (LiteracyBadgeDefinition) uses a `dimension` field that
    holds either a subject slug (e.g., "mathematics", "science") that must
    match an actual LearningTopic.subject value, or one of the four
    financial-literacy dimensions, which are a separate axis with no
    corresponding topic row.

    Virtual dimensions that don't map to a topic subject are allowed:
    "comprehensive" (cross-subject badges) and the literacy dimensions
    (earning / choosing / waiting / caring).

    Returns:
        List of error messages (empty = all good).
    """
    # Virtual badge dimensions that don't map to a topic subject
    VIRTUAL_SUBJECTS = {"comprehensive", *LITERACY_DIMENSIONS}

    existing_subjects = {
        row[0]
        for row in db.query(LearningTopic.subject).distinct().all()
        if row[0]
    }
    errors = []
    for subj in sorted(badge_subjects - VIRTUAL_SUBJECTS):
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
