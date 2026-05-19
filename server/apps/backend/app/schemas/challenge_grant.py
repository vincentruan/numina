"""ChallengeGrant schemas for API request/response."""

from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class ChallengeGrantResponse(SnowflakeBase):
    """Full challenge response for parent app. IDs serialize as strings."""

    id: int  # Serialized to str by SnowflakeBase
    family_id: int
    child_user_id: int
    target_type: str
    target_value: int
    chore_template_id: int | None = None
    current_progress: int
    deadline: datetime
    message: str | None = None
    status: str
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ChallengeGrantCreate(BaseModel):
    child_user_id: str
    target_type: str  # 'task_count' | 'streak_length' | 'specific_chore' | 'star_earnings'
    target_value: int
    deadline: datetime
    message: str | None = None
    chore_template_id: str | None = None  # Required when target_type == 'specific_chore'


class ChildChallengeResponse(SnowflakeBase):
    """Minimal challenge response for child app. IDs serialize as strings."""

    id: int  # Serialized to str by SnowflakeBase
    target_type: str
    target_value: int
    current_progress: int
    deadline: datetime
    message: str | None = None
    status: str


class ChallengeListResponse(BaseModel):
    items: list[ChallengeGrantResponse]


class ChildChallengeListResponse(BaseModel):
    items: list[ChildChallengeResponse]