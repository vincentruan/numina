from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.dashboard import (
    AllocationResponse,
    DailyCostItem,
    EducationRewardSummaryResponse,
    ExpiringSoonItem,
    InsightsResponse,
    InvestmentReturnItem,
    LiabilityAllocationResponse,
    LowUsageItem,
    NarrativeResponse,
    NewAssetsResponse,
    OverviewResponse,
    TopAssetItem,
    TrendResponse,
    UpcomingPaymentsResponse,
)
from apps.backend.app.services import dashboard as dashboard_service

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


@router.get("/liability-allocation", response_model=LiabilityAllocationResponse)
def get_liability_allocation(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_liability_allocation(db, user)


@router.get("/trend", response_model=TrendResponse)
def get_trend(
    period: Literal["month", "quarter", "year"] = Query("month"),
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
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_daily_cost_ranking(db, user, limit)


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


@router.get("/education-reward-summary", response_model=EducationRewardSummaryResponse)
def get_education_reward_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """B1 教育奖励支出专项统计（累计 + 本月 + 笔数）。"""
    return dashboard_service.get_education_reward_summary(db, user)


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


@router.get("/home-assets/{status}/categories")
def get_home_assets_category_counts(
    status: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """获取指定状态下各分类的资产数量（用于分类导航）"""
    valid_statuses = ["in_use", "idle", "sold", "retired"]
    if status not in valid_statuses:
        raise AppError(
            ErrorCode.DASHBOARD_INVALID_STATUS,
            details=f"Invalid status: {status}. Must be one of {valid_statuses}",
        )
    return dashboard_service.get_home_assets_category_counts(db, user, status)


@router.get("/home-assets/{status}")
def get_home_assets_paginated(
    status: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str | None = Query(None),
    sort_order: str = Query("desc"),
    asset_type: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """分页获取指定状态的资产列表（支持搜索/排序/类型筛选）"""
    valid_statuses = ["in_use", "idle", "sold", "retired"]
    if status not in valid_statuses:
        raise AppError(
            ErrorCode.DASHBOARD_INVALID_STATUS,
            details=f"Invalid status: {status}. Must be one of {valid_statuses}",
        )
    return dashboard_service.get_home_assets_page(
        db, user, status, page, page_size, category_id, search, sort_by, sort_order, asset_type
    )


@router.get("/new-assets", response_model=NewAssetsResponse)
def get_new_assets(
    period: Literal["month", "quarter", "year"] = Query("month"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return dashboard_service.get_new_assets(db, user, period)


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


@router.get("/insights", response_model=InsightsResponse)
def get_insights(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """
    Get comprehensive insights data for the Insights tab.
    Returns S0-S5 all sections in one API call for efficiency.
    """
    return dashboard_service.get_insights(db, user)


@router.get("/narrative", response_model=NarrativeResponse)
async def get_narrative(
    force: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Dashboard narrative — AI-generated monthly financial story (R1-R5).

    Returns cached or freshly-generated narrative text. 4h TTL; threshold gate
    (asset_count >= 5, history >= 3 months). Silent degradation on agent failure.
    ``?force=true`` bypasses cache and regenerates.

    DB session is released before agent dispatch (P0 fix): all DB work (cache
    check, threshold, context building) happens here; generate_narrative only
    dispatches the agent and persists via its own short-lived session.
    """
    from apps.backend.app.database import SessionLocal
    from apps.backend.app.services.dashboard_narrative import (
        MIN_ASSET_COUNT,
        SKILL_ID,
        _build_narrative_context,
        _check_history_threshold,
        generate_narrative,
    )
    from apps.backend.app.services.finance_coach_cache import (
        is_cache_fresh,
        latest_by_skill,
    )

    family_id = user.family_id

    # 1. Cache check (R4) — uses request-scoped db
    if not force:
        cached = latest_by_skill(db, family_id, SKILL_ID)
        if is_cache_fresh(cached, SKILL_ID) and cached is not None:
            report = cached.report_json or {}
            narrative = report.get("narrative", "")
            from apps.backend.app.services.dashboard_narrative import (
                _extract_first_sentence,
            )
            return NarrativeResponse(
                narrative=narrative or None,
                first_sentence=report.get(
                    "first_sentence", _extract_first_sentence(narrative)
                ),
                generated_at=cached.generated_at.isoformat()
                if cached.generated_at
                else None,
            )

    # 2. Threshold check (R5) — uses request-scoped db for overview,
    #    then releases it before the history check (which opens its own session).
    overview = dashboard_service.get_overview(db, user)
    if overview.asset_count < MIN_ASSET_COUNT:
        return NarrativeResponse()

    # History check uses a short-lived session (P0 fix — don't hold request db)
    if not _check_history_threshold(int(family_id), SessionLocal):
        return NarrativeResponse()

    # 3. Build context — uses request-scoped db for insights
    try:
        insights = dashboard_service.get_insights(db, user)
    except Exception:
        insights = None
    context = _build_narrative_context(overview, insights)

    # 4. Agent dispatch — no DB session held (P0 fix)
    result = await generate_narrative(user, context)
    return NarrativeResponse(**result)


@router.get("/upcoming-payments", response_model=UpcomingPaymentsResponse)
def get_upcoming_payments(
    days: int = Query(7, ge=0, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """获取即将到期的负债还款列表（默认7天内）"""
    return dashboard_service.get_upcoming_payments(db, user, days)
