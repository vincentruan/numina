"""Pydantic schemas for ExpenseCategory model."""

from datetime import datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase


class ExpenseCategoryCreate(BaseModel):
    name: str
    icon: str = "label"
    sort_order: int = 0

    @field_validator("name")
    @classmethod
    def _validate_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) > 50:
            raise ValueError("name must be at most 50 characters")
        if not v:
            raise ValueError("name must not be empty")
        return v


class ExpenseCategoryResponse(SnowflakeBase):
    id: int
    family_id: int | None = None
    name: str
    icon: str
    sort_order: int
    is_system: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
