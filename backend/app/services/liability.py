from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.liability import Liability
from app.models.user import User
from app.schemas.liability import LiabilityCreate, LiabilityUpdate


def list_liabilities(db: Session, user: User) -> list[Liability]:
    return (
        db.query(Liability)
        .filter(Liability.family_id == user.family_id, Liability.is_active == True)
        .order_by(Liability.created_at.desc())
        .all()
    )


def get_liability(db: Session, user: User, liability_id: str) -> Liability:
    liability = (
        db.query(Liability)
        .filter(Liability.id == liability_id, Liability.family_id == user.family_id)
        .first()
    )
    if not liability:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="负债不存在")
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
    liability = get_liability(db, user, liability_id)
    liability.remaining_amount = max(0, liability.remaining_amount - amount)
    if liability.remaining_amount == 0:
        liability.is_active = False
    db.commit()
    db.refresh(liability)
    return liability
