"""Normalized data structures for the Learning OS taxonomy.

These dataclasses provide a unified interface for taxonomy data from different
sources (os-taxonomy, os-taxonomy-beijing, etc.), normalizing field names and
handling source-specific variations.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurriculumStandard:
    """A resolved curriculum standard reference.

    ``key`` is the raw identifier as it appears in the source data (e.g.
    ``moe-2022-math:S1.NA.02``). ``name`` is the curriculum document title
    (e.g. ``义务教育数学课程标准（2022年版）``) and ``code`` is the standard
    code within that document (e.g. ``S1.NA.02``). The title plus code is
    the displayable form.

    Frozen so instances are hashable: the seed script unions
    curriculum_standards lists through a set-based dedup helper. Instances
    sharing a ``key`` also share ``name`` and ``code``, so hashing on all
    three fields does not change dedup behaviour.
    """

    key: str
    name: str
    code: str


@dataclass
class NormalizedTopic:
    """A learning topic normalized across taxonomy sources.

    Required fields (topic_key, source_taxonomy, topic_type, subject) must be
    provided. Optional fields support both English and Chinese translations,
    age ranges, centrality scores, evidence, assessment prompts, and standards.
    """

    topic_key: str
    source_taxonomy: str
    topic_type: str
    subject: str
    domain: str | None = None
    name: str | None = None
    name_zh: str | None = None
    description: str = ""
    description_zh: str | None = None
    age_range_start: int | None = None
    age_range_end: int | None = None
    centrality: float | None = None
    evidence: list[str] = field(default_factory=list)
    evidence_zh: list[str] | None = None
    assessment_prompt: str | None = None
    assessment_prompt_zh: str | None = None
    standards: list[str] = field(default_factory=list)
    curriculum_standards: list[CurriculumStandard] = field(default_factory=list)
    translation_status: str | None = None
    deprecated: bool = False
    age_group: str = "mid"


@dataclass
class NormalizedDependency:
    """A prerequisite relationship between two topics.

    review_status is None for os-taxonomy (no review process) and may be
    "reviewed" or other status values for os-taxonomy-beijing.
    """

    topic_key: str
    prerequisite_key: str
    strength: str
    reason: str | None = None
    review_status: str | None = None


@dataclass
class NormalizedCluster:
    """A grouping of related topics within a subject/domain.

    Clusters organize topics by subject, domain, and age range, with optional
    summaries in English and Chinese.
    """

    subject: str
    domain: str
    age_range_start: int | None = None
    age_group: str = "mid"
    summary: str = ""
    summary_zh: str | None = None
    source_taxonomy: str = "os-taxonomy"


def compute_age_group(age_range_start: int | None) -> str:
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
