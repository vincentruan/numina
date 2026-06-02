"""AI chat and session endpoint response schemas."""

from datetime import datetime

from apps.backend.app.schemas.base import SnowflakeBase


class ChatResponse(SnowflakeBase):
    question: str
    answer: str
    message_id: int  # Snowflake ID
    session_id: int  # Snowflake ID


class SessionSummaryResponse(SnowflakeBase):
    session_id: int  # Snowflake ID
    created_at: str  # ISO format
    message_count: int
    last_preview: str | None


class SessionDetailResponse(SnowflakeBase):
    session_id: int
    family_id: int
    user_id: int | None
    agent_id: int | None
    title: str | None
    status: str
    last_message_summary: str | None
    last_model: str | None
    has_attachments: bool
    is_pinned: bool
    source: str | None
    created_at: str | None  # ISO format
    updated_at: str | None  # ISO format


class AllSessionsResponse(SnowflakeBase):
    sessions: list[SessionDetailResponse]