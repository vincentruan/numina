"""Pydantic schemas for practice system."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from apps.backend.app.schemas.base import SnowflakeBase

# --- Request schemas ---


class SessionCreateRequest(BaseModel):
    topic_id: int
    session_mode: Literal["practice", "review", "challenge"] = "practice"
    count: int = Field(default=5, ge=1, le=20)


class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer: dict
    time_spent_seconds: int | None = Field(default=None, ge=0, le=7200)


# --- Response schemas ---


class QuestionPublicResponse(SnowflakeBase):
    """Public question response — no answer or solution exposed."""

    id: int
    topic_id: int
    question_type: str
    stem: str
    stem_zh: str | None
    options: list[dict] | None
    difficulty: int
    bloom_level: str
    source: str
    source_version: str | None
    review_status: str
    age_group: str
    parameters: dict | None
    times_used: int
    correct_count: int


class QuestionResponse(QuestionPublicResponse):
    """Admin response with answer and solution."""

    answer: dict
    solution: dict | None
    review_notes: str | None
    created_at: datetime
    updated_at: datetime


class PracticeQuestionWithAnswer(SnowflakeBase):
    """Question with answer/solution — only returned for active session context."""

    id: int
    topic_id: int
    question_type: str
    stem: str
    stem_zh: str | None
    options: list[dict] | None
    difficulty: int
    bloom_level: str
    source: str
    source_version: str | None
    review_status: str
    age_group: str
    parameters: dict | None
    times_used: int
    correct_count: int
    answer: dict
    solution: dict | None


class PracticeSessionResponse(SnowflakeBase):
    id: int
    child_id: int
    topic_id: int
    session_mode: str
    question_ids: list[int]
    started_at: datetime
    ended_at: datetime | None
    total_score: float | None
    completed_count: int
    source: str
    learning_progress_id: int | None

    @field_serializer("question_ids")
    def _serialize_question_ids(self, v: list[int]) -> list[str]:
        return [str(x) for x in v]


class PracticeAttemptResponse(SnowflakeBase):
    id: int
    session_id: int
    question_id: int
    child_id: int
    topic_id: int
    is_correct: bool
    time_spent_seconds: int | None
    attempt_number: int
    created_at: datetime


class PracticeResultResponse(SnowflakeBase):
    """Final result when a practice session is completed."""

    session_id: int
    total_score: float
    correct_count: int
    total_count: int
    xp_earned: int
    coins_earned: int
    mastery_changed: bool
    new_mastery_level: str | None


# --- Phase 5: Weak points + history response schemas ---


class WeakTopicResponse(SnowflakeBase):
    """A topic where the child has low accuracy."""

    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    total_attempts: int
    correct_attempts: int
    accuracy: float
    last_practice_at: datetime | None
    mastery_level: str

    model_config = ConfigDict(from_attributes=True)


class SessionListItem(SnowflakeBase):
    """Summary of a practice session for list view."""

    id: int
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    session_mode: str
    total_score: float | None
    completed_count: int
    total_count: int
    started_at: datetime
    ended_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AttemptDetail(SnowflakeBase):
    """Single attempt with question context."""

    id: int
    question_id: int
    question_stem: str
    question_type: str
    user_answer: dict
    is_correct: bool
    time_spent_seconds: int | None
    attempt_number: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SessionDetailResponse(SnowflakeBase):
    """Full session detail with attempts."""

    id: int
    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    session_mode: str
    total_score: float | None
    completed_count: int
    total_count: int
    started_at: datetime
    ended_at: datetime | None
    attempts: list[AttemptDetail]


class RecommendResponse(SnowflakeBase):
    """Recommended topic for practice."""

    topic_id: int
    topic_name: str
    topic_name_zh: str | None
    mastery_level: str
    accuracy: float
    is_prerequisite: bool
    prerequisite_of_topic_id: int | None


class SubjectCoverageItem(BaseModel):
    """Per-subject coverage breakdown."""

    subject: str
    total: int
    covered: int
    rate: float


class CoverageResponse(BaseModel):
    """Knowledge point coverage statistics."""

    total_topics: int
    covered_topics: int
    coverage_rate: float
    by_subject: list[SubjectCoverageItem]
    by_difficulty: dict[str, int]
