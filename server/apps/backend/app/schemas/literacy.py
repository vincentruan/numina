"""Literacy badge system — Pydantic schemas for scenario + badge endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from apps.backend.app.schemas.base import SnowflakeBase

# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


class ChoiceItem(BaseModel):
    """A single choice option inside a scenario."""

    label: str
    feedback: str = ""


class ScenarioResponse(SnowflakeBase):
    """Response for GET /scenario."""

    id: int
    story: str
    choices: list[dict]
    age_group: str
    completed: bool


class ChoiceRequest(BaseModel):
    """Body for POST /scenario/choose."""

    choice_index: int


class ChoiceFeedbackResponse(BaseModel):
    """Response for POST /scenario/choose."""

    feedback_text: str
    dimension_hint: str
    badges_unlocked: list[str]


# ---------------------------------------------------------------------------
# Badges
# ---------------------------------------------------------------------------


class BadgeInfo(SnowflakeBase):
    """A badge the child currently holds or has held."""

    id: int
    name: str
    level: int
    description: str | None = None
    earned_at: datetime | None = None
    superseded_at: datetime | None = None


class BadgeDefinitionInfo(SnowflakeBase):
    """A badge definition (the 'next' badge the child can unlock)."""

    id: int
    name: str
    level: int
    description: str
    criteria_summary: str


class BadgeDimensionResponse(BaseModel):
    """One dimension of the badge wall."""

    model_config = ConfigDict(from_attributes=True)

    dimension: str
    current_badge: BadgeInfo | None
    history: list[BadgeInfo]
    next_badge: BadgeDefinitionInfo | None


class BadgeWallResponse(BaseModel):
    """Response for GET /badges."""

    dimensions: list[BadgeDimensionResponse]
