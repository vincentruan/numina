from datetime import date, datetime

from pydantic import BaseModel


class WishCreate(BaseModel):
    name: str
    description: str | None = None
    expected_price: float | None = None
    priority: str = "medium"
    category_id: str | None = None


class WishUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    expected_price: float | None = None
    priority: str | None = None
    status: str | None = None
    category_id: str | None = None


class WishRealizeRequest(BaseModel):
    purchase_price: float
    purchase_date: date
    category_id: str | None = None


class CategoryInfo(BaseModel):
    id: str
    name: str
    icon: str
    asset_type: str

    model_config = {"from_attributes": True}


class WishResponse(BaseModel):
    id: str
    family_id: str
    user_id: str
    name: str
    description: str | None
    expected_price: float | None
    priority: str
    status: str
    category_id: str | None
    category: CategoryInfo | None
    realized_asset_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
