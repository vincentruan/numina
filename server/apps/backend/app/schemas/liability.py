from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class LiabilityCreate(BaseModel):
    category: str
    name: str
    original_amount: Decimal
    remaining_amount: Decimal
    monthly_payment: Decimal | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: int | None = None
    notes: str | None = None
    currency: str = "CNY"

    @field_validator("original_amount", "remaining_amount", "monthly_payment", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if v is None or isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class LiabilityUpdate(BaseModel):
    category: str | None = None
    name: str | None = None
    original_amount: Decimal | None = None
    remaining_amount: Decimal | None = None
    monthly_payment: Decimal | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: int | None = None
    notes: str | None = None
    currency: str | None = None

    @field_validator("original_amount", "remaining_amount", "monthly_payment", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if v is None or isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class PaymentRequest(BaseModel):
    amount: Decimal

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class LiabilityResponse(SnowflakeBase):
    id: int
    user_id: int
    family_id: int
    category: str
    name: str
    # Money fields serialized as str (2 decimals) per the money-as-str convention.
    original_amount: str
    remaining_amount: str
    monthly_payment: str | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: int | None = None
    notes: str | None = None
    is_active: bool
    currency: str = "CNY"
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("original_amount", "remaining_amount", "monthly_payment", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        if v is None or isinstance(v, str):
            return v
        return str(Decimal(v).quantize(Decimal("0.01")))
