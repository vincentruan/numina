from pydantic import BaseModel

from app.schemas.base import SnowflakeBase


class OverviewResponse(BaseModel):
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
    month_over_month_change: float | None = None
    total_daily_cost: float = 0


class AllocationItem(SnowflakeBase):
    category_id: int
    category_name: str
    icon: str
    color: str
    amount: float
    percentage: float


class AllocationResponse(BaseModel):
    items: list[AllocationItem]
    total: float


class TrendPoint(BaseModel):
    date: str
    total_assets: float
    total_liabilities: float
    net_worth: float


class TrendResponse(BaseModel):
    points: list[TrendPoint]


class TopAssetItem(SnowflakeBase):
    id: int
    name: str
    category_name: str
    icon: str
    current_value: float
    currency: str = "CNY"
    original_value: float = 0.0


class DailyCostItem(SnowflakeBase):
    id: int
    name: str
    category_name: str
    icon: str
    daily_cost: float
    days_used: int
    total_cost: float
    currency: str = "CNY"
    original_value: float = 0.0


class LowUsageItem(SnowflakeBase):
    id: int
    name: str
    category_name: str
    icon: str
    current_value: float
    usage_frequency: str
    purchase_date: str | None = None
    currency: str = "CNY"
    original_value: float = 0.0


class InvestmentReturnItem(SnowflakeBase):
    id: int
    name: str
    category_name: str
    icon: str
    purchase_price: float
    current_value: float
    return_rate: float
    profit: float
    currency: str = "CNY"
    original_purchase_price: float = 0.0
    original_current_value: float = 0.0


class ExpiringSoonItem(SnowflakeBase):
    """Asset approaching end of expected lifespan."""
    id: int
    name: str
    category_name: str
    icon: str
    asset_type: str  # 'physical' or 'financial'
    purchase_date: str | None = None
    expected_lifespan_days: int | None = None
    remaining_days: int | None = None  # negative = already past expected lifespan
    current_value: float
    currency: str = "CNY"
    original_value: float = 0.0
