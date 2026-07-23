from datetime import date, datetime

from pydantic import BaseModel, field_validator

from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.schemas.liability import _coerce_money_str, _coerce_to_decimal


class AssetLifecycleEventResponse(SnowflakeBase):
    id: int
    event_type: str
    event_date: date
    sell_price: str | None = None
    sell_fee: str | None = None
    sell_channel: str | None = None
    notes: str | None = None
    created_at: datetime

    @field_validator("sell_price", "sell_fee", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class AssetCreate(BaseModel):
    category_id: int
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
    warranty_expiry_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: float | None = 0
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    target_daily_cost: float | None = None
    image_url: str | None = None
    tag_ids: list[int] = []

    @field_validator(
        "purchase_price",
        "current_value",
        "annual_maintenance_cost",
        "target_daily_cost",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)


class AssetUpdate(BaseModel):
    category_id: int | None = None
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
    warranty_expiry_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: float | None = None
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    target_daily_cost: float | None = None
    image_url: str | None = None
    tag_ids: list[int] | None = None

    @field_validator(
        "purchase_price",
        "current_value",
        "annual_maintenance_cost",
        "target_daily_cost",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)


class AssetSellRequest(BaseModel):
    sell_price: float
    sell_fee: float = 0
    sell_channel: str | None = None
    notes: str | None = None

    @field_validator("sell_price", "sell_fee", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)


class AssetSellResponse(SnowflakeBase):
    asset_id: int
    name: str
    net_recovery: str
    total_profit_loss: str
    actual_daily_cost: str
    target_daily_cost: str | None
    days_held: int
    purchase_price: str | None
    sell_price: str

    @field_validator(
        "net_recovery",
        "total_profit_loss",
        "actual_daily_cost",
        "target_daily_cost",
        "purchase_price",
        "sell_price",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class AssetValueUpdate(BaseModel):
    current_value: float

    @field_validator("current_value", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_to_decimal(v)


class ValuationResponse(SnowflakeBase):
    id: int
    asset_id: int
    value: str
    valued_at: datetime
    notes: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


class TagBrief(SnowflakeBase):
    id: int
    name: str
    color: str


class CategoryBrief(SnowflakeBase):
    id: int
    name: str
    icon: str
    color: str


class AssetResponse(SnowflakeBase):
    id: int
    user_id: int
    family_id: int
    category_id: int
    category: CategoryBrief | None = None
    name: str
    asset_type: str
    purchase_price: str | None = None
    current_value: str | None = None
    currency: str
    purchase_date: date | None = None
    status: str
    location: str | None = None
    institution: str | None = None
    interest_rate: float | None = None
    maturity_date: date | None = None
    warranty_expiry_date: date | None = None
    expected_lifespan_days: int | None = None
    annual_maintenance_cost: str | None = None
    usage_frequency: str | None = None
    properties: str | None = None
    notes: str | None = None
    is_archived: bool
    sell_price: str | None = None
    sell_date: date | None = None
    sell_fee: str | None = None
    sell_channel: str | None = None
    retire_date: date | None = None
    target_daily_cost: str | None = None
    image_url: str | None = None
    from_wish_id: int | None = None
    tags: list[TagBrief] = []
    daily_cost: float | None = None
    return_rate: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    lifecycle_events: list[AssetLifecycleEventResponse] = []

    @field_validator(
        "purchase_price",
        "current_value",
        "annual_maintenance_cost",
        "sell_price",
        "sell_fee",
        "target_daily_cost",
        mode="before",
    )
    @classmethod
    def _coerce_money(cls, v):
        return _coerce_money_str(v)


# Batch operation schemas
class BatchAssetRequest(BaseModel):
    asset_ids: list[int]


class BatchUpdateCategoryRequest(BaseModel):
    asset_ids: list[int]
    category_id: int


class BatchUpdateTagsRequest(BaseModel):
    asset_ids: list[int]
    tag_ids: list[int]


class BatchUpdateStatusRequest(BaseModel):
    asset_ids: list[int]
    status: str  # 'active' or 'archived'


class BatchItemError(SnowflakeBase):
    id: int
    error_code: str
    message: str


class BatchOperationResponse(BaseModel):
    success_count: int
    failed_count: int
    partial: bool
    errors: list[BatchItemError]


class BatchExportResponse(BaseModel):
    format: str
    data: list[dict]
    count: int


class PaginatedAssetResponse(BaseModel):
    """分页资产列表响应"""
    items: list[AssetResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ChildAssetResponse(SnowflakeBase):
    id: int
    name: str
    image_url: str | None = None
    purchase_date: date | None = None
    purchase_price: float | None = None
    current_value: float | None = None
    status: str
    from_wish_id: int | None = None
    created_at: datetime
