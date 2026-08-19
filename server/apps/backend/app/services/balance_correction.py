"""Balance correction service — post-creation liability adjustments (U3).

NOT used during create_liability (Path 1 decision). Only for manual
corrections after the liability exists.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.balance_correction import BalanceCorrection
from apps.backend.app.models.liability import Liability
from apps.backend.app.models.user import User
from apps.backend.app.services.finance_coach_cache import invalidate_skill


def create_correction(
    db: Session,
    user: User,
    liability_id: str,
    amount: Decimal,
    reason: str | None = None,
) -> BalanceCorrection:
    """Create a balance correction and update the liability's remaining_amount.

    Args:
      amount: signed. Positive = increase debt, negative = decrease.
    """
    liability = (
        db.query(Liability)
        .filter(Liability.id == liability_id, Liability.family_id == user.family_id)
        .first()
    )
    if not liability:
        raise AppError(ErrorCode.LIABILITY_NOT_FOUND)

    correction = BalanceCorrection(
        liability_id=int(liability_id),
        amount=amount,
        reason=reason,
        created_by=user.id,
    )
    db.add(correction)

    # Update remaining_amount: positive correction increases debt.
    liability.remaining_amount = max(Decimal("0"), liability.remaining_amount + amount)
    if liability.remaining_amount == 0:
        liability.is_active = False

    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(db, user.family_id, "dashboard-narrative")
    db.commit()
    db.refresh(correction)
    return correction


def list_corrections(
    db: Session, user: User, liability_id: str,
) -> list[BalanceCorrection]:
    """List all balance corrections for a liability."""
    liability = (
        db.query(Liability)
        .filter(Liability.id == liability_id, Liability.family_id == user.family_id)
        .first()
    )
    if not liability:
        raise AppError(ErrorCode.LIABILITY_NOT_FOUND)

    return (
        db.query(BalanceCorrection)
        .filter(BalanceCorrection.liability_id == int(liability_id))
        .order_by(BalanceCorrection.created_at.desc())
        .all()
    )
