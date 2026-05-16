from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.snapshot import AssetSnapshot
from apps.backend.app.models.user import User
from apps.backend.app.schemas.dashboard import (
    AllocationItem,
    AllocationResponse,
    DailyCostItem,
    ExpiringSoonItem,
    InvestmentReturnItem,
    LowUsageItem,
    OverviewResponse,
    TopAssetItem,
    TrendPoint,
    TrendResponse,
)
from apps.backend.app.services.asset import compute_daily_cost, compute_return_rate
from apps.backend.app.services.exchange_rate import ExchangeRateService


def get_overview(db: Session, user: User) -> OverviewResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    # Query assets and convert each to default currency
    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )
    total_assets_val = 0.0
    for a in assets:
        if a.current_value is not None:
            asset_currency = a.currency or "CNY"
            converted = ExchangeRateService.convert(a.current_value, asset_currency, default_currency, db)
            total_assets_val += converted

    # Query liabilities and convert each to default currency
    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .all()
    )
    total_liabilities_val = 0.0
    for l in liabilities:
        if l.remaining_amount is not None:
            liability_currency = getattr(l, "currency", "CNY") or "CNY"
            converted = ExchangeRateService.convert(l.remaining_amount, liability_currency, default_currency, db)
            total_liabilities_val += converted

    asset_count = len(assets)

    # Calculate total daily cost with currency conversion
    daily_cost_assets = [
        a for a in assets
        if a.purchase_date is not None and a.purchase_price is not None
    ]
    total_daily_cost = 0.0
    for a in daily_cost_assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            asset_currency = a.currency or "CNY"
            converted = ExchangeRateService.convert(dc, asset_currency, default_currency, db)
            total_daily_cost += converted
    total_daily_cost = round(total_daily_cost, 2)

    # Month over month change
    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    last_snapshot = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
            AssetSnapshot.snapshot_date <= last_month,
        )
        .order_by(AssetSnapshot.snapshot_date.desc())
        .first()
    )
    mom_change = None
    current_net = total_assets_val - total_liabilities_val
    if last_snapshot and last_snapshot.net_worth != 0:
        # Snapshot net_worth is stored in CNY, convert to default_currency for comparison
        snapshot_net = ExchangeRateService.convert(last_snapshot.net_worth, "CNY", default_currency, db)
        mom_change = round((current_net - snapshot_net) / abs(snapshot_net) * 100, 2)

    return OverviewResponse(
        total_assets=round(total_assets_val, 2),
        total_liabilities=round(total_liabilities_val, 2),
        net_worth=round(current_net, 2),
        asset_count=asset_count,
        month_over_month_change=mom_change,
        total_daily_cost=total_daily_cost,
    )


def get_allocation(db: Session, user: User) -> AllocationResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    # Query all assets with their categories
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )

    # Group by category with currency conversion
    category_totals: dict[str, dict] = {}
    for a in assets:
        if a.current_value is None:
            continue
        cat_id = a.category_id
        asset_currency = a.currency or "CNY"
        converted = ExchangeRateService.convert(a.current_value, asset_currency, default_currency, db)

        if cat_id not in category_totals:
            category_totals[cat_id] = {
                "id": a.category.id if a.category else cat_id,
                "name": a.category.name if a.category else "",
                "icon": a.category.icon if a.category else "",
                "color": a.category.color if a.category else "",
                "amount": 0.0,
            }
        category_totals[cat_id]["amount"] += converted

    total = sum(c["amount"] for c in category_totals.values()) or 1
    items = [
        AllocationItem(
            category_id=c["id"],
            category_name=c["name"],
            icon=c["icon"],
            color=c["color"],
            amount=round(c["amount"], 2),
            percentage=round(c["amount"] / total * 100, 2),
        )
        for c in category_totals.values()
    ]
    return AllocationResponse(items=items, total=round(total, 2))


def get_trend(db: Session, user: User, period: str = "month") -> TrendResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"
    today = date.today()

    if period == "year":
        start_date = today - timedelta(days=365)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:
        start_date = today - timedelta(days=30)

    snapshots = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
            AssetSnapshot.snapshot_date >= start_date,
        )
        .order_by(AssetSnapshot.snapshot_date)
        .all()
    )

    points = []
    for s in snapshots:
        # Convert from CNY (stored in DB) to user's default_currency
        converted_assets = ExchangeRateService.convert(s.total_assets, "CNY", default_currency, db)
        converted_liabilities = ExchangeRateService.convert(s.total_liabilities, "CNY", default_currency, db)
        converted_net = ExchangeRateService.convert(s.net_worth, "CNY", default_currency, db)
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
            Asset.is_archived == False,
            Asset.current_value != None,
        )
        .all()
    )

    items = []
    for a in assets:
        asset_currency = a.currency or "CNY"
        converted = ExchangeRateService.convert(a.current_value, asset_currency, default_currency, db)
        items.append(
            TopAssetItem(
                id=a.id,
                name=a.name,
                category_name=a.category.name if a.category else "",
                icon=a.category.icon if a.category else "",
                current_value=round(converted, 2),
                currency=default_currency,
                original_value=a.current_value,
            )
        )

    # Sort by converted value and limit
    items.sort(key=lambda x: x.current_value, reverse=True)
    return items[:limit]


def get_daily_cost_ranking(db: Session, user: User) -> list[DailyCostItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.purchase_date != None,
            Asset.purchase_price != None,
        )
        .all()
    )

    items = []
    for a in assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            days = (date.today() - a.purchase_date).days
            years = days / 365.0
            total_cost = a.purchase_price + (a.annual_maintenance_cost or 0) * years

            # Convert to default currency
            asset_currency = a.currency or "CNY"
            dc_converted = ExchangeRateService.convert(dc, asset_currency, default_currency, db)
            total_cost_converted = ExchangeRateService.convert(total_cost, asset_currency, default_currency, db)

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
    return items


def get_low_usage_assets(db: Session, user: User) -> list[LowUsageItem]:
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
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
                    a.current_value or 0, a.currency or "CNY", default_currency, db
                ),
                2,
            ),
            usage_frequency=a.usage_frequency or "",
            purchase_date=a.purchase_date.isoformat() if a.purchase_date else None,
            currency=default_currency,
            original_value=a.current_value or 0,
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
            Asset.is_archived == False,
            Asset.asset_type == "financial",
            Asset.purchase_price != None,
            Asset.current_value != None,
        )
        .all()
    )

    items = []
    for a in assets:
        rr = compute_return_rate(a)
        if rr is not None:
            asset_currency = a.currency or "CNY"
            purchase_price_converted = ExchangeRateService.convert(
                a.purchase_price, asset_currency, default_currency, db
            )
            current_value_converted = ExchangeRateService.convert(
                a.current_value, asset_currency, default_currency, db
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
                    original_purchase_price=a.purchase_price,
                    original_current_value=a.current_value,
                )
            )

    items.sort(key=lambda x: x.return_rate, reverse=True)
    return items


def get_states_summary(db: Session, user: User) -> dict:
    family_id = user.family_id
    results = (
        db.query(
            Asset.status,
            func.count(Asset.id).label("count"),
            func.coalesce(func.sum(Asset.current_value), 0).label("total_value"),
        )
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .group_by(Asset.status)
        .all()
    )
    states = {}
    total_count = 0
    total_value = 0
    for r in results:
        states[r.status] = {"count": r.count, "total_value": r.total_value}
        total_count += r.count
        total_value += r.total_value
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
                Asset.is_archived == False,
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
) -> dict:
    """分页获取指定状态的资产列表"""
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
        try:
            filters.append(Asset.category_id == int(category_id))
        except ValueError:
            pass  # invalid category_id format — ignore filter, return all

    query = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(*filters)
        .order_by(Asset.updated_at.desc())
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


def get_expiring_soon_assets(db: Session, user: User, days_threshold: int = 90) -> list[ExpiringSoonItem]:
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
            Asset.is_archived == False,
            Asset.status == "in_use",  # Only active assets
            Asset.purchase_date != None,
            Asset.expected_lifespan_days != None,
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
                a.current_value or 0, asset_currency, default_currency, db
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
                    original_value=a.current_value or 0,
                )
            )
    
    # Sort by remaining days (most urgent first)
    items.sort(key=lambda x: x.remaining_days)
    return items
