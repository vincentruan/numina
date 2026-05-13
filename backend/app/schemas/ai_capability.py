"""AI capability discovery schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.base import SnowflakeBase


# ── Capability discovery schemas (no IDs, plain BaseModel) ────────────────────

class AICapabilityUISchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: str
    color: str
    route: str | None
    input_mode: str
    placeholder: str | None
    example_questions: list[str] = Field(default_factory=list)


class AICapabilityPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_roles: list[str] = Field(default_factory=list)
    require_confirmation: bool
    max_tokens: int
    enable_thinking: bool
    enable_tools: list[str] = Field(default_factory=list)


class AICapabilitySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    category: str
    ui: AICapabilityUISchema
    policy: AICapabilityPolicySchema
    skill_id: str
    harness_config: dict[str, Any] = Field(default_factory=dict)


# ── AI capability response schemas (with Snowflake IDs) ───────────────────────

class AIAlertResponse(SnowflakeBase):
    id: int
    asset_id: int
    asset_name: str
    alert_type: str
    severity: str
    suggestion: str
    remaining_life_days: int | None
    daily_cost: float | None
    created_at: str


class AIDisposalSuggestionResponse(SnowflakeBase):
    id: int
    asset_id: int
    asset_name: str
    category_name: str
    inefficiency_score: float
    suggested_channel: str
    estimated_resale_range: str
    suggestion: str
    daily_cost: float | None
    created_at: str


class AISpendingLeakResponse(SnowflakeBase):
    id: int
    asset_id: int
    asset_name: str
    leak_type: str
    severity: str
    estimated_annual_waste: float
    suggestion: str
    created_at: str
