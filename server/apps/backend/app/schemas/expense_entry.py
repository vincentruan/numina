"""Pydantic schemas for ExpenseEntry model."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import (
    SnowflakeBase,
    coerce_money_str,
    coerce_to_decimal,
)


class ExpenseEntryCreate(BaseModel):
    amount: Decimal
    currency: str
    expense_date: date
    category_id: int | None = None
    description: str | None = None
    ref_id: int | None = None
    ref_type: str | None = None  # 'trip', 'split_settlement'
    receipt_image_url: str | None = None
    split_type: str | None = None  # 'equal', 'per_person', 'custom'
    exchange_rate: float | None = None  # R3: user-provided rate when auto-rate unavailable
    itinerary_item_id: int | None = None  # back-reference to linked itinerary item

    @field_validator("split_type")
    @classmethod
    def _validate_split_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ("equal", "per_person", "custom"):
            raise ValueError("split_type must be 'equal', 'per_person', or 'custom'")
        return v

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        return coerce_to_decimal(v)

    @field_validator("amount")
    @classmethod
    def _validate_amount_positive(cls, v: Decimal) -> Decimal:
        if v is not None and v <= 0:
            raise ValueError("amount must be positive")
        return v


class ExpenseEntryResponse(SnowflakeBase):
    id: int
    family_id: int
    transfer_id: int
    leg_type: str
    ref_id: int | None = None
    ref_type: str | None = None
    category_id: int | None = None
    amount: str
    currency: str
    amount_cny: str
    exchange_rate: float | None = None
    expense_date: date
    description: str | None = None
    receipt_image_url: str | None = None
    split_type: str | None = None
    user_id: int
    itinerary_item_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("amount", "amount_cny", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return coerce_money_str(v)
