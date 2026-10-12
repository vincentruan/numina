"""Pydantic schemas for practice system."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from apps.backend.app.schemas.base import SnowflakeBase


# --- Request schemas ---


class SessionCreateRequest(BaseModel):
    topic_id: int
    session_mode: str = "practice"
    count: int = Field(default=5, ge=1, le=20)


class SubmitAnswerRequest(BaseModel):
    question_id: int
    user_answer: dict
    time_spent_seconds: int | None = None


# --- Response schemas ---


class QuestionResponse(SnowflakeBase):
    id: int
    topic_id: int
    question_type: str
    stem: str
    stem_zh: str | None
    options: list[dict] | None
    answer: dict
    solution: dict | None
    difficulty: int
    bloom_level: str
    source: str
    source_version: str | None
    review_status: str
    review_notes: str | None
    age_group: str
    parameters: dict | None
    times_used: int
    correct_count: int
    created_at: datetime
    updated_at: datetime


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


class PracticeAttemptResponse(SnowflakeBase):
    model_config = ConfigDict(from_attributes=True)

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
