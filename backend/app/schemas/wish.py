from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.base import SnowflakeBase


class WishCreate(BaseModel):
    name: str
    description: str | None = None
    expected_price: float | None = None
    priority: str = "medium"
    category_id: int | None = None
    currency: str = "CNY"


class WishUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    expected_price: float | None = None
    priority: str | None = None
    status: str | None = None
    category_id: int | None = None
    currency: str | None = None


class WishRealizeRequest(BaseModel):
    purchase_price: float
    purchase_date: date
    category_id: int | None = None


class CategoryInfo(SnowflakeBase):
    id: int
    name: str
    icon: str
    asset_type: str


class WishResponse(SnowflakeBase):
    id: int
    family_id: int
    user_id: int
    name: str
    description: str | None
    expected_price: float | None
    priority: str
    status: str
    category_id: int | None
    category: CategoryInfo | None
    currency: str = "CNY"
    realized_asset_id: int | None
    created_at: datetime
    updated_at: datetime
