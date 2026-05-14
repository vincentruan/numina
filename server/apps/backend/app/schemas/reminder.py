# backend/app/schemas/reminder.py
from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class ReminderResponse(SnowflakeBase):
    id: int
    family_id: int
    reminder_type: str
    title: str
    body: str
    severity: str
    asset_id: int | None
    status: str
    dismissed_at: datetime | None
    resolved_at: datetime | None
    created_at: datetime


class ReminderSummary(BaseModel):
    """总览页摘要：各类型 active 数量"""

    large_purchase: int = 0
    allocation_drift: int = 0
    expiring_soon: int = 0
    maturity: int = 0
    total: int = 0
