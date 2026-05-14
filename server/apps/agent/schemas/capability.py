"""Capability discovery schemas."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CapabilityUISchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    icon: str = "message-circle"
    color: str = "#6366f1"
    route: str | None = None
    input_mode: str = "free_text"
    placeholder: str | None = None
    example_questions: list[str] = Field(default_factory=list)


class CapabilityPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_roles: list[str] = Field(default_factory=lambda: ["member", "admin"])
    require_confirmation: bool = False
    max_tokens: int = 2000
    enable_thinking: bool = True
    enable_tools: list[str] = Field(default_factory=list)


class CapabilityDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str = ""
    category: str = "general"
    ui: CapabilityUISchema
    policy: CapabilityPolicy
    skill_id: str
    harness_config: dict[str, Any] = Field(default_factory=dict)
