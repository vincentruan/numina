"""Service layer for CoinTransaction ledger."""

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.user import User
from apps.backend.app.schemas.chore import GrantRequest


def get_total_earned(
    db: Session, child_user_id: int, family_id: int | None = None
) -> int:
    """Return total coins ever earned (sum of positive transactions only)."""
    q = db.query(func.sum(CoinTransaction.amount)).filter(
        CoinTransaction.child_user_id == child_user_id,
        CoinTransaction.amount > 0,
    )
    if family_id is not None:
        q = q.filter(CoinTransaction.family_id == family_id)
    result = q.scalar()
    return result or 0


def get_balance(db: Session, child_user_id: int) -> int:
    """Return current coin balance for a child. Always returns an integer."""
    result = (
        db.query(func.sum(CoinTransaction.amount))
        .filter(CoinTransaction.child_user_id == child_user_id)
        .scalar()
    )
    return result or 0


def list_transactions(
    db: Session, child_user_id: int, family_id: int
) -> list[CoinTransaction]:
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


def gift_coins(
    db: Session,
    sender: User,
    to_child_id: str,
    amount: int,
    emoji_reason: str | None,
) -> tuple[CoinTransaction, CoinTransaction, str]:
    """Transfer coins from one child to a sibling in the same family.

    Returns (debit_tx, credit_tx, recipient_display_name).
    """
    if amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "赠送数量必须大于0")

    # Validate recipient is a child in the same family
    recipient = (
        db.query(User)
        .filter(
            User.id == to_child_id,
            User.family_id == sender.family_id,
            User.role == "child",
            User.id != sender.id,
        )
        .first()
    )
    if not recipient:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "兄弟姐妹不存在或不属于该家庭")

    # Lock sender's transactions to prevent concurrent double-spend
    db.query(CoinTransaction).filter(
        CoinTransaction.child_user_id == sender.id
    ).with_for_update().all()

    # Check sender balance (after acquiring lock)
    balance = get_balance(db, sender.id)
    if balance < amount:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "星星币余额不足")

    narrative = emoji_reason or "🎁"

    debit = CoinTransaction(
        family_id=sender.family_id,
        child_user_id=sender.id,
        amount=-amount,
        transaction_type="gift_sent",
        ref_id=None,
        narrative=f"赠送给 {recipient.display_name}",
        narrative_emoji=narrative,
    )
    credit = CoinTransaction(
        family_id=sender.family_id,
        child_user_id=to_child_id,
        amount=amount,
        transaction_type="gift_received",
        ref_id=None,
        narrative=f"来自 {sender.display_name} 的礼物",
        narrative_emoji=narrative,
    )
    db.add(debit)
    db.add(credit)
    db.commit()
    db.refresh(debit)
    db.refresh(credit)
    return debit, credit, recipient.display_name


def write_parent_grant(
    db: Session, parent_user: User, req: GrantRequest
) -> CoinTransaction:
    """Write a parent_grant transaction directly (no approval queue)."""
    # Validate child belongs to same family
    child = (
        db.query(User)
        .filter(
            User.id == req.child_user_id,
            User.family_id == parent_user.family_id,
            User.role == "child",
        )
        .first()
    )
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
