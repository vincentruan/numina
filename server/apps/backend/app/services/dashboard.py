from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from apps.backend.app.models.activity import Activity
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.rental_contract import RentalContract
from apps.backend.app.models.snapshot import AssetSnapshot
from apps.backend.app.models.user import User
from apps.backend.app.schemas.dashboard import (
    AllocationItem,
    AllocationResponse,
    DailyCostItem,
    DailyCostStat,
    DurationBucket,
    DurationDistributionResponse,
    EducationRewardSummaryResponse,
    ExpiringSoonItem,
    GoalProgressItem,
    GoalProgressResponse,
    GoalProgressSummary,
    InsightsResponse,
    InvestmentReturnItem,
    InvestmentReturnSummary,
    LiabilityAllocationItem,
    LiabilityAllocationResponse,
    LongestHeldStat,
    LowUsageItem,
    NewAssetItem,
    NewAssetsResponse,
    OverviewResponse,
    RetentionItem,
    RetentionRateResponse,
    SmartDiscoveryResponse,
    TopAssetItem,
    TopCategoryStat,
    TrendPoint,
    TrendResponse,
    TypeDistributionItem,
    TypeDistributionResponse,
    UpcomingPaymentItem,
    UpcomingPaymentsResponse,
)
from apps.backend.app.services.asset import (
    compute_annualized_return,
    compute_daily_cost,
)
from apps.backend.app.services.exchange_rate import ExchangeRateService


def _period_start_date(today: date, period: str) -> date:
    if period == "year":
        return today - timedelta(days=365)
    elif period == "quarter":
        return today - timedelta(days=90)
    return today - timedelta(days=30)


def get_overview(db: Session, user: User) -> OverviewResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    # Query assets and convert each to default currency
    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .all()
    )
    total_assets_val = 0.0
    for a in assets:
        if a.current_value is not None:
            asset_currency = a.currency or "CNY"
            # a.current_value is Decimal (Numeric); ExchangeRateService.convert
            # takes float (Decimal/float mixed arithmetic raises TypeError).
            converted = ExchangeRateService.convert(
                float(a.current_value), asset_currency, default_currency, db
            )
            total_assets_val += converted

    # Query liabilities and convert each to default currency
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active)
        .all()
    )
    total_liabilities_val = 0.0
    for liab in liabilities:
        if liab.remaining_amount is not None:
            liability_currency = getattr(liab, "currency", "CNY") or "CNY"
            # liab.remaining_amount is Decimal (Numeric); ExchangeRateService.convert
            # expects float. Coerce here — the aggregate is a stat where float
            # precision is sufficient.
            converted = ExchangeRateService.convert(
                float(liab.remaining_amount), liability_currency, default_currency, db
            )
            total_liabilities_val += converted

    asset_count = len(assets)

    # Calculate total daily cost with currency conversion
    daily_cost_assets = [
        a
        for a in assets
        if a.purchase_date is not None and a.purchase_price is not None
    ]
    total_daily_cost = 0.0
    for a in daily_cost_assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            asset_currency = a.currency or "CNY"
            converted = ExchangeRateService.convert(
                dc, asset_currency, default_currency, db
            )
            total_daily_cost += converted
    total_daily_cost = round(total_daily_cost, 2)

    # Month over month change
    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    last_snapshot = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id.is_(None),
            AssetSnapshot.snapshot_date <= last_month,
        )
        .order_by(AssetSnapshot.snapshot_date.desc())
        .first()
    )
    mom_change = None
    mom_change_amount = None
    current_net = total_assets_val - total_liabilities_val
    if last_snapshot and last_snapshot.net_worth != 0:
        # Snapshot net_worth is stored in CNY, convert to default_currency for comparison
        snapshot_net = ExchangeRateService.convert(
            last_snapshot.net_worth, "CNY", default_currency, db
        )
        mom_change_amount = round(current_net - snapshot_net, 2)
        mom_change = round((current_net - snapshot_net) / abs(snapshot_net) * 100, 2)

    # Rental contracts (U13): income/expense/net/deposit; None when no active contracts
    # so the frontend hides the metric entirely.
    rental_contracts = (
        db.query(RentalContract)
        .filter(RentalContract.family_id == family_id, RentalContract.is_active.is_(True))
        .all()
    )
    rental_net = None
    rental_income = None
    rental_expense = None
    rental_deposit = None
    if rental_contracts:
        rental_income = 0.0
        rental_expense = 0.0
        rental_deposit = 0.0
        for c in rental_contracts:
            converted_rent = ExchangeRateService.convert(
                float(c.monthly_rent), c.currency or "CNY", default_currency, db
            )
            converted_deposit = ExchangeRateService.convert(
                float(c.deposit or 0), c.currency or "CNY", default_currency, db
            )
            if c.role == "landlord":
                rental_income += converted_rent
            else:
                rental_expense += converted_rent
            rental_deposit += converted_deposit
        rental_income = round(rental_income, 2)
        rental_expense = round(rental_expense, 2)
        rental_net = round(rental_income - rental_expense, 2)
        rental_deposit = round(rental_deposit, 2)

    return OverviewResponse(
        currency=default_currency,
        total_assets=round(total_assets_val, 2),
        total_liabilities=round(total_liabilities_val, 2),
        net_worth=round(current_net, 2),
        asset_count=asset_count,
        month_over_month_change=mom_change,
        month_over_month_change_amount=mom_change_amount,
        total_daily_cost=total_daily_cost,
        rental_net_cash_flow=rental_net,
        rental_monthly_income=rental_income,
        rental_monthly_expense=rental_expense,
        rental_total_deposit=rental_deposit,
    )


def get_allocation(db: Session, user: User) -> AllocationResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    # Query all assets with their categories
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .all()
    )

    # Group by category with currency conversion
    category_totals: dict[int, dict] = {}
    for a in assets:
        if a.current_value is None:
            continue
        cat_id = a.category_id
        asset_currency = a.currency or "CNY"
        converted = ExchangeRateService.convert(
            float(a.current_value), asset_currency, default_currency, db
        )

        if cat_id not in category_totals:
            category_totals[cat_id] = {
                "id": a.category.id if a.category else cat_id,
                "name": a.category.name if a.category else "",
                "icon": a.category.icon if a.category else "",
                "color": a.category.color if a.category else "",
                "amount": 0.0,
                "asset_type": a.category.asset_type if a.category else a.asset_type,
            }
        category_totals[cat_id]["amount"] += converted

    total = sum(c["amount"] for c in category_totals.values()) or 1

    def build_item(c: dict) -> AllocationItem:
        return AllocationItem(
            category_id=c["id"],
            category_name=c["name"],
            icon=c["icon"],
            color=c["color"],
            amount=round(c["amount"], 2),
            percentage=round(c["amount"] / total * 100, 2),
        )

    items = [build_item(c) for c in category_totals.values()]
    physical_items = [build_item(c) for c in category_totals.values() if c.get("asset_type") == "physical"]
    financial_items = [build_item(c) for c in category_totals.values() if c.get("asset_type") == "financial"]

    return AllocationResponse(
        items=items,
        physical_items=physical_items,
        financial_items=financial_items,
        total=round(total, 2),
    )


def get_liability_allocation(db: Session, user: User) -> LiabilityAllocationResponse:
    """Return active liabilities grouped by category, converted to default currency."""
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active)
        .all()
    )

    category_colors = {
        "mortgage": "#EF4444",
        "car_loan": "#F97316",
        "credit_card": "#6366F1",
        "personal_loan": "#8B5CF6",
        "other": "#64748B",
    }

    category_totals: dict[str, float] = {}
    for liability in liabilities:
        if liability.remaining_amount is None:
            continue
        liability_currency = getattr(liability, "currency", "CNY") or "CNY"
        converted = ExchangeRateService.convert(
            float(liability.remaining_amount), liability_currency, default_currency, db
        )
        category = liability.category or "other"
        category_totals[category] = category_totals.get(category, 0.0) + converted

    total = sum(category_totals.values()) or 0.0
    denominator = total if total > 0 else 1

    items = [
        LiabilityAllocationItem(
            category_name=category,
            amount=round(amount, 2),
            percentage=round(amount / denominator * 100, 2),
            color=category_colors.get(category, "#64748B"),
        )
        for category, amount in sorted(
            category_totals.items(), key=lambda x: x[1], reverse=True
        )
    ]

    return LiabilityAllocationResponse(items=items, total=round(total, 2))


def get_trend(db: Session, user: User, period: str = "month") -> TrendResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"
    today = date.today()

    start_date = _period_start_date(today, period)

    snapshots = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id.is_(None),
            AssetSnapshot.snapshot_date >= start_date,
        )
        .order_by(AssetSnapshot.snapshot_date)
        .all()
    )

    points = []
    for s in snapshots:
        # Convert from CNY (stored in DB) to user's default_currency
        converted_assets = ExchangeRateService.convert(
            s.total_assets, "CNY", default_currency, db
        )
        converted_liabilities = ExchangeRateService.convert(
            s.total_liabilities, "CNY", default_currency, db
        )
        converted_net = ExchangeRateService.convert(
            s.net_worth, "CNY", default_currency, db
        )
        points.append(
            TrendPoint(
                date=s.snapshot_date.isoformat(),
                total_assets=round(converted_assets, 2),
                total_liabilities=round(converted_liabilities, 2),
                net_worth=round(converted_net, 2),
            )
        )
    return TrendResponse(points=points)


def get_top_assets(db: Session, user: User, limit: int = 10) -> list[TopAssetItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.current_value.isnot(None),
        )
        .order_by(Asset.current_value.desc().nullslast())
        .limit(limit)
        .all()
    )

    items = []
    for a in assets:
        asset_currency = a.currency or "CNY"
        converted = ExchangeRateService.convert(
            float(a.current_value or 0), asset_currency, default_currency, db
        )
        items.append(
            TopAssetItem(
                id=a.id,
                name=a.name,
                category_name=a.category.name if a.category else "",
                icon=a.category.icon if a.category else "",
                current_value=round(converted, 2),
                currency=default_currency,
                original_value=float(a.current_value or 0)
                if a.current_value is not None
                else 0.0,
            )
        )

    # Re-sort by converted value for multi-currency correctness
    items.sort(key=lambda x: x.current_value, reverse=True)
    return items


def get_daily_cost_ranking(
    db: Session, user: User, limit: int = 10
) -> list[DailyCostItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date.isnot(None),
            Asset.purchase_price.isnot(None),
        )
        .all()
    )

    items = []
    for a in assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            if a.purchase_date is None:
                continue
            days = (date.today() - a.purchase_date).days
            years = days / 365.0
            total_cost = (
                float(a.purchase_price or 0)
                + float(a.annual_maintenance_cost or 0) * years
            )

            # Convert to default currency
            asset_currency = a.currency or "CNY"
            dc_converted = ExchangeRateService.convert(
                dc, asset_currency, default_currency, db
            )
            total_cost_converted = ExchangeRateService.convert(
                total_cost, asset_currency, default_currency, db
            )

            items.append(
                DailyCostItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    daily_cost=round(dc_converted, 2),
                    days_used=days,
                    total_cost=round(total_cost_converted, 2),
                    currency=default_currency,
                    original_value=round(total_cost, 2),
                )
            )

    items.sort(key=lambda x: x.daily_cost, reverse=True)
    return items[:limit]


def get_low_usage_assets(db: Session, user: User) -> list[LowUsageItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.usage_frequency.in_(["rarely", "idle"]),
        )
        .all()
    )
    return [
        LowUsageItem(
            id=a.id,
            name=a.name,
            category_name=a.category.name if a.category else "",
            icon=a.category.icon if a.category else "",
            current_value=round(
                ExchangeRateService.convert(
                    float(a.current_value or 0),
                    a.currency or "CNY",
                    default_currency,
                    db,
                ),
                2,
            ),
            usage_frequency=a.usage_frequency or "",
            purchase_date=a.purchase_date.isoformat() if a.purchase_date else None,
            currency=default_currency,
            original_value=float(a.current_value or 0),
        )
        for a in assets
    ]


def get_investment_returns(db: Session, user: User) -> list[InvestmentReturnItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.asset_type == "financial",
            Asset.purchase_price.isnot(None),
            Asset.current_value.isnot(None),
        )
        .all()
    )

    items = []
    for a in assets:
        rr = compute_annualized_return(a)
        if rr is not None:
            asset_currency = a.currency or "CNY"
            purchase_price_converted = ExchangeRateService.convert(
                float(a.purchase_price or 0), asset_currency, default_currency, db
            )
            current_value_converted = ExchangeRateService.convert(
                float(a.current_value or 0), asset_currency, default_currency, db
            )
            profit = current_value_converted - purchase_price_converted

            items.append(
                InvestmentReturnItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    purchase_price=round(purchase_price_converted, 2),
                    current_value=round(current_value_converted, 2),
                    return_rate=rr,
                    profit=round(profit, 2),
                    currency=default_currency,
                    original_purchase_price=float(a.purchase_price)
                    if a.purchase_price is not None
                    else 0.0,
                    original_current_value=float(a.current_value)
                    if a.current_value is not None
                    else 0.0,
                )
            )

    items.sort(key=lambda x: x.return_rate, reverse=True)
    return items


def get_education_reward_summary(
    db: Session, user: User
) -> EducationRewardSummaryResponse:
    """B1 教育奖励支出专项统计（方案 B）。

    聚合当前 family 的 `type='education_reward'` Activity：
    - total / count：全时段 sum(amount) / count
    - month_total：本月 sum(amount)（created_at >= 本月 1 号，KTD-3）

    不做货币换算（KTD-1：amount 写入时已是元值）。无记录返回 0，不报错（KTD-2）。
    """
    family_id = user.family_id
    today = date.today()
    month_start = date(today.year, today.month, 1)

    total_row = (
        db.query(
            func.coalesce(func.sum(Activity.amount), 0).label("total"),
            func.count(Activity.id).label("cnt"),
        )
        .filter(
            Activity.family_id == family_id,
            Activity.type == "education_reward",
        )
        .one()
    )

    month_total = (
        db.query(func.coalesce(func.sum(Activity.amount), 0).label("month_total"))
        .filter(
            Activity.family_id == family_id,
            Activity.type == "education_reward",
            Activity.created_at >= month_start,
        )
        .scalar()
    )

    return EducationRewardSummaryResponse(
        total=float(total_row.total or 0),
        month_total=float(month_total or 0),
        count=int(total_row.cnt or 0),
    )


def get_states_summary(db: Session, user: User) -> dict:
    family_id = user.family_id
    results = (
        db.query(
            Asset.status,
            func.count(Asset.id).label("count"),
            func.coalesce(func.sum(Asset.current_value), 0).label("total_value"),
        )
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .group_by(Asset.status)
        .all()
    )
    states = {}
    total_count = 0
    total_value = 0.0
    for r in results:
        states[r.status] = {"count": r.count, "total_value": r.total_value}
        total_count += int(r._mapping["count"])
        total_value += float(r._mapping["total_value"])
    return {"states": states, "total_count": total_count, "total_value": total_value}


def get_home_assets(db: Session, user: User, limit: int = 5) -> dict:
    """Get assets grouped by status for home page display."""
    from apps.backend.app.schemas.asset import AssetResponse
    from apps.backend.app.services.asset import compute_daily_cost, compute_return_rate

    family_id = user.family_id
    statuses = ["in_use", "idle", "sold", "retired"]

    result = {}
    for status in statuses:
        assets = (
            db.query(Asset)
            .options(joinedload(Asset.category), joinedload(Asset.tags))
            .filter(
                Asset.family_id == family_id,
                Asset.is_archived.is_(False),
                Asset.status == status,
            )
            .order_by(Asset.updated_at.desc())
            .limit(limit)
            .all()
        )
        items = []
        for a in assets:
            resp = AssetResponse.model_validate(a)
            resp.daily_cost = compute_daily_cost(a)
            resp.return_rate = compute_return_rate(a)
            items.append(resp)
        if items:  # Only include non-empty groups
            result[status] = items

    return result


def get_home_assets_category_counts(db: Session, user: User, status: str) -> list[dict]:
    """返回指定状态下各分类的资产数量，用于分类导航（不分页）"""
    from apps.backend.app.models.category import Category

    results = (
        db.query(
            Asset.category_id,
            func.count(Asset.id).label("count"),
        )
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.status == status,
            Asset.category_id.isnot(None),
        )
        .group_by(Asset.category_id)
        .all()
    )

    if not results:
        return []

    category_ids = [r.category_id for r in results]
    categories = db.query(Category).filter(Category.id.in_(category_ids)).all()
    cat_map = {c.id: c for c in categories}

    return [
        {
            "id": str(r.category_id),
            "name": cat_map[r.category_id].name if r.category_id in cat_map else "",
            "icon": cat_map[r.category_id].icon if r.category_id in cat_map else "",
            "color": cat_map[r.category_id].color if r.category_id in cat_map else "",
            "asset_type": cat_map[r.category_id].asset_type
            if r.category_id in cat_map
            else "",
            "count": r.count,
        }
        for r in results
    ]


def get_home_assets_page(
    db: Session,
    user: User,
    status: str,
    page: int = 1,
    page_size: int = 20,
    category_id: str | None = None,
    search: str | None = None,
    sort_by: str | None = None,
    sort_order: str = "desc",
    asset_type: str | None = None,
) -> dict:
    """分页获取指定状态的资产列表（支持搜索/排序/类型筛选）"""
    import math

    from apps.backend.app.schemas.asset import AssetResponse
    from apps.backend.app.services.asset import compute_daily_cost, compute_return_rate

    family_id = user.family_id

    filters = [
        Asset.family_id == family_id,
        Asset.is_archived.is_(False),
        Asset.status == status,
    ]
    if category_id:
        import contextlib
        with contextlib.suppress(ValueError):
            filters.append(Asset.category_id == int(category_id))
    if asset_type in ("physical", "financial"):
        filters.append(Asset.asset_type == asset_type)
    if search:
        filters.append(Asset.name.ilike(f"%{search}%"))

    # Sorting: whitelist columns to avoid arbitrary-column injection; default updated_at desc
    sort_columns = {
        "current_value": Asset.current_value,
        "purchase_date": Asset.purchase_date,
        "name": Asset.name,
        "updated_at": Asset.updated_at,
    }
    sort_col = sort_columns.get(sort_by or "", Asset.updated_at)
    order = sort_col.asc() if sort_order == "asc" else sort_col.desc()

    query = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(*filters)
        .order_by(order)
    )

    total = query.count()
    offset = (page - 1) * page_size
    assets = query.offset(offset).limit(page_size).all()

    items = []
    for a in assets:
        resp = AssetResponse.model_validate(a)
        resp.daily_cost = compute_daily_cost(a)
        resp.return_rate = compute_return_rate(a)
        items.append(resp)

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "has_next": page < total_pages,
        "has_prev": page > 1,
    }


def get_expiring_soon_assets(
    db: Session, user: User, days_threshold: int = 90
) -> list[ExpiringSoonItem]:
    """
    Get assets approaching end of expected lifespan.

    For physical assets (electronics), expiration is normal lifecycle - show with muted color.
    For financial assets (accounts, subscriptions), expiration needs attention - show with alert color.
    """
    default_currency = user.default_currency or "CNY"
    today = date.today()

    # Query assets with expected lifespan
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.status == "in_use",  # Only active assets
            Asset.purchase_date.isnot(None),
            Asset.expected_lifespan_days.isnot(None),
        )
        .all()
    )

    items = []
    for a in assets:
        if not a.purchase_date or not a.expected_lifespan_days:
            continue

        # Calculate remaining days
        expiry_date = a.purchase_date + timedelta(days=a.expected_lifespan_days)
        remaining_days = (expiry_date - today).days

        # Only include assets within threshold (including already expired)
        if remaining_days <= days_threshold:
            asset_currency = a.currency or "CNY"
            current_value_converted = ExchangeRateService.convert(
                float(a.current_value or 0), asset_currency, default_currency, db
            )

            items.append(
                ExpiringSoonItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    asset_type=a.asset_type,
                    purchase_date=a.purchase_date.isoformat(),
                    expected_lifespan_days=a.expected_lifespan_days,
                    remaining_days=remaining_days,
                    current_value=round(current_value_converted, 2),
                    currency=default_currency,
                    original_value=float(a.current_value or 0),
                )
            )

    # Sort by remaining days (most urgent first)
    items.sort(key=lambda x: x.remaining_days or 0)
    return items


def get_recent_alerts(db: Session, user: User, limit: int = 10) -> list[dict]:
    """Get recent alerts for a family."""
    from packages.db.models.reminder import Reminder

    rows = (
        db.query(Reminder)
        .filter(
            Reminder.family_id == user.family_id,
            Reminder.status == "active",
        )
        .order_by(Reminder.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(r.id),
            "title": r.title,
            "body": r.body,
            "severity": r.severity,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


def get_new_assets(db: Session, user: User, period: str = "month") -> NewAssetsResponse:
    default_currency = user.default_currency or "CNY"
    today = date.today()

    start_date = _period_start_date(today, period)

    count = (
        db.query(func.count(Asset.id))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.created_at >= start_date,
        )
        .scalar()
    ) or 0

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
            Asset.created_at >= start_date,
        )
        .order_by(Asset.created_at.desc())
        .limit(5)
        .all()
    )

    return NewAssetsResponse(
        count=count,
        period=period,
        items=[
            NewAssetItem(
                id=a.id,
                name=a.name,
                icon=a.category.icon if a.category else "",
                category_name=a.category.name if a.category else "",
                current_value=round(
                    ExchangeRateService.convert(
                        float(a.current_value or 0),
                        a.currency or "CNY",
                        default_currency,
                        db,
                    ),
                    2,
                ),
                currency=default_currency,
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in assets
        ],
    )


# ═══════════════════════════════════════
# Insights Service Functions (S0-S5)
# ═══════════════════════════════════════


def get_smart_discovery(db: Session, user: User) -> SmartDiscoveryResponse:
    """S0 智能发现 - 5项统计卡片"""
    family_id = user.family_id
    today = date.today()

    # 1. 购入同比上月
    # Correct formula: go to last day of previous month, then set day=1
    last_month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
    last_month_end = today.replace(day=1) - timedelta(days=1)
    prev_month_start = (last_month_start - timedelta(days=1)).replace(day=1)

    assets_this_month = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date >= last_month_start,
            Asset.purchase_date <= last_month_end,
        )
        .all()
    )

    assets_prev_month = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date >= prev_month_start,
            Asset.purchase_date < last_month_start,
        )
        .all()
    )

    count_this = len(assets_this_month)
    count_prev = len(assets_prev_month)
    purchase_yoy = None
    if count_prev > 0:
        purchase_yoy = round((count_this - count_prev) / count_prev * 100, 2)

    # 2. 最高日均成本
    daily_cost_items = get_daily_cost_ranking(db, user)
    highest_daily_cost = None
    if daily_cost_items:
        top = daily_cost_items[0]
        highest_daily_cost = DailyCostStat(
            name=top.name, cost=top.daily_cost, icon=top.icon
        )

    # 3. 最低日均成本
    lowest_daily_cost = None
    if daily_cost_items:
        bottom = daily_cost_items[-1]
        lowest_daily_cost = DailyCostStat(
            name=bottom.name, cost=bottom.daily_cost, icon=bottom.icon
        )

    # 4. 持有最久
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date.isnot(None),
        )
        .all()
    )

    longest_held = None
    if assets:
        # Sort by days held
        assets_with_days = [
            (a, (today - a.purchase_date).days) for a in assets if a.purchase_date
        ]
        assets_with_days.sort(key=lambda x: x[1], reverse=True)
        if assets_with_days:
            longest_asset, days = assets_with_days[0]
            longest_held = LongestHeldStat(
                name=longest_asset.name,
                days=days,
                icon=longest_asset.category.icon if longest_asset.category else "",
            )

    # 5. 占比最高分类
    allocation = get_allocation(db, user)
    top_category = None
    if allocation.items:
        top_cat = allocation.items[0]
        top_category = TopCategoryStat(
            name=top_cat.category_name,
            percentage=top_cat.percentage,
            icon=top_cat.icon,
            color=top_cat.color,
        )

    return SmartDiscoveryResponse(
        purchase_yoy=purchase_yoy,
        highest_daily_cost=highest_daily_cost,
        lowest_daily_cost=lowest_daily_cost,
        longest_held=longest_held,
        top_category=top_category,
    )


def get_goal_progress(db: Session, user: User) -> GoalProgressResponse:
    """S2 目标进度总览"""
    family_id = user.family_id
    today = date.today()

    # Query assets with expected lifespan
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.status == "in_use",
            Asset.purchase_date.isnot(None),
            Asset.expected_lifespan_days.isnot(None),
        )
        .all()
    )

    items: list[GoalProgressItem] = []
    healthy = 0
    near_end = 0
    overdue = 0

    for a in assets:
        if not a.purchase_date or not a.expected_lifespan_days:
            continue

        days_held = (today - a.purchase_date).days
        expected_days = a.expected_lifespan_days
        pct = round(days_held / expected_days * 100, 2)

        # Determine status
        if pct > 100:
            status = "overdue"
            overdue += 1
        elif pct >= 80:
            status = "near-end"
            near_end += 1
        else:
            status = "on-track"
            healthy += 1

        items.append(
            GoalProgressItem(
                id=a.id,
                name=a.name,
                category_color=a.category.color if a.category else "#7B61FF",
                status=status,
                progress_pct=min(pct, 110),
                days_held=days_held,
                expected_days=expected_days,
                expected_years=round(expected_days / 365, 1),
            )
        )

    # Sort by status priority: overdue > near-end > on-track, then by pct
    status_order = {"overdue": 0, "near-end": 1, "on-track": 2}
    items.sort(key=lambda x: (status_order[x.status], -x.progress_pct))

    return GoalProgressResponse(
        summary=GoalProgressSummary(
            healthy=healthy, near_end=near_end, overdue=overdue
        ),
        items=items[:10],  # Return top 10
    )


def get_type_distribution(db: Session, user: User) -> TypeDistributionResponse:
    """S3 资产类型分布"""
    family_id = user.family_id

    allocation = get_allocation(db, user)

    # Also get count per category
    count_results = (
        db.query(
            Asset.category_id,
            func.count(Asset.id).label("count"),
        )
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.category_id.isnot(None),
        )
        .group_by(Asset.category_id)
        .all()
    )

    # Build count map
    count_map: dict[int, int] = {r[0]: r[1] for r in count_results}

    categories: list[TypeDistributionItem] = []
    for item in allocation.items:
        categories.append(
            TypeDistributionItem(
                category_id=item.category_id,
                name=item.category_name,
                color=item.color,
                percentage=item.percentage,
                amount=item.amount,
                count=count_map.get(item.category_id, 0),
            )
        )

    total_count = sum(c.count for c in categories)

    return TypeDistributionResponse(
        total_value=allocation.total,
        total_count=total_count,
        categories=categories,
    )


def get_duration_distribution(db: Session, user: User) -> DurationDistributionResponse:
    """S4 持有时长分布"""
    family_id = user.family_id
    today = date.today()

    assets = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.purchase_date.isnot(None),
        )
        .all()
    )

    if not assets:
        return DurationDistributionResponse(
            avg_days=0,
            max_days=0,
            buckets=[],
        )

    # Calculate days held for each asset
    days_list = [(today - a.purchase_date).days for a in assets if a.purchase_date]

    avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0
    max_days = max(days_list) if days_list else 0

    # Bucket definitions (in days)
    bucket_defs = [
        ("less_than_1_year", 0, 365),
        ("range_1_to_2_years", 365, 730),
        ("range_2_to_4_years", 730, 1460),
        ("range_4_to_6_years", 1460, 2190),
        ("range_6_to_8_years", 2190, 2920),
        ("more_than_8_years", 2920, None),
    ]

    total = len(days_list)
    buckets: list[DurationBucket] = []
    for label_key, min_days, max_days_bucket in bucket_defs:
        if max_days_bucket is None:
            count = sum(1 for d in days_list if d >= min_days)
        else:
            count = sum(1 for d in days_list if min_days <= d < max_days_bucket)
        pct = round(count / total * 100, 1) if total > 0 else 0
        buckets.append(
            DurationBucket(
                label_key=label_key,
                count=count,
                percentage=pct,
            )
        )

    return DurationDistributionResponse(
        avg_days=avg_days,
        max_days=max_days,
        buckets=buckets,
    )


def get_retention_rate(db: Session, user: User) -> RetentionRateResponse:
    """S5 资产保值率（仅实物资产）"""
    default_currency = user.default_currency or "CNY"
    family_id = user.family_id
    today = date.today()

    # Query physical assets with purchase price and current value
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived.is_(False),
            Asset.asset_type == "physical",
            Asset.purchase_price.isnot(None),
            Asset.purchase_date.isnot(None),
        )
        .all()
    )

    items: list[RetentionItem] = []
    total_bought = 0.0
    total_sold = 0.0  # Sum of sold assets' purchase prices

    for a in assets:
        if not a.purchase_price or not a.purchase_date:
            continue

        asset_currency = a.currency or "CNY"
        bought = ExchangeRateService.convert(
            float(a.purchase_price), asset_currency, default_currency, db
        )

        # Get current value (or 0 if sold/retired)
        if a.status in ("sold", "retired"):
            current = 0.0
            # Add to sold total
            total_sold += bought
        else:
            current = ExchangeRateService.convert(
                float(a.current_value or 0), asset_currency, default_currency, db
            )

        total_bought += bought

        days = (today - a.purchase_date).days
        rate = round(current / bought * 100, 2) if bought > 0 else 0
        profit = round(current - bought, 2)

        items.append(
            RetentionItem(
                id=a.id,
                name=a.name,
                icon=a.category.icon if a.category else "",
                service_days=days,
                bought_amount=round(bought, 2),
                current_amount=round(current, 2),
                retention_rate=rate,
                profit_loss=profit,
            )
        )

    # Sort by retention rate (highest first)
    items.sort(key=lambda x: x.retention_rate, reverse=True)

    # Add rank after sorting
    for i, item in enumerate(items):
        item.rank = i + 1

    # Calculate totals
    avg_rate = (
        round(sum(i.retention_rate for i in items) / len(items), 2) if items else 0
    )
    total_profit_loss = round(sum(i.profit_loss for i in items), 2)

    return RetentionRateResponse(
        total_bought=round(total_bought, 2),
        total_sold=round(total_sold, 2),
        avg_rate=avg_rate,
        total_profit_loss=total_profit_loss,
        top_items=items[:5],  # Return top 5
    )


def get_insights(db: Session, user: User) -> InsightsResponse:
    """获取洞悉 Tab 完整数据"""
    investment_items = get_investment_returns(db, user)
    if investment_items:
        avg_annualized = round(
            sum(i.return_rate for i in investment_items) / len(investment_items), 2
        )
        investment_summary = InvestmentReturnSummary(
            annualized_rate=avg_annualized,
            asset_count=len(investment_items),
            description="金融资产年化收益率（按持有天数年化）",
        )
    else:
        investment_summary = InvestmentReturnSummary(
            annualized_rate=None,
            asset_count=0,
            description="暂无有效持有天数的金融资产",
        )

    return InsightsResponse(
        smart_discovery=get_smart_discovery(db, user),
        daily_cost_ranking=get_daily_cost_ranking(db, user, limit=5),
        goal_progress=get_goal_progress(db, user),
        type_distribution=get_type_distribution(db, user),
        duration_distribution=get_duration_distribution(db, user),
        retention_rate=get_retention_rate(db, user),
        investment_returns=investment_summary,
    )


def _next_payment_date(start_day: int, today: date) -> date:
    """Return the next occurrence of start_day on or after today.

    Month-end clamping: if start_day exceeds the number of days in the
    candidate month, the last day of that month is used instead.
    """
    import calendar

    def _clamp(year: int, month: int, day: int) -> date:
        last = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last))

    candidate = _clamp(today.year, today.month, start_day)
    if candidate >= today:
        return candidate

    # Advance to next month
    if today.month == 12:
        return _clamp(today.year + 1, 1, start_day)
    return _clamp(today.year, today.month + 1, start_day)


def get_upcoming_payments(
    db: Session, user: User, days: int = 7
) -> UpcomingPaymentsResponse:
    """Return active liabilities whose next payment date falls within *days* days from today."""
    today = date.today()
    cutoff = today + timedelta(days=days)

    liabilities = (
        db.query(Liability)
        .filter(
            Liability.family_id == user.family_id,
            Liability.is_active,
            Liability.start_date.isnot(None),
        )
        .all()
    )

    items: list[UpcomingPaymentItem] = []
    for liability in liabilities:
        # Exclude liabilities whose end_date is in the past
        if liability.end_date is not None and liability.end_date < today:
            continue

        if liability.start_date is None:
            continue
        next_due = _next_payment_date(liability.start_date.day, today)
        if next_due > cutoff:
            continue

        items.append(
            UpcomingPaymentItem(
                liability_id=liability.id,
                name=liability.name,
                amount=float(liability.monthly_payment)
                if liability.monthly_payment is not None
                else None,
                due_date=next_due.isoformat(),
            )
        )

    total_amount = sum(item.amount for item in items if item.amount is not None)
    return UpcomingPaymentsResponse(items=items, total_amount=total_amount)
