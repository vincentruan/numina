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


class RentalContractCreate(BaseModel):
    role: str  # landlord / tenant
    monthly_rent: Decimal
    deposit: Decimal = Decimal("0")
    start_date: date
    end_date: date | None = None
    linked_asset_id: int | None = None
    counterparty: str | None = None
    notes: str | None = None
    currency: str = "CNY"

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str) -> str:
        if v not in ("landlord", "tenant"):
            raise ValueError("role must be 'landlord' or 'tenant'")
        return v

    @field_validator("monthly_rent", "deposit", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)

    @field_validator("monthly_rent")
    @classmethod
    def _validate_monthly_rent_positive(cls, v: Decimal) -> Decimal:
        if v is not None and v <= 0:
            raise ValueError("monthly_rent must be positive")
        return v

    @field_validator("deposit")
    @classmethod
    def _validate_deposit_non_negative(cls, v: Decimal) -> Decimal:
        if v is not None and v < 0:
            raise ValueError("deposit must be non-negative")
        return v


class RentalContractUpdate(BaseModel):
    role: str | None = None
    monthly_rent: Decimal | None = None
    deposit: Decimal | None = None
    start_date: date | None = None
    end_date: date | None = None
    linked_asset_id: int | None = None
    counterparty: str | None = None
    notes: str | None = None
    currency: str | None = None

    @field_validator("role")
    @classmethod
    def _validate_role(cls, v: str | None) -> str | None:
        if v is not None and v not in ("landlord", "tenant"):
            raise ValueError("role must be 'landlord' or 'tenant'")
        return v

    @field_validator("monthly_rent", "deposit", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)

    @field_validator("monthly_rent")
    @classmethod
    def _validate_monthly_rent_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("monthly_rent must be positive")
        return v

    @field_validator("deposit")
    @classmethod
    def _validate_deposit_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < 0:
            raise ValueError("deposit must be non-negative")
        return v


class RentalContractResponse(SnowflakeBase):
    id: int
    user_id: int
    family_id: int
    role: str
    monthly_rent: str
    deposit: str
    start_date: date
    end_date: date | None = None
    linked_asset_id: int | None = None
    counterparty: str | None = None
    notes: str | None = None
    currency: str = "CNY"
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("monthly_rent", "deposit", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class RentalContractSummary(BaseModel):
    monthly_income: str
    monthly_expense: str
    net_cash_flow: str
    total_deposit: str

    @field_validator("monthly_income", "monthly_expense", "net_cash_flow", "total_deposit", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)
