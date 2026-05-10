"""心愿工厂 — 幂等创建，按 (user_id, name) 查重。"""

from sqlalchemy.orm import Session

from models import ChildWish, Wish
from factories.users import next_id


class WishFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        user_id: int,
        family_id: int,
        name: str,
        expected_price: float | None = None,
        priority: str = "medium",
        status: str = "pending",
        currency: str = "CNY",
        description: str | None = None,
        category_id: int | None = None,
        converts_to_asset: bool = True,
    ) -> tuple[Wish, bool]:
        existing = (
            db.query(Wish)
            .filter(Wish.user_id == user_id, Wish.name == name)
            .first()
        )
        if existing:
            return existing, False

        wish = Wish(
            id=next_id(),
            family_id=family_id,
            user_id=user_id,
            name=name,
            description=description,
            expected_price=expected_price,
            priority=priority,
            status=status,
            currency=currency,
            category_id=category_id,
            converts_to_asset=converts_to_asset,
        )
        db.add(wish)
        db.flush()
        return wish, True


class ChildWishFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        child_user_id: int,
        family_id: int,
        name: str,
        emoji: str | None = None,
        priority: str = "medium",
        status: str = "pending_review",
        star_coin_cost: int | None = None,
        description: str | None = None,
    ) -> tuple[ChildWish, bool]:
        existing = (
            db.query(ChildWish)
            .filter(ChildWish.child_user_id == child_user_id, ChildWish.name == name)
            .first()
        )
        if existing:
            return existing, False

        wish = ChildWish(
            id=next_id(),
            family_id=family_id,
            child_user_id=child_user_id,
            name=name,
            description=description,
            emoji=emoji,
            priority=priority,
            status=status,
            star_coin_cost=star_coin_cost,
        )
        db.add(wish)
        db.flush()
        return wish, True
