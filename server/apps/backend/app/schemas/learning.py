# server/apps/backend/app/schemas/learning.py
"""Request/response schemas for Learning OS APIs."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

# --- Knowledge Graph (Global) ---

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
    deprecated: bool


class TopicGraphResponse(BaseModel):
    """Local subgraph: prerequisites + dependents of a topic."""
    topic: TopicResponse
    prerequisites: list[TopicResponse]
    dependents: list[TopicResponse]


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
    due_date: date | None

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
