"""W1 savings request/response schemas (Plan B T2).

Money fields (amount, saved_amount, monthly_saving) are NUMERIC(18,2) Decimal in
the model, serialized as str (2 decimals) per the bigint/numeric-as-string
convention. SnowflakeBase only converts int id/*_id fields; money fields are
typed str here with a field_validator coercing Decimal→str.
"""
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, field_serializer, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class SavingsLogCreate(BaseModel):
    amount: Decimal  # positive deposit / negative withdrawal
    log_date: date | None = None  # default today (set in service)
    note: str | None = None


class SavingsLogResponse(SnowflakeBase):
    id: str
    wish_id: str
    family_id: str
    user_id: str
    amount: str  # Decimal → str (2 decimals)
    log_date: date
    note: str | None
    created_at: str  # isoformat

    @field_validator("amount", mode="before")
    @classmethod
    def _coerce_amount(cls, v):
        return str(Decimal(v).quantize(Decimal("0.01"))) if v is not None else v

    @field_serializer("created_at")
    def _ser_created_at(self, v):
        return v.isoformat() if v else None


class WishSavingsResponse(SnowflakeBase):
    wish_id: str
    saved_amount: str
    monthly_saving: str
    target_date: date | None
    savings_count: int

    @field_validator("saved_amount", "monthly_saving", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return str(Decimal(v).quantize(Decimal("0.01"))) if v is not None else v
