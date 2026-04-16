"""Service layer for CoinTransaction ledger."""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.coin_transaction import CoinTransaction
from app.models.user import User
from app.schemas.chore import GrantRequest


def get_balance(db: Session, child_user_id: str) -> int:
    """Return current coin balance for a child. Always returns an integer."""
    result = db.query(func.sum(CoinTransaction.amount)).filter(
        CoinTransaction.child_user_id == child_user_id
    ).scalar()
    return result or 0


def list_transactions(db: Session, child_user_id: str, family_id: str) -> list[CoinTransaction]:
    """Return all transactions for a child, newest first."""
    return (
        db.query(CoinTransaction)
        .filter(
            CoinTransaction.child_user_id == child_user_id,
            CoinTransaction.family_id == family_id,
        )
        .order_by(CoinTransaction.created_at.desc())
        .all()
    )


def write_parent_grant(db: Session, parent_user: User, req: GrantRequest) -> CoinTransaction:
    """Write a parent_grant transaction directly (no approval queue)."""
    # Validate child belongs to same family
    child = db.query(User).filter(
        User.id == req.child_user_id,
        User.family_id == parent_user.family_id,
        User.role == "child",
    ).first()
    if not child:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "孩子不存在或不属于该家庭")

    tx = CoinTransaction(
        family_id=parent_user.family_id,
        child_user_id=req.child_user_id,
        amount=req.amount,
        transaction_type="parent_grant",
        ref_id=None,  # no unique constraint for parent_grant (multiple grants allowed)
        narrative=req.reason,
        narrative_emoji="🎁",
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx
