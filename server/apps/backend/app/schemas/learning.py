# server/apps/backend/app/schemas/learning.py
"""Request/response schemas for Learning OS APIs."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

# --- Knowledge Graph (Global) ---


class CurriculumStandard(BaseModel):
    """A resolved curriculum standard reference.

    ``key`` is the raw identifier from the source data, ``name`` the curriculum
    document title and ``code`` the code within that document. ``code`` is
    nullable because rows written before resolution store bare identifier
    strings (see ``TopicResponse.normalize_curriculum_standards``).
    """

    key: str
    name: str
    code: str | None = None


class TopicResponse(SnowflakeBase):
    id: int
    topic_key: str
    topic_type: str
    subject: str
    domain: str | None
    name: str | None
    name_zh: str | None
    description: str
    description_zh: str | None
    age_range_start: int | None
    age_range_end: int | None
    age_group: str
    centrality: float | None
    evidence: list[str] = []
    evidence_zh: list[str] | None
    assessment_prompt: str | None
    assessment_prompt_zh: str | None
    standards: list[str] = []
    ability_dimensions: list[str] | None
    curriculum_standards: list[CurriculumStandard] | None = None
    source_taxonomy: str = "os-taxonomy"
    deprecated: bool

    @field_validator("curriculum_standards", mode="before")
    @classmethod
    def normalize_curriculum_standards(cls, v: object) -> object:
        """Accept the legacy bare-identifier shape as well as resolved entries.

        Rows written before backend resolution store plain identifier strings
        (``["moe-2022-chinese:S1.RW.01"]``). Normalizing here rather than in a
        router mapper is deliberate: ``learning_child.py`` and
        ``learning_family.py`` return raw ORM objects under
        ``response_model=TopicResponse`` and never pass through
        ``_topic_to_response``, so a mapper-level fix would 500 on the child
        home and today cards.
        """
        if not isinstance(v, list):
            return v
        return [
            {"key": item, "name": item, "code": None} if isinstance(item, str) else item
            for item in v
        ]


class TopicEdge(BaseModel):
    """A prerequisite or dependent edge with its review status.

    ``review_status`` is ``"reviewed"`` for human-reviewed edges, ``"machine"``
    for AI-generated edges, or ``None`` for os-taxonomy edges that carry no
    review status.
    """

    topic: TopicResponse
    review_status: str | None = None


class TopicGraphResponse(BaseModel):
    """Local subgraph: prerequisites + dependents of a topic."""

    topic: TopicResponse
    prerequisites: list[TopicEdge]
    dependents: list[TopicEdge]


class ClusterResponse(SnowflakeBase):
    id: int
    subject: str
    domain: str
    age_range_start: int | None
    age_group: str
    summary: str


class SubjectSummary(BaseModel):
    subject: str
    topic_count: int
    mastered_count: int = 0  # filled per-child


# --- Progress (Per-Family) ---


class ProgressResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    mastery_level: str
    mastery_score: float | None
    completed_via: str | None
    attempts: int
    xp_earned: int
    last_practice_at: datetime | None
    first_mastered_at: datetime | None
    stability: float | None
    next_review_at: datetime | None
    ability_dimensions_score: dict | None


# --- Assignment ---


class AssignmentCreate(BaseModel):
    child_id: int
    topic_id: int
    assignment_type: str = "parent_assigned"
    priority: int = 0
    due_date: date | None = None

    @field_validator("assignment_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"parent_assigned", "ai_recommended", "self_selected"}
        if v not in allowed:
            raise ValueError(f"assignment_type must be one of {allowed}")
        return v


class AssignmentResponse(SnowflakeBase):
    id: int
    family_id: int
    child_id: int
    topic_id: int
    path_id: int | None
    created_by: int
    assignment_type: str
    status: str
    priority: int
    due_date: date | None
    created_at: datetime
    completed_at: datetime | None
    topic: TopicResponse | None = None  # expanded when needed


class TodayLearningResponse(SnowflakeBase):
    """Today's learning overview for a child — drives the TodayLearningCard."""

    current_topic: TopicResponse | None = None
    pending_assignment: AssignmentResponse | None = None
    recommended_topic: TopicResponse | None = None
    study_minutes_today: int = 0
    current_zone: str = "growth"
    learning_streak_days: int = 0


class LearningStatsResponse(SnowflakeBase):
    """Child learning stats — XP, level, streak."""

    child_id: int
    cumulative_xp: int
    level: int
    level_name_zh: str
    level_name_en: str
    level_emoji: str
    next_level_threshold: int | None
    learning_streak_days: int
    current_zone: str
    onboarding_completed: bool


class OnboardingCompleteResponse(BaseModel):
    """Response for onboarding completion."""

    onboarding_completed: bool


class AssessStreamRequest(BaseModel):
    """Optional body for multi-turn tutorial messages. Omit for initial assessment."""

    user_message: str | None = Field(default=None, max_length=4000)


# --- Session ---


class SessionCreate(BaseModel):
    topic_id: int
    assignment_id: int | None = None
    session_type: str = "tutorial"


class SessionResponse(SnowflakeBase):
    id: int
    assignment_id: int | None
    child_id: int
    topic_id: int
    thread_id: str | None
    session_type: str
    score: float | None
    duration_seconds: int | None
    started_at: datetime
    ended_at: datetime | None
    difficulty_warning: dict | None = None


# --- Assessment Attempt ---


class AssessmentAttemptResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    session_id: int | None
    assessment_type: str
    score: float | None
    passed: bool
    ai_confidence: float | None
    duration_seconds: int | None
    created_at: datetime


# --- Composite / Dashboard ---


class ChildLearningOverview(SnowflakeBase):
    child_id: int
    child_name: str
    mastered_count: int
    learning_count: int
    available_count: int
    locked_count: int
    review_count: int
    total_study_minutes: int
    cumulative_xp: int = 0
    level: int = 1
    level_name_zh: str = ""
    learning_streak_days: int = 0
    current_zone: str = "growth"


class ChildSessionLogResponse(SnowflakeBase):
    """AI session log for parent review."""

    session_id: int
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    session_type: str
    score: float | None
    duration_seconds: int | None
    started_at: datetime
    ended_at: datetime | None


class ReviewItemResponse(SnowflakeBase):
    """For parent review queue."""

    progress_id: int
    child_id: int
    child_name: str
    topic_id: int
    topic_name: str
    topic_description: str
    evidence: list[str]
    evidence_zh: list[str] | None
    attempts: int
    study_duration_seconds: int
    submitted_at: datetime


class ChildProgressOverview(BaseModel):
    """Aggregated progress overview for a child."""

    mastered_count: int
    learning_count: int
    available_count: int
    locked_count: int
    review_count: int
    assessing_count: int
    parent_review_count: int
    total_study_minutes: int = 0
    today_study_minutes: int = 0


# --- Learning Path ---


class PathCreate(BaseModel):
    child_id: int
    name: str
    name_zh: str | None = None
    description: str = ""
    description_zh: str | None = None
    topic_ids: list[int]
    per_task_score: int = 5
    bonus_score: int = 10
    milestone_scores: list[dict] | None = None
    due_date: date | None = None

    @field_validator("topic_ids")
    @classmethod
    def topic_ids_not_empty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("topic_ids must not be empty")
        return v

    @field_validator("milestone_scores")
    @classmethod
    def validate_milestone_scores(cls, v: list[dict] | None, info) -> list[dict] | None:
        if v is None:
            return v
        topic_ids = info.data.get("topic_ids", [])
        max_threshold = len(topic_ids)
        seen_thresholds: set[int] = set()
        for entry in v:
            if "threshold" not in entry or "bonus" not in entry:
                raise ValueError("Each milestone must have 'threshold' and 'bonus'")
            threshold = entry["threshold"]
            bonus = entry["bonus"]
            if (
                not isinstance(threshold, int)
                or threshold < 1
                or threshold > max_threshold
            ):
                raise ValueError(
                    f"threshold must be integer in [1, {max_threshold}], got {threshold}"
                )
            if not isinstance(bonus, int) or bonus < 1:
                raise ValueError(f"bonus must be positive integer, got {bonus}")
            if threshold in seen_thresholds:
                raise ValueError(f"duplicate threshold: {threshold}")
            seen_thresholds.add(threshold)
        return v


class PathItemResponse(SnowflakeBase):
    id: int
    path_id: int
    topic_id: int
    sort_order: int
    status: str
    topic_name: str | None = None
    topic_name_zh: str | None = None
    completed_at: datetime | None = None


class PathResponse(SnowflakeBase):
    id: int
    family_id: int
    child_id: int
    created_by: int
    name: str
    name_zh: str | None = None
    description: str = ""
    description_zh: str | None = None
    status: str
    per_task_score: int
    bonus_score: int
    milestone_scores: list[dict] = []
    due_date: date | None = None
    created_at: datetime
    completed_at: datetime | None = None
    items: list[PathItemResponse] = []
    completed_count: int = 0
    total_count: int = 0
    next_milestone: dict | None = None
