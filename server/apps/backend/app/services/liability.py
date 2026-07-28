from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.schemas.liability import LiabilityCreate, LiabilityUpdate
from apps.backend.app.services.finance_coach_cache import invalidate_skill


def list_liabilities(db: Session, user: User, is_active: bool | None = None) -> list[Liability]:
    query = db.query(Liability).filter(Liability.family_id == user.family_id)
    if is_active is not None:
        query = query.filter(Liability.is_active == is_active)
    return query.order_by(Liability.created_at.desc()).all()


def get_liability(db: Session, user: User, liability_id: str) -> Liability:
    liability = (
        db.query(Liability)
        .filter(Liability.id == liability_id, Liability.family_id == user.family_id)
        .first()
    )
    if not liability:
        raise AppError(ErrorCode.LIABILITY_NOT_FOUND)
    return liability


def create_liability(db: Session, user: User, req: LiabilityCreate) -> Liability:
    liability = Liability(
        user_id=user.id,
        family_id=user.family_id,
        category=req.category,
        name=req.name,
        original_amount=req.original_amount,
        remaining_amount=req.remaining_amount,
        currency=req.currency,
        monthly_payment=req.monthly_payment,
        interest_rate=req.interest_rate,
        start_date=req.start_date,
        end_date=req.end_date,
        institution=req.institution,
        linked_asset_id=req.linked_asset_id,
        notes=req.notes,
    )
    db.add(liability)
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(db, user.family_id, "dashboard-narrative")
    db.commit()
    db.refresh(liability)
    return liability


def update_liability(db: Session, user: User, liability_id: str, req: LiabilityUpdate) -> Liability:
    liability = get_liability(db, user, liability_id)
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(liability, key, value)
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(db, user.family_id, "dashboard-narrative")
    db.commit()
    db.refresh(liability)
    return liability


def delete_liability(db: Session, user: User, liability_id: str) -> None:
    liability = get_liability(db, user, liability_id)
    db.delete(liability)
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(db, user.family_id, "dashboard-narrative")
    db.commit()


def record_payment(db: Session, user: User, liability_id: str, amount: Decimal) -> Liability:
    from apps.backend.app.models.payment_record import PaymentRecord
    liability = get_liability(db, user, liability_id)
    liability.remaining_amount = max(Decimal("0"), liability.remaining_amount - amount)
    if liability.remaining_amount == 0:
        liability.is_active = False
    record = PaymentRecord(liability_id=liability_id, amount=amount)
    db.add(record)
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(db, user.family_id, "dashboard-narrative")
    db.commit()
    db.refresh(liability)
    return liability


def get_payments(db: Session, user: User, liability_id: str) -> list:
    from apps.backend.app.models.payment_record import PaymentRecord
    get_liability(db, user, liability_id)  # Verify access
    return (
        db.query(PaymentRecord)
        .filter(PaymentRecord.liability_id == liability_id)
        .order_by(PaymentRecord.paid_at.desc())
        .all()
    )


def list_liabilities_for_family(
    db: Session,
    family_id: str,
    user: User | None = None,
    limit: int = 20,
) -> list[dict]:
    """List liabilities for a family.

    Multi-currency: when *user* is provided, ``remaining_amount`` is converted
    to the user's ``default_currency`` and the original currency is preserved
    in ``original_currency``.
    """
    from apps.backend.app.models.liability import Liability
    from packages.domain.exchange_rate.service import ExchangeRateService

    rows = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .limit(limit)
        .all()
    )

    dc = (user.default_currency or "CNY") if user else None

    result = []
    for liab in rows:
        raw_amount = str(liab.remaining_amount or Decimal("0"))
        entry: dict[str, Any] = {
            "id": str(liab.id),
            "name": liab.name,
            "category": liab.category,
            "remaining_amount": raw_amount,
            "currency": liab.currency,
        }
        if dc and liab.currency != dc:
            rate_from, _ = ExchangeRateService.get_rate(liab.currency, db)
            rate_to, _ = ExchangeRateService.get_rate(dc, db)
            if rate_from is not None and rate_to is not None:
                converted = ExchangeRateService.convert(
                    float(liab.remaining_amount or 0), liab.currency, dc, db
                )
                entry["remaining_amount"] = str(converted)
                entry["original_currency"] = liab.currency
                entry["currency"] = dc
        result.append(entry)
    return result
