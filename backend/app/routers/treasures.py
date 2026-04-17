from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.deps import get_current_child_user
from app.database import get_db
from app.models.asset import Asset
from app.models.child_wish import ChildWish
from app.models.coin_transaction import CoinTransaction
from app.models.user import User
from app.schemas.treasure import TreasureItem

router = APIRouter(tags=["treasures"])


@router.get("/child/treasures", response_model=list[TreasureItem])
def list_treasures(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    """获取儿童用户的宝贝画廊（通过心愿兑现的资产）"""
    # Single query: assets LEFT JOIN wishes LEFT JOIN coin_transactions
    # Use DISTINCT ON asset.id to prevent duplicate rows when a wish has
    # multiple wish_spend transactions (e.g. due to retries).
    rows = (
        db.query(Asset, ChildWish, CoinTransaction)
        .outerjoin(ChildWish, ChildWish.realized_asset_id == Asset.id)
        .outerjoin(
            CoinTransaction,
            (CoinTransaction.ref_id == ChildWish.id)
            & (CoinTransaction.transaction_type == "wish_spend"),
        )
        .filter(Asset.user_id == user.id)
        .order_by(desc(Asset.purchase_date))
        .all()
    )

    # Deduplicate by asset id — keep first occurrence (largest coins_spent wins
    # if there are multiple wish_spend rows, but in practice there should be one).
    seen: set[str] = set()
    result: list[TreasureItem] = []
    for asset, _wish, tx in rows:
        if asset.id in seen:
            continue
        seen.add(asset.id)
        result.append(TreasureItem(
            id=asset.id,
            name=asset.name,
            image_url=asset.image_url,
            purchase_date=asset.purchase_date,
            coins_spent=abs(tx.amount) if tx else None,
        ))
    return result
