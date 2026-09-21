"""Pydantic schemas for Trip model."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import (
    SnowflakeBase,
    coerce_money_str,
    coerce_to_decimal,
)

# --- valid status transitions ---
_VALID_STATUSES = {"planning", "active", "settled", "archived"}
_VALID_TRANSITIONS: dict[str, str] = {
    "planning": "active",
    "active": "settled",
    "settled": "archived",
}


class TripCreate(BaseModel):
    name: str
    destination: str
    departure_date: date
    return_date: date | None = None
    planned_budget: Decimal | None = None
    currency: str = "CNY"
    timezone: str | None = None
    wish_id: int | None = None

    @field_validator("planned_budget", mode="before")
    @classmethod
    def _coerce_budget(cls, v):
        return coerce_to_decimal(v)


class TripUpdate(BaseModel):
    name: str | None = None
    destination: str | None = None
    departure_date: date | None = None
    return_date: date | None = None
    status: str | None = None
    planned_budget: Decimal | None = None
    currency: str | None = None
    timezone: str | None = None

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_VALID_STATUSES)}"
            )
        return v

    @field_validator("planned_budget", mode="before")
    @classmethod
    def _coerce_budget(cls, v):
        return coerce_to_decimal(v)


class TripResponse(SnowflakeBase):
    id: int
    family_id: int
    user_id: int
    name: str
    destination: str
    departure_date: date
    return_date: date | None = None
    status: str
    planned_budget: str | None = None
    initial_funding: str | None = None
    actual_spend: str
    currency: str
    wish_id: int | None = None
    timezone: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("planned_budget", "initial_funding", "actual_spend", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return coerce_money_str(v)
