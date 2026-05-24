from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class SiblingResponse(SnowflakeBase):
    id: int
    display_name: str
    avatar_color: str | None


class GiftRequest(BaseModel):
    to_child_id: int
    amount: int
    emoji_reason: str | None = None

    @field_validator("emoji_reason")
    @classmethod
    def validate_emoji_reason(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 10:
            raise ValueError("emoji_reason 不能超过10个字符")
        if any(c in v for c in ('<', '>', '&', '"', "'")):
            raise ValueError("emoji_reason 包含非法字符")
        return v


class GiftResponse(BaseModel):
    sent_amount: int
    to_display_name: str


class ChildBalanceResponse(BaseModel):
    balance: int


class ChildLedgerEntryResponse(BaseModel):
    amount: int
    created_at: datetime
