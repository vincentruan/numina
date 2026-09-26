"""Pydantic schemas for ItineraryItem and ItineraryItemType."""

from __future__ import annotations

from datetime import date as _date_type
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import (
    SnowflakeBase,
    coerce_money_str,
    coerce_to_decimal,
)

# Valid core item types
CORE_TYPES = {"accommodation", "dining", "transport", "activity"}
ALL_TYPES = CORE_TYPES | {"custom"}


class ItineraryItemCreate(BaseModel):
    date: _date_type
    end_date: _date_type | None = None
    type: str
    sort_order: int = 0
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    description: str | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    purchase_date: _date_type | None = None
    custom_type_id: int | None = None
    type_metadata: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in ALL_TYPES:
            raise ValueError(f"type must be one of {sorted(ALL_TYPES)}")
        return v

    @field_validator("end_date")
    @classmethod
    def _validate_end_date(cls, v: _date_type | None, info) -> _date_type | None:
        if v is not None:
            start = info.data.get("date")
            if start is not None and v < start:
                raise ValueError("end_date must be >= date")
        return v

    @field_validator("cost_amount", mode="before")
    @classmethod
    def _coerce_cost(cls, v):
        return coerce_to_decimal(v)

    @field_validator("cost_amount")
    @classmethod
    def _validate_cost_positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("cost_amount must be positive")
        return v

    @field_validator("cost_currency")
    @classmethod
    def _validate_cost_currency_not_empty(cls, v: str | None) -> str | None:
        if v is not None and v.strip() == "":
            return None
        return v


class ItineraryItemUpdate(BaseModel):
    date: _date_type | None = None
    end_date: _date_type | None = None
    type: str | None = None
    sort_order: int | None = None
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    description: str | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    purchase_date: _date_type | None = None
    custom_type_id: int | None = None
    type_metadata: dict[str, Any] | None = None

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str | None) -> str | None:
        if v is not None and v not in ALL_TYPES:
            raise ValueError(f"type must be one of {sorted(ALL_TYPES)}")
        return v

    @field_validator("cost_amount", mode="before")
    @classmethod
    def _coerce_cost(cls, v):
        return coerce_to_decimal(v)

    @field_validator("end_date")
    @classmethod
    def _validate_end_date(cls, v: _date_type | None, info) -> _date_type | None:
        if v is not None:
            start = info.data.get("date")
            if start is not None and v < start:
                raise ValueError("end_date must be >= date")
        return v


class ItineraryItemResponse(SnowflakeBase):
    id: int
    trip_id: int
    family_id: int
    date: _date_type
    end_date: _date_type | None = None
    type: str
    sort_order: int
    start_time: time | None = None
    end_time: time | None = None
    location: str | None = None
    description: str | None = None
    cost_amount: str | None = None
    cost_currency: str | None = None
    purchase_date: _date_type | None = None
    custom_type_id: int | None = None
    type_metadata: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_validator("cost_amount", mode="before")
    @classmethod
    def _coerce_cost_str(cls, v):
        return coerce_money_str(v)


class ItineraryItemTypeCreate(BaseModel):
    name: str
    icon: str = "star"
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        if len(v) > 50:
            raise ValueError("name must be 50 characters or less")
        return v


class ItineraryItemTypeUpdate(BaseModel):
    name: str | None = None
    icon: str | None = None
    sort_order: int | None = None

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("name must not be empty")
            if len(v) > 50:
                raise ValueError("name must be 50 characters or less")
        return v


class ItineraryItemTypeResponse(SnowflakeBase):
    id: int
    family_id: int | None = None
    name: str
    icon: str
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
