from datetime import date, datetime
from pydantic import BaseModel


class WishCreate(BaseModel):
    name: str
    category_id: str | None = None
    expected_price: float | None = None
    target_date: date | None = None
    priority: int = 3
    notes: str | None = None


class WishUpdate(BaseModel):
    name: str | None = None
    category_id: str | None = None
    expected_price: float | None = None
    target_date: date | None = None
    priority: int | None = None
    notes: str | None = None


class WishResponse(BaseModel):
    id: str
    family_id: str
    user_id: str
    name: str
    category_id: str | None = None
    expected_price: float | None = None
    target_date: date | None = None
    priority: int
    notes: str | None = None
    is_fulfilled: bool
    fulfilled_asset_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    model_config = {"from_attributes": True}


class FulfillRequest(BaseModel):
    asset_id: str
