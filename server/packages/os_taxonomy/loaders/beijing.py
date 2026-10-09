"""Loader for the os-taxonomy-beijing knowledge graph data.

Reads topics.zh.json, cn-topics.json, dependencies.zh.json,
cn-dependencies.json, cn-bridge-dependencies.json, clusters.zh.json, and
cn-curriculum-standards.json from the Beijing data directory and returns
NormalizedTopic/NormalizedDependency/NormalizedCluster instances with
source_taxonomy="beijing".
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from packages.os_taxonomy.types import (
    CurriculumStandard,
    NormalizedCluster,
    NormalizedDependency,
    NormalizedTopic,
)

# Subject name -> slug mapping for Chinese curriculum subjects
SUBJECT_MAP_ZH: dict[str, str] = {
    "Mathematics": "mathematics",
    "Science": "science",
    "English": "english",
    "History": "history",
    "Chinese": "chinese",
    "Moral & Rule of Law": "ethics_law",
    "Physics": "physics",
    "Chemistry": "chemistry",
    "Biology": "biology",
    "Geography": "geography",
    "Art": "art",
    "Information Technology": "information_technology",
    "General Technology": "general_technology",
    "PE & Health": "pe_health",
    "Labor": "labor",
    "Politics": "politics",
    "Comprehensive Practical Activity": "comprehensive_practical",
    # Cluster-only subjects (not in cn-topics)
    "Personal & Social Development": "personal_social",
}

# English subject map for os-taxonomy subjects (pass-through, lowercased)
SUBJECT_MAP_EN: dict[str, str] = {
    name: name.lower().replace(" & ", "_").replace(" ", "_")
    for name in SUBJECT_MAP_ZH
}


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


def _map_subject(name: str) -> str:
    """Map subject display name to slug via SUBJECT_MAP_ZH, fallback to lowercase."""
    return SUBJECT_MAP_ZH.get(name, name.lower().replace(" ", "_"))


class BeijingLoader:
    """Loader for the os-taxonomy-beijing knowledge graph source.

    Reads from JSON files in the Beijing data directory and returns
    normalized dataclass instances with source_taxonomy="beijing".
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        """Initialize with data directory path.

        Args:
            data_dir: Path to the Beijing data directory. If None, uses
                BEIJING_TAXONOMY_DIR env var or default location relative
                to this file.
        """
        if data_dir is not None:
            self._data_dir = Path(data_dir)
        else:
            env_dir = os.environ.get("BEIJING_TAXONOMY_DIR")
            if env_dir:
                self._data_dir = Path(env_dir)
            else:
                # Default: server/data/os-taxonomy-beijing/data/
                # __file__ = server/packages/os_taxonomy/loaders/beijing.py
                self._data_dir = (
                    Path(__file__).resolve().parent.parent.parent.parent
                    / "data"
                    / "os-taxonomy-beijing"
                    / "data"
                )

    def _read_json(self, filename: str) -> dict:
        """Read and parse a JSON file from the data directory."""
        filepath = self._data_dir / filename
        with open(filepath, encoding="utf-8") as f:
            return json.load(f)

    def _read_upstream_topics(self) -> dict[str, dict]:
        """Load upstream os-taxonomy topics.json for enriching mt_ fields.

        The upstream file carries subject/type/domain/age metadata that
        topics.zh.json omits. Returns {} if the file is not available.
        """
        upstream_path = (
            Path(__file__).resolve().parent.parent / "topics.json"
        )
        if not upstream_path.is_file():
            return {}
        with open(upstream_path, encoding="utf-8") as f:
            return {t["id"]: t for t in json.load(f)["topics"]}

    def _read_curriculum_standards(self) -> dict[str, CurriculumStandard]:
        """Load cn-curriculum-standards.json as a key -> CurriculumStandard map.

        The file nests standards under ``curricula[]``; each curriculum
        carries the document title in ``name`` and its standards in
        ``topics[]`` (each with ``key``, ``code``, ``strand``, ``note``).
        The ``strand`` field is not usable for display — it is normally a
        code echo like "(moe-2022-math / S4.GE.02)" — so only the curriculum
        name and the code are carried through.
        """
        data = self._read_json("cn-curriculum-standards.json")
        lookup: dict[str, CurriculumStandard] = {}
        for curriculum in data["curricula"]:
            name = curriculum["name"]
            for entry in curriculum["topics"]:
                lookup[entry["key"]] = CurriculumStandard(
                    key=entry["key"],
                    name=name,
                    code=entry["code"],
                )
        return lookup

    def _resolve_standards(
        self,
        keys: list[str],
        lookup: dict[str, CurriculumStandard],
    ) -> list[CurriculumStandard]:
        """Resolve raw cnStandards identifiers, dropping unresolvable ones."""
        return [lookup[key] for key in keys if key in lookup]

    def load_topics(self) -> list[NormalizedTopic]:
        """Load all topics from topics.zh.json and cn-topics.json.

        Returns a combined list of topics from both sources, all with
        source_taxonomy="beijing".

        topics.zh.json carries no subject/type/domain fields, so mt_
        topics are enriched by cross-referencing the upstream
        os-taxonomy topics.json (same topic IDs).
        """
        topics: list[NormalizedTopic] = []
        standards_lookup = self._read_curriculum_standards()

        # --- topics.zh.json (mt_ prefix, Chinese-only topics) ---
        zh_data = self._read_json("topics.zh.json")
        upstream = self._read_upstream_topics()
        for raw in zh_data["topics"]:
            up = upstream.get(raw["id"])
            age_start = up.get("ageRangeStart") if up else None
            topics.append(
                NormalizedTopic(
                    topic_key=raw["id"],
                    source_taxonomy="beijing",
                    topic_type=(up.get("type", "concept").lower() if up else "concept"),
                    subject=_map_subject(up["subject"]) if up else "",
                    domain=up.get("domain") if up else None,
                    name=up.get("name") if up else None,
                    name_zh=raw["name"],
                    description=(up.get("description", "") if up else ""),
                    description_zh=raw.get("description"),
                    age_range_start=age_start,
                    age_range_end=up.get("ageRangeEnd") if up else None,
                    centrality=up.get("centrality") if up else None,
                    evidence=raw.get("evidence", []),
                    evidence_zh=None,
                    assessment_prompt=up.get("assessmentPrompt") if up else None,
                    assessment_prompt_zh=raw.get("assessmentPrompt"),
                    standards=up.get("standards", []) if up else [],
                    curriculum_standards=self._resolve_standards(
                        raw.get("cnStandards", []), standards_lookup
                    ),
                    translation_status=raw.get("translationStatus"),
                    deprecated=False,
                    age_group=_compute_age_group(age_start),
                )
            )

        # --- cn-topics.json (mtc_ prefix, Chinese curriculum topics) ---
        cn_data = self._read_json("cn-topics.json")
        for raw in cn_data["topics"]:
            age_start = raw.get("ageRangeStart")
            topics.append(
                NormalizedTopic(
                    topic_key=raw["id"],
                    source_taxonomy="beijing",
                    topic_type=raw.get("type", "concept").lower(),
                    subject=_map_subject(raw.get("subject", "")),
                    domain=raw.get("domain"),
                    name=None,
                    name_zh=raw["name"],
                    description="",
                    description_zh=raw.get("description"),
                    age_range_start=age_start,
                    age_range_end=raw.get("ageRangeEnd"),
                    centrality=raw.get("centrality"),
                    evidence=raw.get("evidence", []),
                    evidence_zh=None,
                    assessment_prompt=None,
                    assessment_prompt_zh=raw.get("assessmentPrompt"),
                    standards=[],
                    curriculum_standards=self._resolve_standards(
                        raw.get("cnStandards", []), standards_lookup
                    ),
                    translation_status=None,
                    deprecated=False,
                    age_group=_compute_age_group(age_start),
                )
            )

        return topics

    def load_dependencies(self) -> list[NormalizedDependency]:
        """Load all dependencies from three source files.

        Merges dependencies.zh.json (mt_→mt_), cn-dependencies.json
        (mtc_→mtc_), and cn-bridge-dependencies.json (mt_→mtc_ bridge).

        Edges with reviewStatus=="rejected" are excluded.
        """
        deps: list[NormalizedDependency] = []

        # --- dependencies.zh.json (mt_→mt_, no reviewStatus) ---
        zh_data = self._read_json("dependencies.zh.json")
        for raw in zh_data["dependencies"]:
            deps.append(
                NormalizedDependency(
                    topic_key=raw["topicId"],
                    prerequisite_key=raw["prerequisiteId"],
                    strength=raw["strength"],
                    reason=raw.get("reason"),
                    review_status=None,
                )
            )

        # --- cn-dependencies.json (mtc_→mtc_, has reviewStatus) ---
        cn_data = self._read_json("cn-dependencies.json")
        for raw in cn_data["dependencies"]:
            if raw.get("reviewStatus") == "rejected":
                continue
            deps.append(
                NormalizedDependency(
                    topic_key=raw["topicId"],
                    prerequisite_key=raw["prerequisiteId"],
                    strength=raw["strength"],
                    reason=raw.get("reason"),
                    review_status=raw.get("reviewStatus"),
                )
            )

        # --- cn-bridge-dependencies.json (mtc_→mt_ bridge, has reviewStatus) ---
        bridge_data = self._read_json("cn-bridge-dependencies.json")
        for raw in bridge_data["dependencies"]:
            if raw.get("reviewStatus") == "rejected":
                continue
            deps.append(
                NormalizedDependency(
                    topic_key=raw["topicId"],
                    prerequisite_key=raw["prerequisiteId"],
                    strength=raw["strength"],
                    reason=raw.get("reason"),
                    review_status=raw.get("reviewStatus"),
                )
            )

        return deps

    def load_clusters(self) -> list[NormalizedCluster]:
        """Load all clusters from clusters.zh.json."""
        data = self._read_json("clusters.zh.json")
        return [
            NormalizedCluster(
                subject=_map_subject(raw["subject"]),
                domain=raw["domain"],
                age_range_start=raw.get("ageRangeStart"),
                age_group=_compute_age_group(raw.get("ageRangeStart")),
                summary="",
                summary_zh=raw.get("summary"),
                source_taxonomy="beijing",
            )
            for raw in data["clusters"]
        ]


# ---------------------------------------------------------------------------
# Register this loader in the global registry
# ---------------------------------------------------------------------------
from packages.os_taxonomy.loaders import _LOADER_REGISTRY  # noqa: E402

_LOADER_REGISTRY["beijing"] = BeijingLoader()
