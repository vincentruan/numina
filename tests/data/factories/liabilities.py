"""负债工厂 — 幂等创建，按 (user_id, name) 查重。"""

from datetime import date

from sqlalchemy.orm import Session

from models import Liability
from factories.users import next_id


class LiabilityFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        user_id: int,
        family_id: int,
        name: str,
        category: str,
        original_amount: float,
        remaining_amount: float,
        currency: str = "CNY",
        monthly_payment: float | None = None,
        interest_rate: float | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        institution: str | None = None,
        linked_asset_id: int | None = None,
        notes: str | None = None,
    ) -> tuple[Liability, bool]:
        existing = (
            db.query(Liability)
            .filter(Liability.user_id == user_id, Liability.name == name, Liability.is_active == True)  # noqa: E712
            .first()
        )
        if existing:
            return existing, False

        liability = Liability(
            id=next_id(),
            user_id=user_id,
            family_id=family_id,
            category=category,
            name=name,
            original_amount=original_amount,
            remaining_amount=remaining_amount,
            currency=currency,
            monthly_payment=monthly_payment,
            interest_rate=interest_rate,
            start_date=start_date,
            end_date=end_date,
            institution=institution,
            linked_asset_id=linked_asset_id,
            notes=notes,
        )
        db.add(liability)
        db.flush()
        return liability, True
