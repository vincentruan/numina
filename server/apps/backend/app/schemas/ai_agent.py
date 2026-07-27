import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from apps.backend.app.schemas.base import SnowflakeBase

_AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")


class AgentCreateRequest(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=128)
    description: str | None = None
    icon: str | None = Field(None, max_length=16)
    color: str | None = Field(None, max_length=16)
    soul_md: str = Field(..., min_length=10)
    skills: list[str] | None = None
    model: str | None = None
    subagent_enabled: bool = False
    tool_groups: list[str] | None = None
    is_published: bool = False

    @field_validator("agent_name")
    @classmethod
    def validate_agent_name(cls, v: str) -> str:
        if not _AGENT_NAME_RE.match(v):
            raise ValueError("agent_name 必须以小写字母开头，仅包含小写字母、数字、下划线和连字符")
        return v


class AgentUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    soul_md: str | None = None
    skills: list[str] | None = None
    model: str | None = None
    subagent_enabled: bool | None = None
    tool_groups: list[str] | None = None
    display_order: int | None = None
    is_published: bool | None = None


class AgentResponse(SnowflakeBase):
    id: int
    family_id: int
    agent_name: str
    display_name: str
    description: str | None
    icon: str | None
    color: str | None
    soul_md: str
    skills: list[str] | None
    model: str | None
    subagent_enabled: bool
    tool_groups: list[str] | None
    agent_type: str  # system | custom
    is_enabled: bool
    is_published: bool
    display_order: int
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    can_edit: bool
    can_delete: bool


class AgentListGroupedResponse(BaseModel):
    """智能体分组响应"""
    system: list[AgentResponse] = []
    custom: list[AgentResponse] = []
    total: int = 0
