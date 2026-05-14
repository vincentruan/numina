from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.schemas.liability import LiabilityCreate, LiabilityUpdate


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
        monthly_payment=req.monthly_payment,
        interest_rate=req.interest_rate,
        start_date=req.start_date,
        end_date=req.end_date,
        institution=req.institution,
        linked_asset_id=req.linked_asset_id,
        notes=req.notes,
    )
    db.add(liability)
    db.commit()
    db.refresh(liability)
    return liability


def update_liability(db: Session, user: User, liability_id: str, req: LiabilityUpdate) -> Liability:
    liability = get_liability(db, user, liability_id)
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(liability, key, value)
    db.commit()
    db.refresh(liability)
    return liability


def delete_liability(db: Session, user: User, liability_id: str) -> None:
    liability = get_liability(db, user, liability_id)
    db.delete(liability)
    db.commit()


def record_payment(db: Session, user: User, liability_id: str, amount: float) -> Liability:
    from apps.backend.app.models.payment_record import PaymentRecord
    liability = get_liability(db, user, liability_id)
    liability.remaining_amount = max(0, liability.remaining_amount - amount)
    if liability.remaining_amount == 0:
        liability.is_active = False
    record = PaymentRecord(liability_id=liability_id, amount=amount)
    db.add(record)
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
