from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.base import SnowflakeBase


class LiabilityCreate(BaseModel):
    category: str
    name: str
    original_amount: float
    remaining_amount: float
    monthly_payment: float | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: int | None = None
    notes: str | None = None
    currency: str = "CNY"


class LiabilityUpdate(BaseModel):
    category: str | None = None
    name: str | None = None
    original_amount: float | None = None
    remaining_amount: float | None = None
    monthly_payment: float | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: int | None = None
    notes: str | None = None
    currency: str | None = None


class PaymentRequest(BaseModel):
    amount: float


class LiabilityResponse(SnowflakeBase):
    id: int
    user_id: int
    family_id: int
    category: str
    name: str
    original_amount: float
    remaining_amount: float
    monthly_payment: float | None = None
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
