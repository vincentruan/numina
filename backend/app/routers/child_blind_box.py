from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.blind_box_draw import BlindBoxDraw
from app.models.blind_box_gift import BlindBoxGift
from app.models.bonus_draw import BonusDraw
from app.models.chore import ChoreInstance
from app.models.user import User
from app.routers.blind_box import _draw_to_response, _get_or_create_config
from app.schemas.blind_box import BlindBoxDrawResponse, BonusDrawResponse, DrawRequest
from app.services.blind_box import pick_gift, should_upgrade_surprise

router = APIRouter(prefix="/child/blind-box", tags=["child-blind-box"])


@router.post("/draw", response_model=BlindBoxDrawResponse, status_code=201)
def child_draw(
    body: DrawRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_or_create_config(current_user.family_id, db)
    if not config.enabled:
        raise AppError(ErrorCode.BLIND_BOX_DISABLED)

    # Step 1: 校验 ChoreInstance（已批准、属于当前孩子、未消耗）
    instances = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.id.in_(body.chore_instance_ids),
            ChoreInstance.child_user_id == current_user.id,
            ChoreInstance.status == "approved",
            ChoreInstance.consumed_at.is_(None),
        )
        .all()
    )
    if len(instances) != len(body.chore_instance_ids):
        raise AppError(ErrorCode.BLIND_BOX_INVALID_CHORE)

    # Step 2: 计算金币总额
    coins_total = sum(inst.coin_reward for inst in instances)
    if coins_total <= 0:
        raise AppError(ErrorCode.BLIND_BOX_INSUFFICIENT_COINS)

    try:
        # Step 3: 标记 consumed_at
        now = datetime.now(UTC)
        for inst in instances:
            inst.consumed_at = now

        # Step 4: 执行加权抽奖
        gifts = db.query(BlindBoxGift).filter_by(family_id=current_user.family_id, is_active=True).all()
        if not gifts:
            raise AppError(ErrorCode.BLIND_BOX_GIFT_POOL_EMPTY)

        context = {"is_parent_bday": False, "is_sibling_bday": False}
        is_surprise = should_upgrade_surprise(config, context)
        pool = [g for g in gifts if g.value_score >= 7] if is_surprise else gifts
        chosen = pick_gift(pool if pool else gifts, config)

        # Step 5: 写入 BlindBoxDraw 记录
        draw = BlindBoxDraw(
            family_id=current_user.family_id,
            child_user_id=current_user.id,
            coins_spent=coins_total,
            gift_id=chosen.id,
            is_surprise=is_surprise,
            is_bonus=False,
            status="pending_fulfillment",
        )
        db.add(draw)

        # Step 6: 原子提交
        db.commit()
        db.refresh(draw)
    except AppError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR) from exc

    return _draw_to_response(draw)


@router.get("/draws", response_model=list[BlindBoxDrawResponse])
def child_list_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draws = (
        db.query(BlindBoxDraw)
        .filter_by(family_id=current_user.family_id, child_user_id=current_user.id)
        .order_by(BlindBoxDraw.draw_at.desc())
        .all()
    )
    return [_draw_to_response(d) for d in draws]


@router.get("/bonus-draws", response_model=list[BonusDrawResponse])
def child_list_bonus_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(BonusDraw)
        .filter_by(family_id=current_user.family_id, child_user_id=current_user.id)
        .all()
    )


@router.post("/bonus-draws/{bonus_id}/use", response_model=BlindBoxDrawResponse, status_code=201)
def child_use_bonus_draw(
    bonus_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    bonus = db.query(BonusDraw).filter_by(
        id=bonus_id,
        child_user_id=current_user.id,
        family_id=current_user.family_id,
        status="available",
    ).first()
    if not bonus:
        raise AppError(ErrorCode.BLIND_BOX_DRAW_NOT_FOUND)
    if bonus.expires_at < datetime.now(UTC):
        bonus.status = "expired"
        db.commit()
        raise AppError(ErrorCode.BLIND_BOX_BONUS_EXPIRED)

    config = _get_or_create_config(current_user.family_id, db)
    gifts = db.query(BlindBoxGift).filter_by(family_id=current_user.family_id, is_active=True).all()
    if not gifts:
        raise AppError(ErrorCode.BLIND_BOX_GIFT_POOL_EMPTY)

    try:
        context = {"is_parent_bday": False, "is_sibling_bday": False}
        is_surprise = should_upgrade_surprise(config, context)
        pool = [g for g in gifts if g.value_score >= 7] if is_surprise else gifts
        chosen = pick_gift(pool if pool else gifts, config)

        draw = BlindBoxDraw(
            family_id=current_user.family_id,
            child_user_id=current_user.id,
            coins_spent=0,
            gift_id=chosen.id,
            is_surprise=is_surprise,
            is_bonus=True,
            status="pending_fulfillment",
        )
        db.add(draw)
        db.flush()

        bonus.status = "used"
        bonus.used_draw_id = draw.id
        db.commit()
        db.refresh(draw)
    except AppError:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR) from exc

    return _draw_to_response(draw)
