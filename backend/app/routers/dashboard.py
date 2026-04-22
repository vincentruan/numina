import random

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.user import User
from app.schemas.dashboard import (
    AllocationResponse,
    DailyCostItem,
    ExpiringSoonItem,
    InvestmentReturnItem,
    LowUsageItem,
    OverviewResponse,
    TopAssetItem,
    TrendResponse,
)
from app.services import dashboard as dashboard_service
from app.services.cache.factory import get_dashboard_cache

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_overview(db, user)


@router.get("/allocation", response_model=AllocationResponse)
def get_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_allocation(db, user)


@router.get("/trend", response_model=TrendResponse)
def get_trend(
    period: str = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_trend(db, user, period)


@router.get("/top-assets", response_model=list[TopAssetItem])
def get_top_assets(
    limit: int = Query(10),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_top_assets(db, user, limit)


@router.get("/daily-cost-ranking", response_model=list[DailyCostItem])
def get_daily_cost_ranking(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_daily_cost_ranking(db, user)


@router.get("/low-usage-assets", response_model=list[LowUsageItem])
def get_low_usage_assets(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_low_usage_assets(db, user)


@router.get("/investment-returns", response_model=list[InvestmentReturnItem])
def get_investment_returns(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_investment_returns(db, user)


@router.get("/states-summary")
def get_states_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_states_summary(db, user)


@router.get("/home-assets")
def get_home_assets(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get assets grouped by status for home page display."""
    return dashboard_service.get_home_assets(db, user, limit)


@router.get("/home-assets/{status}")
def get_home_assets_paginated(
    status: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """分页获取指定状态的资产列表"""
    valid_statuses = ["in_use", "idle", "sold", "retired"]
    if status not in valid_statuses:
        raise AppError(
            ErrorCode.DASHBOARD_INVALID_STATUS,
            detail=f"Invalid status: {status}. Must be one of {valid_statuses}",
        )
    return dashboard_service.get_home_assets_page(db, user, status, page, page_size)


@router.get("/expiring-soon", response_model=list[ExpiringSoonItem])
def get_expiring_soon(
    days_threshold: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """
    Get assets approaching end of expected lifespan.

    Physical assets (electronics) - normal lifecycle, show with muted color.
    Financial assets (accounts, subscriptions) - needs attention, show with alert color.
    """
    return dashboard_service.get_expiring_soon_assets(db, user, days_threshold)


@router.get("/bundle")
def get_bundle(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get all dashboard data in a single request.

    Combines overview, states-summary, home-assets, allocation, trend,
    low-usage-assets, and expiring-soon into one cached response.
    Uses fixed default parameters matching frontend fetchAll() defaults.
    """
    cache = get_dashboard_cache()
    cache_key = f"dashboard:bundle:{user.family_id}"

    cached = cache.get(cache_key)
    if cached is not None:
        return JSONResponse(content=cached)

    overview = dashboard_service.get_overview(db, user)
    states_summary = dashboard_service.get_states_summary(db, user)
    home_assets = dashboard_service.get_home_assets(db, user, limit=5)
    allocation = dashboard_service.get_allocation(db, user)
    trend = dashboard_service.get_trend(db, user, period="month")
    low_usage_assets = dashboard_service.get_low_usage_assets(db, user)
    expiring_soon = dashboard_service.get_expiring_soon_assets(db, user, days_threshold=90)

    bundle = {
        "overview": overview.model_dump(mode='json'),
        "statesSummary": states_summary,
        "homeAssets": {k: [item.model_dump(mode='json') for item in v] for k, v in home_assets.items()},
        "allocation": allocation.model_dump(mode='json'),
        "trend": trend.model_dump(mode='json'),
        "lowUsageAssets": [item.model_dump(mode='json') for item in low_usage_assets],
        "expiringSoon": [item.model_dump(mode='json') for item in expiring_soon],
    }

    cache.set(cache_key, bundle, ttl_seconds=random.randint(60, 90))
    return JSONResponse(content=bundle)
