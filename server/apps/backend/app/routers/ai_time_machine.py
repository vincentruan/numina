"""资产时光机 API 端点 — What-if 模拟、财务推演、购买力计算。"""

from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category_financial_default import CategoryFinancialDefault
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.snapshot import AssetSnapshot
from apps.backend.app.models.user import User
from apps.backend.app.schemas.projection import ProjectionRequest, ProjectionResponse
from apps.backend.app.schemas.purchasing_power import PurchasingPowerResponse
from apps.backend.app.schemas.whatif import WhatIfRequest, WhatIfResponse
from apps.backend.app.services import dashboard as dashboard_service
from apps.backend.app.services.projection import calculate_projection
from apps.backend.app.services.purchasing_power import calculate_purchasing_power
from apps.backend.app.services.whatif import calculate_whatif

router = APIRouter(prefix="/ai", tags=["ai-time-machine"])


# ---------------------------------------------------------------------------
# Purchasing Power
# ---------------------------------------------------------------------------


@router.get("/purchasing-power", response_model=PurchasingPowerResponse)
def get_purchasing_power(
    amount: float = Query(..., gt=0),
    from_year: int = Query(..., ge=1990, le=2050),
    to_year: int = Query(..., ge=1990, le=2050),
    custom_inflation_rate: float | None = Query(None, ge=0, le=1),
    user: User = Depends(require_adult),
):
    return calculate_purchasing_power(
        amount=amount,
        from_year=from_year,
        to_year=to_year,
        custom_inflation_rate=custom_inflation_rate,
    )


# ---------------------------------------------------------------------------
# What-if
# ---------------------------------------------------------------------------


def _load_family_assets(db: Session, family_id: int) -> tuple[list[dict], dict]:
    """Load family assets and category defaults, return (assets_list, asset_id_set)."""
    db_assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .all()
    )
    category_ids = {a.category_id for a in db_assets}
    defaults = {
        d.category_id: d
        for d in db.query(CategoryFinancialDefault)
        .filter(CategoryFinancialDefault.category_id.in_(category_ids))
        .all()
    }

    assets = []
    for a in db_assets:
        d = defaults.get(a.category_id)
        dep = d.default_annual_depreciation if d else 0.1
        ret = d.default_annual_return if d else 0.0
        # Use asset's own lifespan if available
        if a.expected_lifespan_days and a.expected_lifespan_days > 0:
            dep = 1.0 / (a.expected_lifespan_days / 365.0)
        assets.append({
            "id": a.id,
            "current_value": a.current_value or 0,
            "asset_type": a.asset_type,
            "annual_depreciation": dep,
            "annual_maintenance_cost": a.annual_maintenance_cost or 0,
            "annual_return": a.interest_rate or ret,
        })
    return assets, {a["id"] for a in assets}


def _load_family_liabilities(db: Session, family_id: int) -> list[dict]:
    db_liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active.is_(True))
        .all()
    )
    return [
        {
            "remaining_amount": li.remaining_amount or 0,
            "monthly_payment": li.monthly_payment or 0,
            "end_year": li.end_date.year if li.end_date else None,
        }
        for li in db_liabilities
    ]


@router.post("/whatif", response_model=WhatIfResponse)
def run_whatif(
    body: WhatIfRequest,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    family_id = user.family_id
    assets, asset_ids = _load_family_assets(db, family_id)

    # Validate asset_ids in actions
    for act in body.actions:
        if act.asset_id is not None and act.asset_id not in asset_ids:
            raise AppError(ErrorCode.ASSET_NOT_FOUND)

    liabilities = _load_family_liabilities(db, family_id)

    # Calculate current net worth
    overview = dashboard_service.get_overview(db, user)
    current_net_worth = overview.net_worth

    return calculate_whatif(
        current_net_worth=current_net_worth,
        assets=assets,
        liabilities=liabilities,
        actions=[a.model_dump() for a in body.actions],
        projection_years=body.projection_years,
        inflation_rate=body.inflation_rate,
    )


# ---------------------------------------------------------------------------
# Projection
# ---------------------------------------------------------------------------


@router.post("/projection", response_model=ProjectionResponse)
def run_projection(
    body: ProjectionRequest,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    family_id = user.family_id
    assets, _ = _load_family_assets(db, family_id)
    liabilities = _load_family_liabilities(db, family_id)

    # Load history from snapshots
    snapshots = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id.is_(None),
        )
        .order_by(AssetSnapshot.snapshot_date.asc())
        .all()
    )
    history: list[dict] = []
    seen_years: set[int] = set()
    for s in snapshots:
        y = s.snapshot_date.year
        if y not in seen_years:
            seen_years.add(y)
            history.append({
                "year": y,
                "total_assets": s.total_assets or 0,
                "total_liabilities": s.total_liabilities or 0,
                "net_worth": s.net_worth or 0,
                "real_net_worth": s.net_worth or 0,
            })

    return calculate_projection(
        assets=assets,
        liabilities=liabilities,
        history_points=history,
        projection_years=body.projection_years,
        inflation_rate=body.inflation_rate,
        current_year=date_type.today().year,
        custom_overrides=body.custom_overrides,
    )
