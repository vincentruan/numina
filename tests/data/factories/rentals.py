"""租约工厂 — 幂等创建，按 (user_id, role, monthly_rent, start_date) 查重。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from models import RentalContract
from factories.users import next_id


class RentalContractFactory:
    @staticmethod
    def get_or_create(
        db: Session,
        *,
        user_id: int,
        family_id: int,
        role: str,
        monthly_rent: float,
        deposit: float = 0,
        start_date: date | None = None,
        end_date: date | None = None,
        linked_asset_id: int | None = None,
        counterparty: str | None = None,
        notes: str | None = None,
        currency: str = "CNY",
        is_active: bool = True,
    ) -> tuple[RentalContract, bool]:
        existing = (
            db.query(RentalContract)
            .filter(
                RentalContract.user_id == user_id,
                RentalContract.role == role,
                RentalContract.monthly_rent == monthly_rent,
                RentalContract.start_date == start_date,
                RentalContract.is_active == is_active,
            )
            .first()
        )
        if existing:
            return existing, False

        contract = RentalContract(
            id=next_id(),
            user_id=user_id,
            family_id=family_id,
            role=role,
            monthly_rent=monthly_rent,
            deposit=deposit,
            start_date=start_date or date.today(),
            end_date=end_date,
            linked_asset_id=linked_asset_id,
            counterparty=counterparty,
            notes=notes,
            currency=currency,
            is_active=is_active,
        )
        db.add(contract)
        db.flush()
        return contract, True
