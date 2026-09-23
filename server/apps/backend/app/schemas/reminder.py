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
    expiring_soon: int = 0
    maturity: int = 0
    ai_report_complete: int = 0
    ai_finance_coach_complete: int = 0
    ai_wish_advice_complete: int = 0
    ai_literacy_report_complete: int = 0
    chore_completed: int = 0
    treasure_redeemed: int = 0
    wish_redeemed: int = 0
    learning_assignment_created: int = 0
    learning_submitted_for_review: int = 0
    learning_approved: int = 0
    learning_rejected: int = 0
    learning_streak_3_failures: int = 0
    total: int = 0
