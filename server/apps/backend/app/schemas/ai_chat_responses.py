"""AI chat endpoint response schemas."""

from apps.backend.app.schemas.base import SnowflakeBase


class ChatResponse(SnowflakeBase):
    question: str
    answer: str
    message_id: int  # Snowflake ID
    session_id: int  # Snowflake ID
