from datetime import date, datetime

from pydantic import BaseModel


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
    linked_asset_id: str | None = None
    notes: str | None = None


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
    linked_asset_id: str | None = None
    notes: str | None = None


class PaymentRequest(BaseModel):
    amount: float


class LiabilityResponse(BaseModel):
    id: str
    user_id: str
    family_id: str
    category: str
    name: str
    original_amount: float
    remaining_amount: float
    monthly_payment: float | None = None
    interest_rate: float | None = None
    start_date: date | None = None
    end_date: date | None = None
    institution: str | None = None
    linked_asset_id: str | None = None
    notes: str | None = None
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
