"""Pydantic schemas for chore templates and instances."""

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

_HEX_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


ALLOWED_FREQUENCIES = {"daily", "weekly"}
ALLOWED_ASSIGNMENT_TYPES = {"assigned", "pool"}


class ChoreTemplateCreate(BaseModel):
    name: str
    emoji: str | None = None
    coin_reward: int
    frequency: str
    assignment_type: str
    assignee_ids: list[str] = []  # required when assignment_type='assigned'

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        if len(v) > 100:
            raise ValueError("名称不能超过100个字符")
        return v

    @field_validator("coin_reward")
    @classmethod
    def check_coin_reward(cls, v: int) -> int:
        if v < 1:
            raise ValueError("星星币奖励必须为正整数")
        if v > 1000:
            raise ValueError("星星币奖励不能超过1000")
        return v

    @field_validator("frequency")
    @classmethod
    def check_frequency(cls, v: str) -> str:
        if v not in ALLOWED_FREQUENCIES:
            raise ValueError(f"频率必须为 {ALLOWED_FREQUENCIES}")
        return v

    @field_validator("assignment_type")
    @classmethod
    def check_assignment_type(cls, v: str) -> str:
        if v not in ALLOWED_ASSIGNMENT_TYPES:
            raise ValueError(f"分配方式必须为 {ALLOWED_ASSIGNMENT_TYPES}")
        return v


class ChoreTemplateUpdate(BaseModel):
    name: str | None = None
    emoji: str | None = None
    coin_reward: int | None = None
    assignee_ids: list[str] | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        if len(v) > 100:
            raise ValueError("名称不能超过100个字符")
        return v

    @field_validator("coin_reward")
    @classmethod
    def check_coin_reward(cls, v: int | None) -> int | None:
        if v is not None and v < 1:
            raise ValueError("星星币奖励必须为正整数")
        return v


class AssigneeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str


class ChoreTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    family_id: str
    name: str
    emoji: str | None
    coin_reward: int
    frequency: str
    assignment_type: str
    is_active: bool
    assignees: list[AssigneeResponse] = []


class ChoreInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    template_id: str
    chore_name: str
    chore_emoji: str | None
    coin_reward: int
    date_bucket: str
    status: str
    submitted_at: datetime | None = None
    approved_at: datetime | None = None
    streak_count: int
    streak_bonus: int = 0
    milestone_triggered: str | None = None
    child_user_id: str | None = None
    child_display_name: str | None = None
    child_avatar_color: str | None = None

    @field_validator("child_avatar_color", mode="before")
    @classmethod
    def sanitize_child_avatar_color(cls, v: str | None) -> str | None:
        if v is not None and not _HEX_COLOR_RE.match(v):
            return "#4F46E5"
        return v


class ApproveRequest(BaseModel):
    pass  # no body needed for approval


class RejectRequest(BaseModel):
    return_to_redo: bool = False


class GrantRequest(BaseModel):
    child_user_id: str
    amount: int
    reason: str

    @field_validator("amount")
    @classmethod
    def check_amount(cls, v: int) -> int:
        if v < 1 or v > 100:
            raise ValueError("手动奖励金额必须在 1-100 铜币之间")
        return v

    @field_validator("reason")
    @classmethod
    def check_reason(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("原因不能为空")
        if len(v) > 200:
            raise ValueError("原因不能超过200个字符")
        return v
