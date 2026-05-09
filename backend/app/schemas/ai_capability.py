"""AI capability discovery schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
