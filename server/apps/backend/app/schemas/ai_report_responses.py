"""AI report WebSocket ticket response schema."""

from apps.backend.app.schemas.base import SnowflakeBase


class WSTicketResponse(SnowflakeBase):
    ticket_id: int  # Snowflake ID