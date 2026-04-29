from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.auth.jwt_utils import id_keyed_dict
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.asset import Asset
from app.models.family import Family
from app.models.liability import Liability
from app.models.user import User
from app.schemas.auth import UserResponse
from app.schemas.coin import ChildBalanceResponse
from app.schemas.family import (
    ChildEconomyConfigResponse,
    ChildEconomyConfigUpdate,
    FamilyResponse,
    FamilySettingsResponse,
    FamilySettingsUpdate,
    MemberSummary,
    UpdateFamilyTitleRequest,
)
from app.services import coin_transactions as coin_service
from app.services import family as family_service
from app.services.snapshot import generate_snapshots

router = APIRouter(prefix="/family", tags=["family"])


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/info", response_model=FamilyResponse)
@router.get("", response_model=FamilyResponse)
def get_family(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    response.headers["Cache-Control"] = "private, max-age=300"
    family = family_service.get_family_info(db, user)
    members = family_service.get_family_members(db, user)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
    )

@router.patch("/title", response_model=FamilyResponse)
def update_family_title(
    body: UpdateFamilyTitleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family = family_service.update_family_title(db, user, body.custom_title)
    members = family_service.get_family_members(db, user)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
    )


@router.get("/members", response_model=list[UserResponse])
def get_members(
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    response.headers["Cache-Control"] = "private, max-age=300"
    members = family_service.get_family_members(db, user)
    return [UserResponse.model_validate(m) for m in members]


@router.get("/aggregate")
def get_aggregate(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_id = user.family_id
    total_assets = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Asset.current_value), 0))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )
    return {
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "net_worth": total_assets - total_liabilities,
        "asset_count": asset_count,
    }


@router.get("/members/{member_id}/summary", response_model=MemberSummary)
def get_member_summary(
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    member = (
        db.query(User)
        .filter(User.id == member_id, User.family_id == user.family_id)
        .first()
    )
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)

    total_assets = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Asset.current_value), 0))
        .filter(Asset.user_id == member_id, Asset.is_archived == False)
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.user_id == member_id, Liability.is_active == True)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.user_id == member_id, Asset.is_archived == False)
        .scalar()
    )
    return MemberSummary(
        user=UserResponse.model_validate(member),
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=total_assets - total_liabilities,
        asset_count=asset_count,
    )


@router.patch("/members/{member_id}/role", response_model=UserResponse)
def update_member_role(
    member_id: int,
    body: UpdateRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    member = family_service.update_member_role(db, user, member_id, body.role)
    return UserResponse.model_validate(member)


@router.delete("/members/{member_id}")
def remove_member(
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family_service.remove_member(db, user, member_id)
    return {"detail": "已移除"}


@router.post("/invite-code")
def regenerate_invite_code(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if user.role != 'owner':
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    family = family_service.regenerate_invite_code(db, user)
    return {"invite_code": family.invite_code}


@router.post("/snapshots/generate")
def trigger_snapshots(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    snapshots = generate_snapshots(db, user.family_id)
    return {"detail": f"已生成 {len(snapshots)} 条快照"}


@router.patch("/settings", response_model=FamilySettingsResponse)
def update_family_settings(
    body: FamilySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if user.role != "owner":
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    family = db.query(Family).filter_by(id=user.family_id).first()
    if body.auto_approve_hours is not None:
        family.auto_approve_hours = body.auto_approve_hours
    if body.ai_enabled is not None:
        family.ai_enabled = body.ai_enabled
    if body.coin_copper_to_silver is not None:
        family.coin_copper_to_silver = body.coin_copper_to_silver
    if body.coin_silver_to_gold is not None:
        family.coin_silver_to_gold = body.coin_silver_to_gold
    db.commit()
    db.refresh(family)
    return FamilySettingsResponse(
        auto_approve_hours=family.auto_approve_hours,
        ai_enabled=family.ai_enabled,
        coin_copper_to_silver=family.coin_copper_to_silver,
        coin_silver_to_gold=family.coin_silver_to_gold,
    )


@router.get("/settings", response_model=FamilySettingsResponse)
def get_family_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family = db.query(Family).filter_by(id=user.family_id).first()
    return FamilySettingsResponse(
        auto_approve_hours=family.auto_approve_hours,
        ai_enabled=family.ai_enabled,
        coin_copper_to_silver=family.coin_copper_to_silver,
        coin_silver_to_gold=family.coin_silver_to_gold,
    )


@router.get("/children/{child_id}/balance", response_model=ChildBalanceResponse)
def get_child_balance(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Parent queries a specific child's coin balance."""
    child = db.query(User).filter(
        User.id == child_id,
        User.family_id == user.family_id,
        User.role == "child",
    ).first()
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    balance = coin_service.get_balance(db, child_id)
    return {"balance": balance}


@router.get("/children/balances", response_model=dict[str, int])
def get_all_child_balances(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return {child_user_id: balance} for all children in the family.

    Single GROUP BY query — avoids N+1 when parent dashboard loads balances
    for multiple children simultaneously.
    """
    from sqlalchemy import func as sa_func

    from app.models.coin_transaction import CoinTransaction as CT

    # Get all child IDs in this family
    children = db.query(User.id).filter(
        User.family_id == user.family_id,
        User.role == "child",
        User.is_active == True,
    ).all()
    child_ids = [c.id for c in children]
    if not child_ids:
        return {}

    # Single aggregation query
    rows = (
        db.query(CT.child_user_id, sa_func.sum(CT.amount).label("balance"))
        .filter(CT.child_user_id.in_(child_ids))
        .group_by(CT.child_user_id)
        .all()
    )
    balance_map = {row.child_user_id: row.balance or 0 for row in rows}
    # Ensure children with no transactions appear with balance 0
    for cid in child_ids:
        balance_map.setdefault(cid, 0)
    return id_keyed_dict(balance_map)


class ChoreStats(BaseModel):
    completed_this_week: int
    total_this_week: int


@router.get("/economy-config", response_model=ChildEconomyConfigResponse)
def get_economy_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
) -> ChildEconomyConfigResponse:
    """获取子经济配置（所有成员可查看）。"""
    from app.models.child_economy_config import ChildEconomyConfig

    cfg = db.query(ChildEconomyConfig).filter_by(family_id=user.family_id).first()
    if not cfg:
        cfg = ChildEconomyConfig(family_id=user.family_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return ChildEconomyConfigResponse.model_validate(cfg)


@router.put("/economy-config", response_model=ChildEconomyConfigResponse)
def update_economy_config(
    body: ChildEconomyConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
) -> ChildEconomyConfigResponse:
    """更新子经济配置（仅 owner）。"""
    if user.role != "owner":
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)

    from app.models.child_economy_config import ChildEconomyConfig

    cfg = db.query(ChildEconomyConfig).filter_by(family_id=user.family_id).first()
    if not cfg:
        cfg = ChildEconomyConfig(family_id=user.family_id)
        db.add(cfg)
    if body.auto_approve_hours is not None:
        cfg.auto_approve_hours = body.auto_approve_hours
    if body.coin_copper_to_silver is not None:
        cfg.coin_copper_to_silver = body.coin_copper_to_silver
    if body.coin_silver_to_gold is not None:
        cfg.coin_silver_to_gold = body.coin_silver_to_gold
    db.commit()
    db.refresh(cfg)
    return ChildEconomyConfigResponse.model_validate(cfg)


@router.get("/children/chore-stats", response_model=dict[str, ChoreStats])
def get_children_chore_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return weekly chore completion stats for all children in the family.

    Returns {child_user_id: {completed_this_week, total_this_week}}.
    'completed_this_week' = approved instances in the current ISO week.
    'total_this_week' = all instances (any status) in the current ISO week.
    """
    from datetime import date

    from app.models.chore import ChoreInstance

    # Current ISO week bucket: YYYY-Www
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_bucket = f"{iso_year}-W{iso_week:02d}"

    children = db.query(User.id).filter(
        User.family_id == user.family_id,
        User.role == "child",
        User.is_active == True,
    ).all()
    child_ids = [c.id for c in children]
    if not child_ids:
        return {}

    # Single query: count total and approved per child for this week
    rows = (
        db.query(
            ChoreInstance.child_user_id,
            sqlfunc.count(ChoreInstance.id).label("total"),
            sqlfunc.sum(
                case((ChoreInstance.status == "approved", 1), else_=0)
            ).label("completed"),
        )
        .filter(
            ChoreInstance.family_id == user.family_id,
            ChoreInstance.child_user_id.in_(child_ids),
            ChoreInstance.date_bucket == week_bucket,
        )
        .group_by(ChoreInstance.child_user_id)
        .all()
    )

    stats = {
        row.child_user_id: ChoreStats(
            completed_this_week=row.completed or 0,
            total_this_week=row.total or 0,
        )
        for row in rows
    }
    # Ensure all children appear even with no chores this week
    for cid in child_ids:
        stats.setdefault(cid, ChoreStats(completed_this_week=0, total_this_week=0))
    return id_keyed_dict(stats)
