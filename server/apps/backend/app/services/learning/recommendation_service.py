"""Recommendation path service — merges breakpoint, curriculum gap, and review dimensions."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from apps.backend.app.services.learning.zone_service import (
    find_breakpoint_topics,
    find_curriculum_gap_topics,
    find_review_due_topics,
)
from packages.core.logging import get_logger
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency

logger = get_logger(__name__)

PRIORITY_ORDER: dict[str, int] = {
    "知识断点": 0,
    "课标必会": 1,
    "高基础度": 2,
    "需要复习": 3,
}


@dataclass
class RecommendationTopic:
    topic_id: int
    topic_name: str
    reasons: list[str]
    centrality: float
    prerequisites_met: bool
    suggested_position: int


@dataclass
class RecommendationPath:
    name: str
    topics: list[RecommendationTopic]
    total_count: int


def generate_recommendation_path(
    db: Session, child_id: int
) -> RecommendationPath:
    """Merge breakpoint + curriculum + review topics into a ranked path.

    Algorithm:
    1. Call the three dimension functions.
    2. Deduplicate by topic_id, merging reasons lists.
    3. Sort by: primary = highest-priority reason (PRIORITY_ORDER), secondary = centrality desc.
    4. Compute prerequisites_met for each topic.
    5. Assign 1-based suggested_position.
    """
    breakpoints = find_breakpoint_topics(db, child_id)
    gaps = find_curriculum_gap_topics(db, child_id)
    reviews = find_review_due_topics(db, child_id)

    # Merge into a dict keyed by topic_id
    merged: dict[int, dict] = {}

    for bp in breakpoints:
        if bp.topic_id not in merged:
            merged[bp.topic_id] = {
                "topic_id": bp.topic_id,
                "topic_name": bp.topic_name,
                "reasons": [],
                "centrality": bp.centrality,
            }
        for r in bp.reasons:
            if r not in merged[bp.topic_id]["reasons"]:
                merged[bp.topic_id]["reasons"].append(r)

    for gap in gaps:
        if gap.topic_id not in merged:
            merged[gap.topic_id] = {
                "topic_id": gap.topic_id,
                "topic_name": gap.topic_name,
                "reasons": [],
                "centrality": gap.centrality,
            }
        for r in gap.reasons:
            if r not in merged[gap.topic_id]["reasons"]:
                merged[gap.topic_id]["reasons"].append(r)

    for rev in reviews:
        if rev.topic_id not in merged:
            merged[rev.topic_id] = {
                "topic_id": rev.topic_id,
                "topic_name": rev.topic_name,
                "reasons": [],
                "centrality": rev.centrality,
            }
        for r in rev.reasons:
            if r not in merged[rev.topic_id]["reasons"]:
                merged[rev.topic_id]["reasons"].append(r)

    if not merged:
        return RecommendationPath(name="建议学习路径", topics=[], total_count=0)

    # Get child's mastered topic_ids for prerequisites_met computation
    mastered_ids: set[int] = {
        row[0]
        for row in db.query(LearningProgress.topic_id).filter(
            LearningProgress.child_id == child_id,
            LearningProgress.mastery_level == "mastered",
        ).all()
    }

    # Sort: primary by best priority reason, secondary by centrality desc
    def sort_key(item: dict) -> tuple[int, float]:
        best_priority = min(
            (PRIORITY_ORDER.get(r, 99) for r in item["reasons"]),
            default=99,
        )
        return (best_priority, -item["centrality"])

    sorted_items = sorted(merged.values(), key=sort_key)

    # Build final list with prerequisites_met and suggested_position
    topics: list[RecommendationTopic] = []
    for idx, item in enumerate(sorted_items, start=1):
        prereqs_met = _check_prerequisites_met(db, item["topic_id"], mastered_ids)
        topics.append(
            RecommendationTopic(
                topic_id=item["topic_id"],
                topic_name=item["topic_name"],
                reasons=item["reasons"],
                centrality=item["centrality"],
                prerequisites_met=prereqs_met,
                suggested_position=idx,
            )
        )

    return RecommendationPath(
        name="建议学习路径",
        topics=topics,
        total_count=len(topics),
    )


def _check_prerequisites_met(
    db: Session, topic_id: int, mastered_ids: set[int]
) -> bool:
    """Check if all hard prerequisites of a topic are mastered by the child."""
    hard_prereqs = (
        db.query(LearningDependency.prerequisite_id)
        .filter(
            LearningDependency.topic_id == topic_id,
            LearningDependency.strength == "hard",
        )
        .all()
    )
    if not hard_prereqs:
        return True
    return all(prereq_id in mastered_ids for prereq_id, in hard_prereqs)
