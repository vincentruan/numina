from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
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
