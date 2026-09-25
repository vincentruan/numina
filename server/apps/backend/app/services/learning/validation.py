"""Seed data quality validation for Learning OS."""

from __future__ import annotations

import logging
from collections import defaultdict

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


def validate_no_dependency_cycles(db: Session) -> list[str]:
    """Detect circular prerequisites in the topic dependency graph (DFS-based, O(V+E)).

    Returns:
        List of error messages (empty = no cycles found).
    """
    from packages.db.models.learning.topic import LearningDependency

    edges = db.query(
        LearningDependency.topic_id, LearningDependency.prerequisite_id
    ).all()

    graph: dict[int, list[int]] = defaultdict(list)
    all_nodes: set[int] = set()
    for topic_id, prereq_id in edges:
        graph[prereq_id].append(topic_id)  # prerequisite -> dependent
        all_nodes.add(topic_id)
        all_nodes.add(prereq_id)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[int, int] = {n: WHITE for n in all_nodes}
    cycles: list[str] = []

    def dfs(node: int) -> None:
        color[node] = GRAY
        for neighbor in graph.get(node, []):
            if color[neighbor] == GRAY:
                cycles.append(f"Cycle detected: {node} -> {neighbor}")
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for node in all_nodes:
        if color[node] == WHITE:
            dfs(node)

    return cycles
