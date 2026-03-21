from datetime import date, datetime

from pydantic import BaseModel


class AssetCreate(BaseModel):
    category_id: str
    name: str
    asset_type: str
    purchase_price: float | None = None
    current_value: float | None = None
    currency: str = "CNY"
    purchase_date: date | None = None
    status: str = "in_use"
    location: str | None = None
    institution: str | None = None
    interest_rate: float | None = None
    maturity_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: float | None = 0
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    target_daily_cost: float | None = None
    image_url: str | None = None
    tag_ids: list[str] = []


class AssetUpdate(BaseModel):
    category_id: str | None = None
    name: str | None = None
    asset_type: str | None = None
    purchase_price: float | None = None
    current_value: float | None = None
    currency: str | None = None
    purchase_date: date | None = None
    status: str | None = None
    location: str | None = None
    institution: str | None = None
    interest_rate: float | None = None
    maturity_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: float | None = None
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    target_daily_cost: float | None = None
    image_url: str | None = None
    tag_ids: list[str] | None = None


class AssetSellRequest(BaseModel):
    sell_price: float
    sell_fee: float = 0
    sell_channel: str | None = None
    notes: str | None = None


class AssetSellResponse(BaseModel):
    asset_id: str
    name: str
    net_recovery: float
    total_profit_loss: float
    actual_daily_cost: float
    target_daily_cost: float | None
    days_held: int
    purchase_price: float | None
    sell_price: float


class AssetValueUpdate(BaseModel):
    current_value: float


class ValuationResponse(BaseModel):
    id: str
    asset_id: str
    value: float
    valued_at: datetime
    notes: str | None = None
    model_config = {"from_attributes": True}


class TagBrief(BaseModel):
    id: str
    name: str
    color: str

    model_config = {"from_attributes": True}


class CategoryBrief(BaseModel):
    id: str
    name: str
    icon: str
    color: str

    model_config = {"from_attributes": True}


class AssetResponse(BaseModel):
    id: str
    user_id: str
    family_id: str
    category_id: str
    category: CategoryBrief | None = None
    name: str
    asset_type: str
    purchase_price: float | None = None
    current_value: float | None = None
    currency: str
    purchase_date: date | None = None
    status: str
    location: str | None = None
    institution: str | None = None
    interest_rate: float | None = None
    maturity_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: float | None = None
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    is_archived: bool
    sell_price: float | None = None
    sell_date: date | None = None
    sell_fee: float | None = None
    sell_channel: str | None = None
    retire_date: date | None = None
    target_daily_cost: float | None = None
    image_url: str | None = None
    tags: list[TagBrief] = []
    daily_cost: float | None = None
    return_rate: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
