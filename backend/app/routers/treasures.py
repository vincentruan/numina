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

    return [
        TreasureItem(
            id=asset.id,
            name=asset.name,
            image_url=asset.image_url,
            purchase_date=asset.purchase_date,
            coins_spent=abs(tx.amount) if tx else None,
        )
        for asset, _wish, tx in rows
    ]
