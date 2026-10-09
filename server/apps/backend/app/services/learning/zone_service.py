"""Zone-based recommendation service — simplified Phase 1 zone logic."""

from datetime import date

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

# Age group ordering for zone determination
AGE_GROUP_ORDER = {"low": 0, "mid": 1, "high": 2}

# Map age_group to the next lower group (for Comfort Zone)
_COMFORT_ZONE_MAP = {
    "high": "mid",
    "mid": "low",
    "low": "low",  # No lower group; Comfort = Growth for youngest
}


def _compute_age(birthday: date) -> int:
    today = date.today()
    return today.year - birthday.year - (
        (today.month, today.day) < (birthday.month, birthday.day)
    )


def _age_to_group(age: int) -> str:
    if age <= 7:
        return "low"
    elif age <= 10:
        return "mid"
    return "high"


def get_child_age_group(db: Session, child_id: int) -> str | None:
    """Get child's age_group from birthday. Returns None if no birthday set."""
    from packages.db.models.user import User

    child = db.query(User).filter(User.id == child_id).first()
    if not child or not child.birthday:
        return None
    return _age_to_group(_compute_age(child.birthday))


def get_child_zone(db: Session, child_id: int) -> str:
    """Get child's current zone label.

    Phase 1: returns 'growth' (zones are determined per-topic, not per-child).
    """
    return "growth"


def get_growth_zone_age_group(child_age_group: str) -> str:
    """Growth Zone topics match the child's own age_group."""
    return child_age_group


def get_comfort_zone_age_group(child_age_group: str) -> str:
    """Comfort Zone topics are one level lower."""
    return _COMFORT_ZONE_MAP.get(child_age_group, child_age_group)


def get_zone_for_topic(topic_age_group: str, child_age_group: str) -> str:
    """Determine zone label for a topic relative to child's age_group."""
    if topic_age_group == child_age_group:
        return "growth"
    child_order = AGE_GROUP_ORDER.get(child_age_group, 1)
    topic_order = AGE_GROUP_ORDER.get(topic_age_group, 1)
    if topic_order < child_order:
        return "comfort"
    return "challenge"


def get_zone_recommended_topic(
    db: Session,
    child_id: int,
    source_taxonomy: str | None = None,
) -> tuple[LearningTopic | None, str]:
    """Zone-aware topic recommendation.

    Returns (topic, zone_label). Prefers Growth Zone topics sorted by centrality,
    falls back to Comfort Zone if no Growth candidates.
    Excludes already-mastered topics.
    """
    child_age_group = get_child_age_group(db, child_id)
    if not child_age_group:
        # Fallback: use existing recommendation logic
        from apps.backend.app.services.learning.progress_service import (
            find_recommended_topic,
        )
        return (
            find_recommended_topic(db, child_id, source_taxonomy=source_taxonomy),
            "growth",
        )

    growth_age = get_growth_zone_age_group(child_age_group)
    comfort_age = get_comfort_zone_age_group(child_age_group)

    mastered_topic_ids = {
        row[0]
        for row in db.query(LearningProgress.topic_id).filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "mastered",
        ).all()
    }

    # Try Growth Zone first
    growth_topic = _find_zone_topic(
        db, child_id, growth_age, mastered_topic_ids, source_taxonomy
    )
    if growth_topic:
        return growth_topic, "growth"

    # Fallback to Comfort Zone
    comfort_topic = _find_zone_topic(
        db, child_id, comfort_age, mastered_topic_ids, source_taxonomy
    )
    if comfort_topic:
        return comfort_topic, "comfort"

    return None, "growth"


def _find_zone_topic(
    db: Session,
    child_id: int,
    age_group: str,
    mastered_ids: set[int],
    source_taxonomy: str | None = None,
) -> LearningTopic | None:
    """Find the best available topic in a zone (by centrality, not mastered).

    Only returns topics where the child has a progress record (available/learning/locked).
    """
    filters = [
        LearningTopic.age_group == age_group,
        LearningTopic.deprecated == False,  # noqa: E712
        LearningProgress.mastery_level.in_(["available", "learning", "locked"]),
    ]
    if source_taxonomy:
        filters.append(LearningTopic.source_taxonomy == source_taxonomy)
    if mastered_ids:
        filters.append(LearningTopic.id.notin_(mastered_ids))

    # Available topics in this zone, sorted by centrality
    available = (
        db.query(LearningTopic)
        .join(
            LearningProgress,
            (LearningProgress.topic_id == LearningTopic.id)
            & (LearningProgress.child_id == child_id),
        )
        .filter(*filters)
        .order_by(LearningTopic.centrality.desc())
        .first()
    )
    return available
