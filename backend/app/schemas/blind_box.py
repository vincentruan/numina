from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Gift ──────────────────────────────────────────────────────────────────────

class BlindBoxGiftCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str | None = Field(None, max_length=200)
    emoji: str | None = Field(None, max_length=10)
    value_score: int = Field(..., ge=1, le=10)
    source_wish_id: int | None = None


class BlindBoxGiftUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = Field(None, max_length=200)
    emoji: str | None = Field(None, max_length=10)
    value_score: int | None = Field(None, ge=1, le=10)
    is_active: bool | None = None


class BlindBoxGiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    name: str
    description: str | None
    emoji: str | None
    value_score: int
    source_wish_id: int | None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime
    warning: str | None = None  # 重复检查警告


# ── Draw ──────────────────────────────────────────────────────────────────────

class DrawRequest(BaseModel):
    chore_instance_ids: list[int] = Field(..., min_length=1, description="已批准的 ChoreInstance ID 列表")


class BlindBoxDrawResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    child_user_id: int
    coins_spent: int
    gift_id: int
    gift_name: str
    gift_emoji: str | None
    is_surprise: bool
    is_bonus: bool
    status: str
    draw_at: datetime
    fulfilled_at: datetime | None


# ── Config ────────────────────────────────────────────────────────────────────

class BlindBoxConfigUpdate(BaseModel):
    enabled: bool | None = None
    base_draw_prob: float | None = Field(None, ge=0.0, le=1.0)
    special_day_prob: float | None = Field(None, ge=0.0, le=1.0)
    weight_scale: float | None = Field(None, ge=0.1, le=10.0)
    surprise_threshold_coins: int | None = Field(None, ge=0)
    surprise_prob_normal: float | None = Field(None, ge=0.0, le=1.0)
    surprise_prob_parent_bday: float | None = Field(None, ge=0.0, le=1.0)
    surprise_prob_sibling_bday: float | None = Field(None, ge=0.0, le=1.0)


class BlindBoxConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    enabled: bool
    base_draw_prob: float
    special_day_prob: float
    weight_scale: float
    surprise_threshold_coins: int
    surprise_prob_normal: float
    surprise_prob_parent_bday: float
    surprise_prob_sibling_bday: float


# ── BonusDraw ─────────────────────────────────────────────────────────────────

class BonusDrawResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int
    child_user_id: int
    source_wish_id: int | None
    status: str
    expires_at: datetime
    used_draw_id: int | None
    created_at: datetime
