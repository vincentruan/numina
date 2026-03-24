from pydantic import BaseModel


class OverviewResponse(BaseModel):
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
    month_over_month_change: float | None = None
    total_daily_cost: float = 0


class AllocationItem(BaseModel):
    category_id: str
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


class TopAssetItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    current_value: float
    currency: str = "CNY"
    original_value: float = 0.0


class DailyCostItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    daily_cost: float
    days_used: int
    total_cost: float
    currency: str = "CNY"
    original_value: float = 0.0


class LowUsageItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    current_value: float
    usage_frequency: str
    purchase_date: str | None = None
    currency: str = "CNY"
    original_value: float = 0.0


class InvestmentReturnItem(BaseModel):
    id: str
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
