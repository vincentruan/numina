"""Loader for the os-taxonomy knowledge graph data.

Reads topics.json, dependencies.json, and clusters.json from the package
data directory and returns NormalizedTopic/NormalizedDependency/NormalizedCluster
instances.
"""

from __future__ import annotations

import json
from pathlib import Path

from packages.os_taxonomy.types import (
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)

_DATA_DIR = Path(__file__).parent.parent


def _compute_age_group(age_range_start: int | None) -> str:
    """Compute age group from age_range_start.

    <=7 -> "low", <=10 -> "mid", else -> "high", None -> "mid".
    """
    if age_range_start is None:
        return "mid"
    if age_range_start <= 7:
        return "low"
    if age_range_start <= 10:
        return "mid"
    return "high"


class OsTaxonomyLoader:
    """Loader for the os-taxonomy knowledge graph source.

    Reads from JSON files in the os_taxonomy package directory and returns
    normalized dataclass instances.
    """

    def load_topics(self) -> list[NormalizedTopic]:
        """Load all topics from topics.json."""
        with open(_DATA_DIR / "topics.json", encoding="utf-8") as f:
            data = json.load(f)

        topics: list[NormalizedTopic] = []
        for raw in data["topics"]:
            age_start = raw.get("ageRangeStart")
            topics.append(
                NormalizedTopic(
                    topic_key=raw["id"],
                    source_taxonomy="os-taxonomy",
                    topic_type=raw["type"],
                    subject=raw["subject"],
                    domain=raw.get("domain"),
                    name=raw.get("name"),
                    name_zh=raw.get("nameZh"),
                    description=raw.get("description", ""),
                    description_zh=raw.get("descriptionZh"),
                    age_range_start=age_start,
                    age_range_end=raw.get("ageRangeEnd"),
                    centrality=raw.get("centrality"),
                    evidence=raw.get("evidence", []),
                    evidence_zh=raw.get("evidenceZh"),
                    assessment_prompt=raw.get("assessmentPrompt"),
                    assessment_prompt_zh=raw.get("assessmentPromptZh"),
                    standards=raw.get("standards", []),
                    curriculum_standards=[],
                    translation_status=None,
                    deprecated=False,
                    age_group=_compute_age_group(age_start),
                )
            )
        return topics

    def load_dependencies(self) -> list[NormalizedDependency]:
        """Load all dependency relationships from dependencies.json."""
        with open(_DATA_DIR / "dependencies.json", encoding="utf-8") as f:
            data = json.load(f)

        return [
            NormalizedDependency(
                topic_key=raw["topicId"],
                prerequisite_key=raw["prerequisiteId"],
                strength=raw["strength"],
                reason=raw.get("reason"),
                review_status=None,
            )
            for raw in data["dependencies"]
        ]

    def load_clusters(self) -> list[NormalizedCluster]:
        """Load all clusters from clusters.json."""
        with open(_DATA_DIR / "clusters.json", encoding="utf-8") as f:
            data = json.load(f)

        return [
            NormalizedCluster(
                subject=raw["subject"],
                domain=raw["domain"],
                age_range_start=raw.get("ageRangeStart"),
                age_group=_compute_age_group(raw.get("ageRangeStart")),
                summary=raw.get("summary", ""),
                summary_zh=raw.get("summaryZh"),
                source_taxonomy="os-taxonomy",
            )
            for raw in data["clusters"]
        ]


# ---------------------------------------------------------------------------
# Register this loader in the global registry
# ---------------------------------------------------------------------------
from packages.os_taxonomy.loaders import _LOADER_REGISTRY  # noqa: E402

_LOADER_REGISTRY["os-taxonomy"] = OsTaxonomyLoader()
