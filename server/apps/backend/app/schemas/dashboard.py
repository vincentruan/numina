from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class OverviewResponse(BaseModel):
    currency: str = "CNY"
    total_assets: float
    total_liabilities: float
    net_worth: float
    asset_count: int
    month_over_month_change: float | None = None
    month_over_month_change_amount: float | None = None
    total_daily_cost: float = 0
    # Rental contracts (U13): monthly income/expense/net; deposit is gross sum
    # across all contracts regardless of role; null when no active contracts.
    rental_net_cash_flow: float | None = None
    rental_monthly_income: float | None = None
    rental_monthly_expense: float | None = None
    rental_total_deposit: float | None = None


class AllocationItem(SnowflakeBase):
    category_id: int
    category_name: str
    icon: str
    color: str
    amount: float
    percentage: float


class AllocationResponse(BaseModel):
    items: list[AllocationItem]
    physical_items: list[AllocationItem] = []
    financial_items: list[AllocationItem] = []
    total: float


class LiabilityAllocationItem(BaseModel):
    category_name: str
    amount: float
    percentage: float
    color: str


class LiabilityAllocationResponse(BaseModel):
    items: list[LiabilityAllocationItem]
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


class EducationRewardSummaryResponse(SnowflakeBase):
    """B1 教育奖励支出专项统计（方案 B：只聚合展示，不动资产/净资产/收益率）。

    amount 在 B1 教育联动写入时已是元值（family 默认币种），直接求和，无货币换算（KTD-1）。
    """

    total: float  # 累计总额（全时段）
    month_total: float  # 本月总额
    count: int  # 笔数（全时段）


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


class NewAssetItem(SnowflakeBase):
    id: int
    name: str
    icon: str
    category_name: str
    current_value: float
    currency: str = "CNY"
    created_at: str  # ISO format


class NewAssetsResponse(BaseModel):
    count: int
    period: str
    items: list[NewAssetItem]


# ═══════════════════════════════════════
# Insights Schemas (S0-S5 for 洞悉 Tab)
# ═══════════════════════════════════════


class DailyCostStat(BaseModel):
    """最高/最低日均成本统计"""
    name: str
    cost: float
    icon: str


class LongestHeldStat(BaseModel):
    """持有最久统计"""
    name: str
    days: int
    icon: str


class TopCategoryStat(BaseModel):
    """占比最高分类统计"""
    name: str
    percentage: float
    icon: str
    color: str


class SmartDiscoveryResponse(BaseModel):
    """S0 智能发现 - 5项统计卡片"""
    purchase_yoy: float | None = None
    highest_daily_cost: DailyCostStat | None = None
    lowest_daily_cost: DailyCostStat | None = None
    longest_held: LongestHeldStat | None = None
    top_category: TopCategoryStat | None = None


class GoalProgressItem(SnowflakeBase):
    """S2 目标进度项"""
    id: int
    name: str
    category_color: str
    status: str  # 'on-track', 'near-end', 'overdue'
    progress_pct: float
    days_held: int
    expected_days: int
    expected_years: float


class GoalProgressSummary(BaseModel):
    """S2 目标进度汇总"""
    healthy: int
    near_end: int
    overdue: int


class GoalProgressResponse(BaseModel):
    """S2 目标进度总览响应"""
    summary: GoalProgressSummary
    items: list[GoalProgressItem]


class TypeDistributionItem(SnowflakeBase):
    """S3 资产类型分布项"""
    category_id: int
    name: str
    color: str
    percentage: float
    amount: float
    count: int


class TypeDistributionResponse(BaseModel):
    """S3 资产类型分布响应"""
    total_value: float
    total_count: int
    categories: list[TypeDistributionItem]


class DurationBucket(BaseModel):
    """S4 持有时长区间"""
    label_key: str  # i18n key
    count: int
    percentage: float


class DurationDistributionResponse(BaseModel):
    """S4 持有时长分布响应"""
    avg_days: float
    max_days: int
    buckets: list[DurationBucket]


class RetentionItem(SnowflakeBase):
    """S5 资产保值率项"""
    id: int
    name: str
    icon: str
    service_days: int
    bought_amount: float
    current_amount: float
    retention_rate: float
    profit_loss: float
    rank: int = 0


class RetentionRateResponse(BaseModel):
    """S5 资产保值率响应"""
    total_bought: float
    total_sold: float
    avg_rate: float
    total_profit_loss: float
    top_items: list[RetentionItem]


class InvestmentReturnSummary(BaseModel):
    """D8 金融资产年化收益率摘要"""
    annualized_rate: float | None  # None = 持有天数不足或无有效资产
    asset_count: int  # 有有效年化收益率的金融资产数
    description: str  # 简短说明（后端中性文案，前端以 i18n 为准）


class InsightsResponse(BaseModel):
    """洞悉 Tab 完整响应"""
    smart_discovery: SmartDiscoveryResponse
    daily_cost_ranking: list[DailyCostItem]  # reuse existing schema
    goal_progress: GoalProgressResponse
    type_distribution: TypeDistributionResponse
    duration_distribution: DurationDistributionResponse
    retention_rate: RetentionRateResponse
    investment_returns: InvestmentReturnSummary | None = None


class NarrativeResponse(BaseModel):
    """Dashboard narrative card response (仪表盘叙事卡片)."""

    narrative: str | None = None
    first_sentence: str = ""
    thinking: str = ""
    generated_at: str | None = None


# ═══════════════════════════════════════
# Upcoming Payments (Track A)
# ═══════════════════════════════════════


class UpcomingPaymentItem(SnowflakeBase):
    """Single liability payment due within the requested window."""
    liability_id: int
    name: str
    amount: float | None
    due_date: str  # ISO date string, e.g. "2025-06-15"


class UpcomingPaymentsResponse(BaseModel):
    items: list[UpcomingPaymentItem]
    total_amount: float


class UpcomingRentalItem(SnowflakeBase):
    """Single rental contract with an upcoming renewal or rent collection date."""
    contract_id: int
    name: str
    amount: float | None
    due_date: str  # ISO date string
    role: str  # "landlord" | "tenant"
    counterparty: str | None


class UpcomingRentalsResponse(BaseModel):
    items: list[UpcomingRentalItem]
    total_amount: float
