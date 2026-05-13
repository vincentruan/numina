"""AI report WebSocket ticket response schema."""

from app.schemas.base import SnowflakeBase


class WSTicketResponse(SnowflakeBase):
    ticket_id: int  # Snowflake ID