"""Pydantic schemas for SplitGroup, SplitParticipant, SplitSettlement, and shared-expense magic link."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


def _coerce_money_str(v: Any) -> str | None:
    """Serialize a money value to a 2-decimal str (or None) for the wire."""
    if v is None or isinstance(v, str):
        return v
    return str(Decimal(v).quantize(Decimal("0.01")))


class SplitParticipantCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 200:
            raise ValueError("name must be at most 200 characters")
        if not v:
            raise ValueError("name must not be empty")
        return v


class SplitParticipantResponse(SnowflakeBase):
    id: int
    group_id: int
    name: str
    family_id: int | None = None
    joined_at: datetime | None = None


class SplitGroupResponse(SnowflakeBase):
    id: int
    trip_id: int
    invite_code: str
    created_by_user_id: int
    is_active: bool
    created_at: datetime | None = None
    participants: list[SplitParticipantResponse] = []


class SplitSettlementResponse(SnowflakeBase):
    id: int
    trip_id: int
    from_participant_name: str
    to_participant_name: str
    amount: str
    currency: str
    is_complete: bool
    settled_at: datetime | None = None
    settled_by_user_id: int | None = None
    created_at: datetime | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class GraduationRequest(BaseModel):
    wish_id: int


class SharedExpenseItem(SnowflakeBase):
    id: int
    amount: str
    currency: str
    amount_cny: str
    expense_date: date
    category_name: str | None = None
    payer_name: str  # family display name of who paid

    @field_validator("amount", "amount_cny", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class SharedExpenseResponse(SnowflakeBase):
    """Magic-link payload — no family_id, user_id, receipt_image_url, description, transfer_id, leg_type, exchange_rate."""

    trip_name: str
    destination: str
    departure_date: date
    return_date: date | None = None
    expenses: list[SharedExpenseItem] = []
    participants: list[SplitParticipantResponse] = []
