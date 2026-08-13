import logging

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import case
from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.auth.jwt_utils import id_keyed_dict
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.child_economy_config import ChildEconomyConfig
from apps.backend.app.models.family_debt_thresholds import FamilyDebtThresholds
from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.schemas.auth import UpdateMemberInfoRequest, UserResponse
from apps.backend.app.schemas.coin import (
    ChildBalanceResponse,
    ChildLedgerEntryResponse,
    EarningRateResponse,
)
from apps.backend.app.schemas.family import (
    ChildEconomyConfigResponse,
    ChildEconomyConfigUpdate,
    FamilyResponse,
    FamilySettingsResponse,
    FamilySettingsUpdate,
    MemberSummary,
    UpdateFamilyTitleRequest,
)
from apps.backend.app.services import coin_transactions as coin_service
from apps.backend.app.services import family as family_service
from apps.backend.app.services.snapshot import generate_snapshots
from packages.core.roles import UserRole
from packages.db.models.family import Family

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/family", tags=["family"])


class UpdateRoleRequest(BaseModel):
    role: str


class ResetPasswordRequest(BaseModel):
    new_password: str


class UpdateStatusRequest(BaseModel):
    is_active: bool


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
    invitation_record = (
        db.query(FamilyInvitationCode)
        .filter(FamilyInvitationCode.used_by_family_id == family.id)
        .first()
    )
    creator_code = invitation_record.code if invitation_record else None
    from packages.core.settings import settings
    share_link_enabled = bool(settings.SHORTIO_API_KEY and settings.SHORTIO_DOMAIN)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        creator_code=creator_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
        share_link_enabled=share_link_enabled,
    )


@router.patch("/title", response_model=FamilyResponse)
def update_family_title(
    body: UpdateFamilyTitleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    family = family_service.update_family_title(db, user, body.custom_title)
    members = family_service.get_family_members(db, user)
    invitation_record = (
        db.query(FamilyInvitationCode)
        .filter(FamilyInvitationCode.used_by_family_id == family.id)
        .first()
    )
    creator_code = invitation_record.code if invitation_record else None
    from packages.core.settings import settings
    share_link_enabled = bool(settings.SHORTIO_API_KEY and settings.SHORTIO_DOMAIN)
    return FamilyResponse(
        id=family.id,
        name=family.name,
        custom_title=family.custom_title,
        invite_code=family.invite_code,
        creator_code=creator_code,
        created_by=family.created_by,
        members=[UserResponse.model_validate(m) for m in members],
        share_link_enabled=share_link_enabled,
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
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.family_id == family_id, Liability.is_active)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.family_id == family_id, Asset.is_archived.is_(False))
        .scalar()
    )
    # Coerce to float: asset values are Float, liability amounts are now
    # Decimal (Numeric); mixing them raises TypeError. The aggregate is a
    # dashboard stat where float precision is sufficient.
    total_assets = float(total_assets or 0)
    total_liabilities = float(total_liabilities or 0)
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
        .filter(Asset.user_id == member_id, Asset.is_archived.is_(False))
        .scalar()
    )
    total_liabilities = (
        db.query(sqlfunc.coalesce(sqlfunc.sum(Liability.remaining_amount), 0))
        .filter(Liability.user_id == member_id, Liability.is_active)
        .scalar()
    )
    asset_count = (
        db.query(sqlfunc.count(Asset.id))
        .filter(Asset.user_id == member_id, Asset.is_archived.is_(False))
        .scalar()
    )
    # Coerce to float: asset values are Float, liability amounts are Decimal
    # (Numeric); mixing them raises TypeError (mirror get_aggregate's fix).
    total_assets = float(total_assets or 0)
    total_liabilities = float(total_liabilities or 0)
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
    user: User = Depends(require_owner),
):
    member = family_service.update_member_role(db, user, member_id, body.role)
    return UserResponse.model_validate(member)


@router.patch("/members/{member_id}/info", response_model=UserResponse)
def update_member_info(
    member_id: int,
    body: UpdateMemberInfoRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    member = (
        db.query(User)
        .filter(
            User.id == member_id,
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
        )
        .first()
    )
    if not member:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    if body.display_name is not None:
        member.display_name = body.display_name
    if body.avatar_color is not None:
        member.avatar_color = body.avatar_color
    if body.birthday is not None:
        member.birthday = body.birthday
    if body.birthday_is_lunar is not None:
        member.birthday_is_lunar = body.birthday_is_lunar
    db.commit()
    db.refresh(member)
    return UserResponse.model_validate(member)


@router.delete("/members/{member_id}")
def remove_member(
    member_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    family_service.remove_member(db, user, member_id)
    return {"detail": "已移除"}


@router.post("/members/{member_id}/reset-password")
def reset_member_password(
    member_id: int,
    body: ResetPasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    family_service.reset_member_password(db, user, member_id, body.new_password)
    return {"detail": "✅ 密码已重置"}


@router.patch("/members/{member_id}/status", response_model=UserResponse)
def update_member_status(
    member_id: int,
    body: UpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    member = family_service.update_member_status(db, user, member_id, body.is_active)
    return UserResponse.model_validate(member)


@router.post("/invite-code")
def regenerate_invite_code(
    db: Session = Depends(get_db),
    user: User = Depends(require_owner),
):
    from apps.backend.app.services.auth import _check_invite_code_rate_limit

    _check_invite_code_rate_limit(str(user.id))
    family = family_service.regenerate_invite_code(db, user)
    return {"invite_code": family.invite_code}


@router.post("/share-link")
async def create_share_link(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Generate a short.io share link for the family invite code."""
    from short_io_api_client import AuthenticatedClient
    from short_io_api_client.api.link_management import post_links
    from short_io_api_client.models import PostLinksBody

    from packages.core.settings import settings

    if not settings.SHORTIO_API_KEY or not settings.SHORTIO_DOMAIN:
        raise AppError(ErrorCode.SHARE_LINK_NOT_CONFIGURED)

    family = db.query(Family).filter(Family.id == user.family_id).first()
    if not family:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    # Derive the public base URL from CORS_ORIGINS (first entry, typically the production domain)
    base_url = ""
    if settings.CORS_ORIGINS:
        import re
        match = re.match(r"(https?://[^/]+)", settings.CORS_ORIGINS[0])
        if match:
            base_url = match.group(1)
    if not base_url:
        raise AppError(ErrorCode.SHARE_LINK_NOT_CONFIGURED)

    original_url = f"{base_url}/join-family?code={family.invite_code}"

    client = AuthenticatedClient(
        base_url="https://api.short.io",
        token=settings.SHORTIO_API_KEY,
        prefix="",
    )

    try:
        result = await post_links.asyncio(
            client=client,
            body=PostLinksBody(
                original_url=original_url,
                domain=settings.SHORTIO_DOMAIN,
            ),
        )
    except Exception as exc:
        logger.warning("short.io API call failed: %s", exc)
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED) from exc

    if result is None:
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    # short.io returns error responses (403, 400, etc.) as typed result objects
    # rather than raising exceptions. Detect these and log the actual error.
    result_class_name = type(result).__name__
    if "Response4" in result_class_name or "Response5" in result_class_name:
        error_msg = getattr(result, "message", None) or str(result)
        logger.warning(
            "short.io rejected link creation: %s (domain=%s)",
            error_msg,
            settings.SHORTIO_DOMAIN,
        )
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    # The auto-generated response model stores most fields in additional_properties
    short_url = None
    if hasattr(result, "additional_properties"):
        short_url = (
            result.additional_properties.get("shortURL")
            or result.additional_properties.get("secureShortURL")
        )

    if not short_url:
        logger.warning(
            "short.io response had no shortURL field: %s",
            result_class_name,
        )
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    return {"short_url": short_url}


@router.post("/snapshots/generate")
def trigger_snapshots(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    snapshots = generate_snapshots(db, str(user.family_id))
    return {"detail": f"已生成 {len(snapshots)} 条快照"}


@router.patch("/settings", response_model=FamilySettingsResponse)
def update_family_settings(
    body: FamilySettingsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if user.role != UserRole.OWNER:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)

    config = db.query(ChildEconomyConfig).filter_by(family_id=user.family_id).first()
    if config is None:
        config = ChildEconomyConfig(family_id=user.family_id)
        db.add(config)

    if body.auto_approve_hours is not None:
        config.auto_approve_hours = body.auto_approve_hours
    if body.coin_copper_to_silver is not None:
        config.coin_copper_to_silver = body.coin_copper_to_silver
    if body.coin_silver_to_gold is not None:
        config.coin_silver_to_gold = body.coin_silver_to_gold
    if body.education_reward_enabled is not None:
        config.education_reward_enabled = body.education_reward_enabled
    if body.coin_to_yuan_rate is not None:
        config.coin_to_yuan_rate = body.coin_to_yuan_rate
    db.commit()
    db.refresh(config)

    # Handle report_auto_generate_enabled on Family model
    if body.report_auto_generate_enabled is not None:
        family = db.query(Family).filter_by(id=user.family_id).first()
        if family:
            family.report_auto_generate_enabled = body.report_auto_generate_enabled
            db.commit()

    # Handle ai_enabled on Family model
    if body.ai_enabled is not None:
        family = db.query(Family).filter_by(id=user.family_id).first()
        if family:
            family.ai_enabled = body.ai_enabled
            db.commit()

    family_row = db.query(Family).filter_by(id=user.family_id).first()

    return FamilySettingsResponse(
        auto_approve_hours=config.auto_approve_hours,
        ai_enabled=family_row.ai_enabled if family_row else False,
        coin_copper_to_silver=config.coin_copper_to_silver,
        coin_silver_to_gold=config.coin_silver_to_gold,
        education_reward_enabled=config.education_reward_enabled,
        coin_to_yuan_rate=config.coin_to_yuan_rate,
        report_auto_generate_enabled=family_row.report_auto_generate_enabled if family_row else False,
    )


@router.get("/settings", response_model=FamilySettingsResponse)
def get_family_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    config = db.query(ChildEconomyConfig).filter_by(family_id=user.family_id).first()
    if config is None:
        config = ChildEconomyConfig(family_id=user.family_id)
        db.add(config)
        db.commit()
        db.refresh(config)

    family_row = db.query(Family).filter_by(id=user.family_id).first()

    return FamilySettingsResponse(
        auto_approve_hours=config.auto_approve_hours,
        ai_enabled=family_row.ai_enabled if family_row else False,
        coin_copper_to_silver=config.coin_copper_to_silver,
        coin_silver_to_gold=config.coin_silver_to_gold,
        education_reward_enabled=config.education_reward_enabled,
        coin_to_yuan_rate=config.coin_to_yuan_rate,
        report_auto_generate_enabled=family_row.report_auto_generate_enabled if family_row else False,
    )


# W5 (Plan B T8): high-interest-debt thresholds. A liability is "high-interest"
# when its annual interest_rate >= its category's threshold. Owner-only write
# (spec §5.1 security-lens: a non-owner must not suppress/unsuppress the whole
# family's warnings); all family members read.
DEFAULT_DEBT_THRESHOLDS: dict[str, int] = {
    "credit_card": 12,
    "personal_loan": 10,
    "mortgage": 6,
    "other": 10,
}


class DebtThresholdsRequest(BaseModel):
    thresholds: dict[str, int]


def _thresholds_dict(cfg: FamilyDebtThresholds) -> dict[str, int]:
    return {
        "credit_card": cfg.credit_card,
        "personal_loan": cfg.personal_loan,
        "mortgage": cfg.mortgage,
        "other": cfg.other,
    }


def _get_or_create_debt_thresholds(db: Session, family_id: int) -> FamilyDebtThresholds:
    cfg = db.query(FamilyDebtThresholds).filter_by(family_id=family_id).first()
    if cfg is None:
        cfg = FamilyDebtThresholds(family_id=family_id)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/debt-thresholds")
def get_debt_thresholds(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """W5: read debt-interest thresholds (visible to all family members)."""
    cfg = _get_or_create_debt_thresholds(db, user.family_id)
    return {"thresholds": _thresholds_dict(cfg)}


@router.put("/debt-thresholds")
def put_debt_thresholds(
    body: DebtThresholdsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """W5: update debt-interest thresholds. Owner-only — a non-owner could
    suppress/unsuppress the whole family's high-interest warnings."""
    if user.role != UserRole.OWNER:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)

    cfg = _get_or_create_debt_thresholds(db, user.family_id)
    # Merge: only the 4 known categories are writable; unknown keys ignored.
    for key in DEFAULT_DEBT_THRESHOLDS:
        if key in body.thresholds:
            setattr(cfg, key, body.thresholds[key])
    db.commit()
    db.refresh(cfg)
    return {"thresholds": _thresholds_dict(cfg)}


@router.get("/children/{child_id}/balance", response_model=ChildBalanceResponse)
def get_child_balance(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Parent queries a specific child's coin balance."""
    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
        )
        .first()
    )
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    balance = coin_service.get_balance(db, child_id)
    return {"balance": balance}


@router.get(
    "/children/{child_id}/coins/ledger", response_model=list[ChildLedgerEntryResponse]
)
def get_child_ledger(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Parent queries a specific child's coin ledger for trust-contract math
    (days-estimate delta on cost edits, per R14)."""
    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
        )
        .first()
    )
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    txs = coin_service.list_transactions(db, child_id, user.family_id)
    return [
        ChildLedgerEntryResponse(amount=tx.amount, created_at=tx.created_at)
        for tx in txs
    ]


@router.get("/children/{child_id}/earning-rate", response_model=EarningRateResponse)
def get_child_earning_rate(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return the child's average daily coin earning rate over the past 7 days.

    Uses earning transactions (chore_earn, parent_grant with amount > 0) from
    the last 7 days to compute a daily average and project suggested wish costs
    for 7-, 14-, and 30-day savings horizons.

    If fewer than 3 distinct earning days exist, daily_avg=0 and all suggestions=0
    so the frontend can show an "insufficient data" notice.
    """
    from datetime import date, timedelta
    from math import ceil

    from apps.backend.app.models.coin_transaction import CoinTransaction

    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
        )
        .first()
    )
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)

    cutoff = date.today() - timedelta(days=7)
    # SQLite stores DateTime without timezone; compare as naive date string
    from sqlalchemy import func as sa_func

    rows = (
        db.query(CoinTransaction)
        .filter(
            CoinTransaction.child_user_id == child_id,
            CoinTransaction.transaction_type.in_(["chore_earn", "parent_grant"]),
            CoinTransaction.amount > 0,
            sa_func.date(CoinTransaction.created_at) >= cutoff.isoformat(),
        )
        .all()
    )

    if not rows:
        return EarningRateResponse(
            daily_avg=0.0,
            suggested_7d=0,
            suggested_14d=0,
            suggested_30d=0,
            data_days=0,
        )

    total_earned = sum(tx.amount for tx in rows)
    distinct_days = len({tx.created_at.date() for tx in rows})

    if distinct_days < 3:
        return EarningRateResponse(
            daily_avg=0.0,
            suggested_7d=0,
            suggested_14d=0,
            suggested_30d=0,
            data_days=distinct_days,
        )

    daily_avg = total_earned / 7.0
    suggested_7d = min(max(ceil(daily_avg * 7), 1), 9999)
    suggested_14d = min(max(ceil(daily_avg * 14), 1), 9999)
    suggested_30d = min(max(ceil(daily_avg * 30), 1), 9999)

    return EarningRateResponse(
        daily_avg=daily_avg,
        suggested_7d=suggested_7d,
        suggested_14d=suggested_14d,
        suggested_30d=suggested_30d,
        data_days=distinct_days,
    )


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

    from apps.backend.app.models.coin_transaction import CoinTransaction as CT

    # Get all child IDs in this family
    children = (
        db.query(User.id)
        .filter(
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
            User.is_active,
        )
        .all()
    )
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
    from apps.backend.app.models.child_economy_config import ChildEconomyConfig

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
    user: User = Depends(require_owner),
) -> ChildEconomyConfigResponse:
    """更新子经济配置（仅 owner）。"""

    from apps.backend.app.models.child_economy_config import ChildEconomyConfig

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
    if body.education_reward_enabled is not None:
        cfg.education_reward_enabled = body.education_reward_enabled
    if body.coin_to_yuan_rate is not None:
        cfg.coin_to_yuan_rate = body.coin_to_yuan_rate
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

    from apps.backend.app.models.chore import ChoreInstance

    # Current ISO week bucket: YYYY-Www
    today = date.today()
    iso_year, iso_week, _ = today.isocalendar()
    week_bucket = f"{iso_year}-W{iso_week:02d}"

    children = (
        db.query(User.id)
        .filter(
            User.family_id == user.family_id,
            User.role == UserRole.CHILD,
            User.is_active,
        )
        .all()
    )
    child_ids = [c.id for c in children]
    if not child_ids:
        return {}

    # Single query: count total and approved per child for this week
    rows = (
        db.query(
            ChoreInstance.child_user_id,
            sqlfunc.count(ChoreInstance.id).label("total"),
            sqlfunc.sum(case((ChoreInstance.status == "approved", 1), else_=0)).label(
                "completed"
            ),
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
