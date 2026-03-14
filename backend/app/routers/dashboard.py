from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.dashboard import (
    AllocationResponse,
    DailyCostItem,
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
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_overview(db, user)


@router.get("/allocation", response_model=AllocationResponse)
def get_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_allocation(db, user)


@router.get("/trend", response_model=TrendResponse)
def get_trend(
    period: str = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_trend(db, user, period)


@router.get("/top-assets", response_model=list[TopAssetItem])
def get_top_assets(
    limit: int = Query(10),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_top_assets(db, user, limit)


@router.get("/daily-cost-ranking", response_model=list[DailyCostItem])
def get_daily_cost_ranking(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_daily_cost_ranking(db, user)


@router.get("/low-usage-assets", response_model=list[LowUsageItem])
def get_low_usage_assets(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_low_usage_assets(db, user)


@router.get("/investment-returns", response_model=list[InvestmentReturnItem])
def get_investment_returns(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return dashboard_service.get_investment_returns(db, user)
