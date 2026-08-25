"""Calendar schemas — per-day event aggregation for child activity view."""

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class CalendarChoreEvent(SnowflakeBase):
    id: int
    chore_name: str
    chore_emoji: str | None
    coin_reward: int
    streak_bonus: int
    status: str  # approved | pending_approval


class CalendarWishEvent(SnowflakeBase):
    id: int
    name: str
    emoji: str | None
    star_coin_cost: int | None


class CalendarMilestoneEvent(SnowflakeBase):
    id: int
    milestone_type: str


class CalendarDayDetail(BaseModel):
    date: str  # YYYY-MM-DD
    chores: list[CalendarChoreEvent]
    wishes: list[CalendarWishEvent]
    milestones: list[CalendarMilestoneEvent]


class CalendarDaySummary(BaseModel):
    """Lightweight summary used in the month grid."""

    date: str  # YYYY-MM-DD
    chore_count: int
    wish_count: int
    milestone_count: int


class CalendarMonthResponse(BaseModel):
    year: int
    month: int
    days: list[CalendarDaySummary]
