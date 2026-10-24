"""Zone-based recommendation service — simplified Phase 1 zone logic."""

from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic

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
        LearningTopic.deprecated.is_(False),
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


# ---------------------------------------------------------------------------
# Recommendation dataclasses
# ---------------------------------------------------------------------------

@dataclass
class BreakpointTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float
    blocking_topic_id: int  # the mastered topic whose hard dep points here


@dataclass
class CurriculumGapTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float


@dataclass
class ReviewDueTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float
    next_review_at: datetime


# ---------------------------------------------------------------------------
# Recommendation query functions
# ---------------------------------------------------------------------------

def find_breakpoint_topics(
    db: Session, child_id: int
) -> list[BreakpointTopic]:
    """Find topics that are hard prerequisites of mastered topics but not yet mastered.

    Algorithm:
    1. Get child's mastered topic_ids.
    2. Find hard dependency edges where prerequisite_id is in mastered set.
    3. Collect the dependent topic_ids (these are the "next" topics).
    4. Exclude any that the child has already mastered.
    5. Return as BreakpointTopic sorted by centrality desc.
    """
    # Step 1: mastered topic_ids for this child
    mastered_ids: set[int] = {
        row[0]
        for row in db.query(LearningProgress.topic_id).filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "mastered",
        ).all()
    }
    if not mastered_ids:
        return []

    # Step 2: hard dependency edges where prerequisite is mastered
    edges = (
        db.query(LearningDependency)
        .filter(
            LearningDependency.prerequisite_id.in_(mastered_ids),
            LearningDependency.strength == "hard",
        )
        .all()
    )

    if not edges:
        return []

    # Step 3: dependent topic_ids (topic_id is the topic that HAS the prereq)
    dependent_ids = {e.topic_id for e in edges}

    # Step 4: exclude already-mastered
    child_mastered_dependent: set[int] = {
        row[0]
        for row in db.query(LearningProgress.topic_id).filter(
            LearningProgress.child_id == child_id,
            LearningProgress.topic_id.in_(dependent_ids),
            LearningProgress.mastery_level == "mastered",
        ).all()
    }
    remaining_ids = dependent_ids - child_mastered_dependent
    if not remaining_ids:
        return []

    # Step 5: fetch topic details and build results
    topics = (
        db.query(LearningTopic)
        .filter(LearningTopic.id.in_(remaining_ids))
        .all()
    )
    topic_map = {t.id: t for t in topics}

    # Build a map of dependent_id -> first mastered blocking topic_id
    blocking_map: dict[int, int] = {}
    for e in edges:
        if e.topic_id in remaining_ids and e.topic_id not in blocking_map:
            blocking_map[e.topic_id] = e.prerequisite_id

    results: list[BreakpointTopic] = []
    for tid in remaining_ids:
        t = topic_map.get(tid)
        if t is None:
            continue
        results.append(
            BreakpointTopic(
                topic_id=tid,
                topic_name=t.name_zh or t.name or "",
                reasons=["知识断点"],
                centrality=t.centrality or 0.0,
                blocking_topic_id=blocking_map.get(tid, 0),
            )
        )

    results.sort(key=lambda x: x.centrality, reverse=True)
    return results


def find_curriculum_gap_topics(
    db: Session, child_id: int
) -> list[CurriculumGapTopic]:
    """Find age-appropriate curriculum topics the child hasn't mastered, sorted by centrality."""
    child_age_group = get_child_age_group(db, child_id)
    if not child_age_group:
        return []

    # Mastered topic_ids for this child
    mastered_ids: set[int] = {
        row[0]
        for row in db.query(LearningProgress.topic_id).filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "mastered",
        ).all()
    }

    # Age-appropriate topics with non-empty curriculum standards, not deprecated
    candidates = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.age_group == child_age_group,
            LearningTopic.deprecated.is_(False),
            LearningTopic.curriculum_standards_json.isnot(None),
            LearningTopic.curriculum_standards_json != "[]",
        )
        .all()
    )

    # Filter out mastered
    unmastered = [t for t in candidates if t.id not in mastered_ids]

    # Sort by centrality desc
    unmastered.sort(key=lambda t: t.centrality or 0.0, reverse=True)

    return [
        CurriculumGapTopic(
            topic_id=t.id,
            topic_name=t.name_zh or t.name or "",
            reasons=["课标必会"],
            centrality=t.centrality or 0.0,
        )
        for t in unmastered
    ]


def find_review_due_topics(
    db: Session, child_id: int
) -> list[ReviewDueTopic]:
    """Find mastered topics whose SM-2 next_review_at <= now."""
    now = datetime.now(UTC)

    rows = (
        db.query(LearningProgress, LearningTopic)
        .join(LearningTopic, LearningProgress.topic_id == LearningTopic.id)
        .filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "mastered",
            LearningProgress.next_review_at.isnot(None),
            LearningProgress.next_review_at <= now,
        )
        .all()
    )

    results: list[ReviewDueTopic] = []
    for progress, topic in rows:
        results.append(
            ReviewDueTopic(
                topic_id=topic.id,
                topic_name=topic.name_zh or topic.name or "",
                reasons=["需要复习"],
                centrality=topic.centrality or 0.0,
                next_review_at=progress.next_review_at,
            )
        )

    results.sort(key=lambda x: x.centrality, reverse=True)
    return results
