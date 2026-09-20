"""Pydantic schemas for ExpenseEntry model."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


def _coerce_to_decimal(v: Any) -> Decimal | None:
    """Accept int/float/str/Decimal and return a Decimal (or None)."""
    if v is None or isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _coerce_money_str(v: Any) -> str | None:
    """Serialize a money value to a 2-decimal str (or None) for the wire."""
    if v is None or isinstance(v, str):
        return v
    return str(Decimal(v).quantize(Decimal("0.01")))


class ExpenseEntryCreate(BaseModel):
    amount: Decimal
    currency: str
    expense_date: date
    category_id: int | None = None
    description: str | None = None
    ref_id: int | None = None
    ref_type: str | None = None  # 'trip', 'split_settlement'
    receipt_image_url: str | None = None

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        return _coerce_to_decimal(v)

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
    user_id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("amount", "amount_cny", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)
