from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from apps.backend.app.auth.deps import get_current_user
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.blind_box_config import BlindBoxConfig
from apps.backend.app.models.blind_box_draw import BlindBoxDraw
from apps.backend.app.models.blind_box_gift import BlindBoxGift
from apps.backend.app.models.bonus_draw import BonusDraw
from apps.backend.app.models.child_wish import ChildWish
from apps.backend.app.models.user import User
from apps.backend.app.schemas.blind_box import (
    BlindBoxConfigResponse,
    BlindBoxConfigUpdate,
    BlindBoxDrawResponse,
    BlindBoxGiftCreate,
    BlindBoxGiftResponse,
    BlindBoxGiftUpdate,
    BonusDrawCreate,
    BonusDrawResponse,
)

router = APIRouter(prefix="/blind-box", tags=["blind-box"])


def _get_or_create_config(family_id: int, db: Session) -> BlindBoxConfig:
    config = db.query(BlindBoxConfig).filter_by(family_id=family_id).first()
    if not config:
        config = BlindBoxConfig(family_id=family_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _draw_to_response(draw: BlindBoxDraw) -> BlindBoxDrawResponse:
    """Convert a BlindBoxDraw ORM object (with .gift loaded) to a response schema."""
    gift = draw.gift
    return BlindBoxDrawResponse(
        id=draw.id,
        family_id=draw.family_id,
        child_user_id=draw.child_user_id,
        coins_spent=draw.coins_spent,
        gift_id=draw.gift_id,
        is_surprise=draw.is_surprise,
        is_bonus=draw.is_bonus,
        status=draw.status,
        draw_at=draw.draw_at,
        fulfilled_at=draw.fulfilled_at,
        gift_name=gift.name if gift else "",
        gift_emoji=gift.emoji if gift else None,
    )


@router.get("/gifts", response_model=list[BlindBoxGiftResponse])
def list_gifts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(BlindBoxGift)
        .filter_by(family_id=current_user.family_id, is_active=True)
        .all()
    )


@router.post("/gifts", response_model=BlindBoxGiftResponse, status_code=201)
def create_gift(
    body: BlindBoxGiftCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # 重复名称检查
    duplicate = db.query(BlindBoxGift).filter_by(
        family_id=current_user.family_id,
        name=body.name,
        is_active=True,
    ).first()

    gift = BlindBoxGift(
        **body.model_dump(),
        family_id=current_user.family_id,
        created_by=current_user.id,
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)

    response = BlindBoxGiftResponse.model_validate(gift)
    if duplicate:
        response.warning = f"礼物池中已有同名礼物「{duplicate.name}」，请确认是否重复添加"
    return response


@router.put("/gifts/{gift_id}", response_model=BlindBoxGiftResponse)
def update_gift(
    gift_id: int,
    body: BlindBoxGiftUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift = db.query(BlindBoxGift).filter_by(id=gift_id, family_id=current_user.family_id).first()
    if not gift:
        raise AppError(ErrorCode.BLIND_BOX_GIFT_NOT_FOUND)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(gift, k, v)
    db.commit()
    db.refresh(gift)
    return gift


@router.delete("/gifts/{gift_id}", status_code=204)
def delete_gift(
    gift_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gift = db.query(BlindBoxGift).filter_by(id=gift_id, family_id=current_user.family_id).first()
    if not gift:
        raise AppError(ErrorCode.BLIND_BOX_GIFT_NOT_FOUND)
    gift.is_active = False
    db.commit()


@router.get("/draws", response_model=list[BlindBoxDrawResponse])
def list_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draws = (
        db.query(BlindBoxDraw)
        .filter_by(family_id=current_user.family_id)
        .order_by(BlindBoxDraw.draw_at.desc())
        .all()
    )
    return [_draw_to_response(d) for d in draws]


@router.put("/draws/{draw_id}/fulfill", response_model=BlindBoxDrawResponse)
def fulfill_draw(
    draw_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    draw = (
        db.query(BlindBoxDraw)
        .options(joinedload(BlindBoxDraw.gift))
        .filter_by(id=draw_id, family_id=current_user.family_id)
        .first()
    )
    if not draw:
        raise AppError(ErrorCode.BLIND_BOX_DRAW_NOT_FOUND)
    draw.status = "fulfilled"
    draw.fulfilled_at = datetime.now(UTC)
    db.commit()
    db.refresh(draw)
    return _draw_to_response(draw)


@router.get("/config", response_model=BlindBoxConfigResponse)
def get_config(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _get_or_create_config(current_user.family_id, db)


@router.put("/config", response_model=BlindBoxConfigResponse)
def update_config(
    body: BlindBoxConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    config = _get_or_create_config(current_user.family_id, db)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(config, k, v)
    db.commit()
    db.refresh(config)
    return config


@router.get("/bonus-draws", response_model=list[BonusDrawResponse])
def list_bonus_draws(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return db.query(BonusDraw).filter_by(family_id=current_user.family_id).all()


@router.post("/bonus-draws", response_model=BonusDrawResponse, status_code=201)
def create_bonus_draw(
    req: BonusDrawCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Grant a bonus draw to a child in the same family."""
    child = db.query(User).filter_by(
        id=req.child_user_id,
        family_id=current_user.family_id,
        role="child",
        is_active=True,
    ).first()
    if not child:
        raise AppError(ErrorCode.CHILD_NOT_FOUND)

    bonus = BonusDraw(
        family_id=current_user.family_id,
        child_user_id=req.child_user_id,
        expires_at=req.expires_at,
        status="available",
    )
    db.add(bonus)
    db.commit()
    db.refresh(bonus)
    return bonus


@router.post("/gifts/from-wish/{wish_id}", response_model=BlindBoxGiftResponse, status_code=201)
def create_gift_from_wish(
    wish_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    wish = db.query(ChildWish).filter_by(id=wish_id, family_id=current_user.family_id).first()
    if not wish:
        raise AppError(ErrorCode.NOT_FOUND)

    existing = db.query(BlindBoxGift).filter_by(
        source_wish_id=wish_id, family_id=current_user.family_id
    ).first()
    if existing:
        raise AppError(ErrorCode.BLIND_BOX_WISH_CONFLICT)

    # ChildWish has no estimated_price; use star_coin_cost as proxy (1 coin ≈ 1 yuan)
    price_proxy = getattr(wish, "star_coin_cost", None) or 50
    # Map star_coin_cost to value_score 1-10:
    # ≤50 → 1, ≤100 → 2, ≤200 → 3, ≤400 → 5, ≤800 → 7, >800 → 9
    thresholds = [(50, 1), (100, 2), (200, 3), (400, 5), (800, 7)]
    value_score = next((s for t, s in thresholds if price_proxy <= t), 9)
    gift = BlindBoxGift(
        family_id=current_user.family_id,
        name=wish.name,
        description=wish.description,
        emoji=wish.emoji,
        value_score=value_score,
        source_wish_id=wish.id,
        created_by=current_user.id,
    )
    db.add(gift)
    db.commit()
    db.refresh(gift)
    return gift
