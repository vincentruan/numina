from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.category import Category
from app.models.liability import Liability
from app.models.snapshot import AssetSnapshot
from app.models.user import User
from app.schemas.dashboard import (
    AllocationItem,
    AllocationResponse,
    DailyCostItem,
    InvestmentReturnItem,
    LowUsageItem,
    OverviewResponse,
    TopAssetItem,
    TrendPoint,
    TrendResponse,
)
from app.services.asset import compute_daily_cost, compute_return_rate


def get_overview(db: Session, user: User) -> OverviewResponse:
    family_id = user.family_id

    total_assets_val = (
        db.query(func.coalesce(func.sum(Asset.current_value), 0))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )
    total_liabilities_val = (
        db.query(func.coalesce(func.sum(Liability.remaining_amount), 0))
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .scalar()
    )
    asset_count = (
        db.query(func.count(Asset.id))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )

    # Calculate total daily cost
    daily_cost_assets = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived == False,
            Asset.purchase_date != None,
            Asset.purchase_price != None,
        )
        .all()
    )
    total_daily_cost = 0.0
    for a in daily_cost_assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            total_daily_cost += dc
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
    if last_snapshot and last_snapshot.net_worth != 0:
        current_net = total_assets_val - total_liabilities_val
        mom_change = round((current_net - last_snapshot.net_worth) / abs(last_snapshot.net_worth) * 100, 2)

    return OverviewResponse(
        total_assets=total_assets_val,
        total_liabilities=total_liabilities_val,
        net_worth=total_assets_val - total_liabilities_val,
        asset_count=asset_count,
        month_over_month_change=mom_change,
        total_daily_cost=total_daily_cost,
    )


def get_allocation(db: Session, user: User) -> AllocationResponse:
    family_id = user.family_id
    results = (
        db.query(
            Category.id,
            Category.name,
            Category.icon,
            Category.color,
            func.coalesce(func.sum(Asset.current_value), 0).label("amount"),
        )
        .join(Asset, Asset.category_id == Category.id)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .group_by(Category.id)
        .all()
    )

    total = sum(r.amount for r in results) or 1
    items = [
        AllocationItem(
            category_id=r.id,
            category_name=r.name,
            icon=r.icon,
            color=r.color,
            amount=r.amount,
            percentage=round(r.amount / total * 100, 2),
        )
        for r in results
    ]
    return AllocationResponse(items=items, total=total)


def get_trend(db: Session, user: User, period: str = "month") -> TrendResponse:
    family_id = user.family_id
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

    points = [
        TrendPoint(
            date=s.snapshot_date.isoformat(),
            total_assets=s.total_assets,
            total_liabilities=s.total_liabilities,
            net_worth=s.net_worth,
        )
        for s in snapshots
    ]
    return TrendResponse(points=points)


def get_top_assets(db: Session, user: User, limit: int = 10) -> list[TopAssetItem]:
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.current_value != None,
        )
        .order_by(Asset.current_value.desc())
        .limit(limit)
        .all()
    )
    return [
        TopAssetItem(
            id=a.id,
            name=a.name,
            category_name=a.category.name if a.category else "",
            icon=a.category.icon if a.category else "",
            current_value=a.current_value,
        )
        for a in assets
    ]


def get_daily_cost_ranking(db: Session, user: User) -> list[DailyCostItem]:
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
            items.append(
                DailyCostItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    daily_cost=dc,
                    days_used=days,
                    total_cost=round(total_cost, 2),
                )
            )

    items.sort(key=lambda x: x.daily_cost, reverse=True)
    return items


def get_low_usage_assets(db: Session, user: User) -> list[LowUsageItem]:
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
            current_value=a.current_value or 0,
            usage_frequency=a.usage_frequency or "",
            purchase_date=a.purchase_date.isoformat() if a.purchase_date else None,
        )
        for a in assets
    ]


def get_investment_returns(db: Session, user: User) -> list[InvestmentReturnItem]:
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
            items.append(
                InvestmentReturnItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    purchase_price=a.purchase_price,
                    current_value=a.current_value,
                    return_rate=rr,
                    profit=round(a.current_value - a.purchase_price, 2),
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
    from app.services.asset import compute_daily_cost, compute_return_rate
    from app.schemas.asset import AssetResponse

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
