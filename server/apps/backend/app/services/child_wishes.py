from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.child_wish_cost_history import ChildWishCostHistory
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.user import User
from apps.backend.app.schemas.child_wish import (
    ApproveChildWishRequest,
    ChildWishCostHistoryItem,
    ChildWishCreate,
    ChildWishListResponse,
    ChildWishResponse,
    ChildWishStatsResponse,
    ChildWishStatsSimItem,
    ParentWishResponse,
    RealizeChildWishRequest,
    RejectChildWishRequest,
    UpdateChildWishCostRequest,
)
from apps.backend.app.services.coin_transactions import get_balance
from apps.backend.app.services.notification_bus import fire_notification

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _to_child_response(wish: ChildWish, balance: int = 0) -> ChildWishResponse:
    progress: float | None = None
    if wish.star_coin_cost is not None and wish.star_coin_cost > 0:
        progress = min(balance / wish.star_coin_cost, 1.0)
    return ChildWishResponse(
        id=wish.id,
        family_id=wish.family_id,
        child_user_id=wish.child_user_id,
        name=wish.name,
        description=wish.description,
        emoji=wish.emoji,
        priority=wish.priority,
        status=wish.status,
        has_cost_set=wish.star_coin_cost is not None,
        progress=progress,
        rejection_reason=wish.rejection_reason,
        realized_asset_id=wish.realized_asset_id,
        fulfilled_at=wish.fulfilled_at,
        created_at=wish.created_at,
        updated_at=wish.updated_at,
    )


def _to_parent_response(
    wish: ChildWish, child_display_name: str, db: Session | None = None
) -> ParentWishResponse:
    cost_history: list[ChildWishCostHistoryItem] = []
    if db is not None:
        rows = (
            db.query(ChildWishCostHistory)
            .filter(ChildWishCostHistory.wish_id == wish.id)
            .order_by(ChildWishCostHistory.created_at)
            .all()
        )
        cost_history = [ChildWishCostHistoryItem.model_validate(r) for r in rows]
    return ParentWishResponse(
        id=wish.id,
        family_id=wish.family_id,
        child_user_id=wish.child_user_id,
        child_display_name=child_display_name,
        name=wish.name,
        description=wish.description,
        emoji=wish.emoji,
        priority=wish.priority,
        status=wish.status,
        star_coin_cost=wish.star_coin_cost,
        rejection_reason=wish.rejection_reason,
        realized_asset_id=wish.realized_asset_id,
        fulfilled_at=wish.fulfilled_at,
        created_at=wish.created_at,
        updated_at=wish.updated_at,
        cost_history=cost_history,
    )


def _get_child_name(db: Session, child_user_id: int) -> str:
    child = db.query(User).filter(User.id == child_user_id).first()
    return child.display_name if child else "未知用户"


def _get_wish_for_family(db: Session, wish_id: str, family_id: int) -> ChildWish:
    wish = (
        db.query(ChildWish)
        .filter(
            ChildWish.id == wish_id,
            ChildWish.family_id == family_id,
        )
        .first()
    )
    if not wish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WISH_NOT_FOUND", "message": "心愿不存在"},
        )
    return wish


# ---------------------------------------------------------------------------
# Child endpoints
# ---------------------------------------------------------------------------


def create_child_wish(
    db: Session, user: User, req: ChildWishCreate
) -> ChildWishResponse:
    wish = ChildWish(
        family_id=user.family_id,
        child_user_id=user.id,
        name=req.name,
        description=req.description,
        emoji=req.emoji,
        priority=req.priority,
        status="pending_review",
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    balance = get_balance(db, user.id)
    fire_notification(
        user.family_id,
        {
            "type": "child_wish_submitted",
            "wish_id": wish.id,
            "child_name": user.display_name,
            "wish_name": wish.name,
            "message": f"{user.display_name} 提交了新心愿：{wish.name}",
        },
    )
    return _to_child_response(wish, balance)


def list_child_wishes(db: Session, user: User) -> ChildWishListResponse:
    wishes = (
        db.query(ChildWish)
        .filter(
            ChildWish.family_id == user.family_id,
            ChildWish.child_user_id == user.id,
        )
        .all()
    )
    balance = get_balance(db, user.id)

    result = ChildWishListResponse()
    for w in wishes:
        resp = _to_child_response(w, balance)
        if w.status == "pending_review":
            result.pending_review.append(resp)
        elif w.status == "active":
            result.active.append(resp)
        elif w.status == "redemption_requested":
            result.redemption_requested.append(resp)
        elif w.status == "realized":
            result.realized.append(resp)
        elif w.status == "rejected":
            result.rejected.append(resp)

    result.active.sort(key=lambda r: _PRIORITY_ORDER.get(r.priority, 99))
    return result


def get_child_wish(db: Session, user: User, wish_id: str) -> ChildWishResponse:
    wish = (
        db.query(ChildWish)
        .filter(
            ChildWish.id == wish_id,
            ChildWish.family_id == user.family_id,
            ChildWish.child_user_id == user.id,
        )
        .first()
    )
    if not wish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WISH_NOT_FOUND", "message": "心愿不存在"},
        )
    balance = get_balance(db, user.id)
    return _to_child_response(wish, balance)


def request_redemption(db: Session, user: User, wish_id: str) -> ChildWishResponse:
    wish = (
        db.query(ChildWish)
        .filter(
            ChildWish.id == wish_id,
            ChildWish.family_id == user.family_id,
            ChildWish.child_user_id == user.id,
        )
        .first()
    )
    if not wish:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "WISH_NOT_FOUND", "message": "心愿不存在"},
        )
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_STATUS_INVALID",
                "message": "只有进行中的心愿才能发起兑现申请",
            },
        )
    if wish.star_coin_cost is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WISH_NO_COST", "message": "心愿尚未设定积分门槛"},
        )
    balance = get_balance(db, user.id)
    if balance < wish.star_coin_cost:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_INSUFFICIENT_COINS",
                "message": f"积分不足，当前余额 {balance}，需要 {wish.star_coin_cost}",
            },
        )
    wish.status = "redemption_requested"
    db.commit()
    db.refresh(wish)
    return _to_child_response(wish, balance)


def get_child_stats(db: Session, user: User) -> ChildWishStatsResponse:
    wishes = (
        db.query(ChildWish)
        .filter(
            ChildWish.family_id == user.family_id,
            ChildWish.child_user_id == user.id,
        )
        .all()
    )
    balance = get_balance(db, user.id)

    active = [
        w for w in wishes if w.status == "active" and w.star_coin_cost is not None
    ]
    active.sort(key=lambda w: _PRIORITY_ORDER.get(w.priority, 99))
    realized_count = sum(1 for w in wishes if w.status == "realized")

    remaining = balance
    shortfall = 0
    sim: list[ChildWishStatsSimItem] = []
    for w in active:
        cost = w.star_coin_cost
        if cost is None:
            continue
        covered = remaining >= cost
        progress = min(remaining / cost, 1.0) if cost > 0 else 1.0
        if covered:
            remaining -= cost
        elif w.priority == "high":
            shortfall = max(shortfall, cost - remaining)
        sim.append(
            ChildWishStatsSimItem(
                wish_id=w.id,
                name=w.name,
                priority=w.priority,
                star_coin_cost=cost,
                progress=round(progress, 4),
                covered=covered,
            )
        )

    return ChildWishStatsResponse(
        balance=balance,
        active_wish_count=len(active),
        realized_wish_count=realized_count,
        priority_simulation=sim,
        shortfall_for_high_priority=shortfall,
    )


# ---------------------------------------------------------------------------
# Parent endpoints
# ---------------------------------------------------------------------------


def list_parent_queue(db: Session, user: User) -> list[ParentWishResponse]:
    wishes = (
        db.query(ChildWish)
        .filter(
            ChildWish.family_id == user.family_id,
            ChildWish.status.in_(["pending_review", "redemption_requested"]),
        )
        .all()
    )
    wishes.sort(
        key=lambda w: (0 if w.status == "redemption_requested" else 1, w.created_at)
    )

    # Batch-load child users to avoid N+1 queries
    child_ids = {w.child_user_id for w in wishes}
    child_map: dict[int, str] = {}
    if child_ids:
        children = db.query(User).filter(User.id.in_(child_ids)).all()
        child_map = {c.id: c.display_name for c in children}

    return [
        _to_parent_response(
            w,
            child_map.get(w.child_user_id, "未知用户")
            if w.child_user_id
            else "未知用户",
            db,
        )
        for w in wishes
    ]


def approve_child_wish(
    db: Session, user: User, wish_id: str, req: ApproveChildWishRequest
) -> ParentWishResponse:
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "WISH_PENDING_ONLY", "message": "只有待审核的心愿才能批准"},
        )
    wish.star_coin_cost = req.star_coin_cost
    wish.status = "active"
    db.commit()
    db.refresh(wish)
    fire_notification(
        wish.family_id,
        {
            "type": "child_wish_approved",
            "wish_id": wish.id,
            "wish_name": wish.name,
            "message": f"你的心愿「{wish.name}」已被批准！",
            "target_user_id": wish.child_user_id,
        },
    )
    return _to_parent_response(wish, _get_child_name(db, wish.child_user_id), db)


def reject_child_wish(
    db: Session, user: User, wish_id: str, req: RejectChildWishRequest
) -> ParentWishResponse:
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_REJECT_PENDING_ONLY",
                "message": "只有待审核的心愿才能拒绝",
            },
        )
    wish.status = "rejected"
    wish.rejection_reason = req.rejection_reason
    db.commit()
    db.refresh(wish)
    fire_notification(
        wish.family_id,
        {
            "type": "child_wish_rejected",
            "wish_id": wish.id,
            "wish_name": wish.name,
            "message": f"你的心愿「{wish.name}」未被批准。",
            "target_user_id": wish.child_user_id,
        },
    )
    return _to_parent_response(wish, _get_child_name(db, wish.child_user_id), db)


def update_child_wish_cost(
    db: Session, user: User, wish_id: str, req: UpdateChildWishCostRequest
) -> ParentWishResponse:
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "active":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_ACTIVE_ONLY",
                "message": "只有进行中的心愿才能修改积分",
            },
        )
    if wish.star_coin_cost is not None and req.star_coin_cost >= wish.star_coin_cost:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_COST_DECREASE_ONLY",
                "message": "积分门槛只能降低，不能提高",
            },
        )
    history_entry = ChildWishCostHistory(
        wish_id=wish.id,
        old_cost=wish.star_coin_cost,
        new_cost=req.star_coin_cost,
        changed_by_user_id=user.id,
    )
    db.add(history_entry)
    wish.star_coin_cost = req.star_coin_cost
    db.commit()
    db.refresh(wish)
    return _to_parent_response(wish, _get_child_name(db, wish.child_user_id), db)


def realize_child_wish(
    db: Session, user: User, wish_id: str, req: RealizeChildWishRequest
) -> ParentWishResponse:
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "redemption_requested":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_REDEMPTION_ONLY",
                "message": "只有申请兑现的心愿才能兑现",
            },
        )

    balance = get_balance(db, wish.child_user_id)
    if wish.star_coin_cost is None or balance < wish.star_coin_cost:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_INSUFFICIENT_COINS",
                "message": f"积分不足，无法兑现（余额 {balance}，需要 {wish.star_coin_cost}）",
            },
        )

    category_id = req.category_id
    if not category_id:
        from apps.backend.app.models.category import Category

        default_cat = (
            db.query(Category)
            .filter(
                Category.asset_type == "physical",
                Category.family_id.is_(None),
            )
            .first()
        )
        if default_cat:
            category_id = default_cat.id

    if not category_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="请提供分类",
        )

    try:
        tx = CoinTransaction(
            family_id=user.family_id,
            child_user_id=wish.child_user_id,
            transaction_type="wish_spend",
            amount=-(wish.star_coin_cost or 0),
            ref_id=wish.id,
        )
        db.add(tx)

        asset = Asset(
            family_id=user.family_id,
            user_id=wish.child_user_id,
            category_id=category_id,
            name=wish.name,
            asset_type="physical",
            purchase_price=0,
            current_value=0,
            purchase_date=date.today(),
            status="in_use",
            from_wish_id=wish.id,
        )
        db.add(asset)
        db.flush()

        wish.status = "realized"
        wish.realized_asset_id = asset.id
        wish.fulfilled_at = datetime.now(UTC)
        db.commit()
        db.refresh(wish)

        # Trigger bonus draw opportunity on wish realization (probabilistic)
        try:
            import random

            from apps.backend.app.models.blind_box_config import BlindBoxConfig
            from apps.backend.app.models.bonus_draw import BonusDraw

            config = (
                db.query(BlindBoxConfig).filter_by(family_id=user.family_id).first()
            )
            bonus_prob = config.base_draw_prob if config else 0.30
            if random.random() < bonus_prob:
                bonus = BonusDraw(
                    family_id=wish.family_id,
                    child_user_id=wish.child_user_id,
                    source_wish_id=wish.id,
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                )
                db.add(bonus)
                db.commit()
        except Exception:
            pass  # bonus draw failure never blocks wish realization

        # Check milestones after primary transaction — failure never blocks realize
        from apps.backend.app.services.milestones import check_and_record_milestones

        milestone = check_and_record_milestones(
            db,
            wish.child_user_id,
            wish.family_id,
            {"wish": wish},
        )
        resp = _to_parent_response(wish, _get_child_name(db, wish.child_user_id), db)
        resp.milestone_triggered = milestone
        return resp
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "WISH_REALIZE_FAILED", "message": f"兑现失败: {str(e)}"},
        ) from e


def get_child_asset(db: Session, user: User, asset_id: str):
    """Fetch a child's own asset by ID, filtering out archived assets.

    Args:
        db: SQLAlchemy session
        user: Current child user (must own the asset)
        asset_id: Asset ID to fetch

    Returns:
        ChildAssetResponse with asset details

    Raises:
        HTTPException 404: Asset not found, not owned by user, or archived
    """
    from apps.backend.app.models.asset import Asset
    from apps.backend.app.schemas.asset import ChildAssetResponse

    asset = (
        db.query(Asset)
        .filter(
            Asset.id == asset_id,
            Asset.user_id == user.id,
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
        )
        .first()
    )
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ASSET_NOT_FOUND", "message": "资产不存在"},
        )
    return ChildAssetResponse.model_validate(asset)


def defer_redemption(db: Session, user: User, wish_id: str) -> ParentWishResponse:
    wish = _get_wish_for_family(db, wish_id, user.family_id)
    if wish.status != "redemption_requested":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "WISH_HOLD_PENDING_ONLY",
                "message": "只有申请兑现的心愿才能暂不兑现",
            },
        )
    wish.status = "active"
    db.commit()
    db.refresh(wish)
    return _to_parent_response(wish, _get_child_name(db, wish.child_user_id), db)
