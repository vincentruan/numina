from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class ChildWishCreate(BaseModel):
    name: str
    description: str | None = None
    emoji: str | None = None
    priority: str = "medium"

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("名称不能为空")
        if len(v) > 50:
            raise ValueError("名称不能超过50个字符")
        return v

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 200:
            raise ValueError("描述不能超过200个字符")
        return v

    @field_validator("emoji")
    @classmethod
    def validate_emoji(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 10:
            raise ValueError("emoji 不能超过10个字符")
        # Reject any HTML/script content
        if any(c in v for c in ('<', '>', '&', '"', "'")):
            raise ValueError("emoji 包含非法字符")
        return v

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v: str) -> str:
        if v not in ("high", "medium", "low"):
            raise ValueError("优先级必须是 high、medium 或 low")
        return v


class ChildWishResponse(SnowflakeBase):
    id: int
    family_id: int
    child_user_id: int
    name: str
    description: str | None
    emoji: str | None
    priority: str
    status: str
    has_cost_set: bool
    progress: float | None  # balance / star_coin_cost, computed by backend
    rejection_reason: str | None
    realized_asset_id: int | None
    created_at: datetime
    updated_at: datetime


class ChildWishListResponse(BaseModel):
    pending_review: list[ChildWishResponse] = []
    active: list[ChildWishResponse] = []
    redemption_requested: list[ChildWishResponse] = []
    realized: list[ChildWishResponse] = []
    rejected: list[ChildWishResponse] = []


class ApproveChildWishRequest(BaseModel):
    star_coin_cost: int

    @field_validator("star_coin_cost")
    @classmethod
    def validate_cost(cls, v: int) -> int:
        if v < 1:
            raise ValueError("积分门槛必须 ≥ 1")
        return v


class RejectChildWishRequest(BaseModel):
    rejection_reason: str | None = None


class UpdateChildWishCostRequest(BaseModel):
    star_coin_cost: int

    @field_validator("star_coin_cost")
    @classmethod
    def validate_cost(cls, v: int) -> int:
        if v < 1:
            raise ValueError("积分门槛必须 ≥ 1")
        return v


class RealizeChildWishRequest(BaseModel):
    category_id: int | None = None


class ChildWishCostHistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    old_cost: int | None
    new_cost: int
    changed_by_user_id: int
    created_at: datetime


class ParentWishResponse(SnowflakeBase):
    id: int
    family_id: int
    child_user_id: int
    child_display_name: str
    name: str
    description: str | None
    emoji: str | None
    priority: str
    status: str
    star_coin_cost: int | None
    rejection_reason: str | None
    realized_asset_id: int | None
    created_at: datetime
    updated_at: datetime
    milestone_triggered: str | None = None
    cost_history: list[ChildWishCostHistoryItem] = []


class ChildWishStatsSimItem(BaseModel):
    wish_id: int
    name: str
    priority: str
    star_coin_cost: int
    progress: float
    covered: bool


class ChildWishStatsResponse(BaseModel):
    balance: int
    active_wish_count: int
    realized_wish_count: int
    priority_simulation: list[ChildWishStatsSimItem]
    shortfall_for_high_priority: int
