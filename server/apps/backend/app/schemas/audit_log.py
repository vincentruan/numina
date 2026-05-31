"""Pydantic schemas for security audit log responses."""

from datetime import datetime

from apps.backend.app.schemas.base import SnowflakeBase


class AuditLogResponse(SnowflakeBase):
    id: int
    event_type: str
    user_id: int | None
    family_id: int | None
    ip_address: str | None
    user_agent: str | None
    outcome: str
    detail: str | None
    created_at: datetime


class AuditLogListResponse(SnowflakeBase):
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int
