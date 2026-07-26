"""W1 wish savings CRUD + invariant (Plan B T2).

INVARIANT: wish_savings_log is the source of truth; wish.saved_amount is a
derived cache. record_savings/delete_savings update saved_amount in the SAME
transaction as the log write, with SELECT ... FOR UPDATE on the wish row to
serialize concurrent savings writes. recompute_saved_amount() reconciles (CI
asserts saved_amount == recompute_saved_amount(wish_id)).

AUTHZ: reuse wish_service.get_wish (family filter + NOT_FOUND). POST: any family
adult may record (shared contribution). DELETE: only log.user_id == caller.id or
the family owner (mirror wish_service.update_wish owner check, broadened to
family owner since savings are a shared family resource).
"""

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from apps.backend.app.models.wish_savings_log import WishSavingsLog
from apps.backend.app.services.finance_coach_cache import invalidate_skill
from apps.backend.app.services.wish import get_wish


def record_savings(
    db: Session,
    user: User,
    wish_id: str,
    amount: Decimal,
    log_date: date | None = None,
    note: str | None = None,
) -> WishSavingsLog:
    """Write a savings log + update saved_amount in-transaction. Returns the log.

    SELECT ... FOR UPDATE locks the wish row so concurrent deposits serialize
    (prevents lost-update on saved_amount). Commits.
    """
    log_date = log_date or datetime.now(UTC).date()
    # Lock the wish row for the duration of this transaction.
    wish = (
        db.query(Wish)
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .with_for_update()
        .first()
    )
    if not wish:
        raise AppError(ErrorCode.NOT_FOUND)

    log = WishSavingsLog(
        wish_id=int(wish_id),
        family_id=user.family_id,
        user_id=user.id,
        amount=amount,
        log_date=log_date,
        note=note,
    )
    db.add(log)
    wish.saved_amount = (wish.saved_amount or Decimal("0")) + amount
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(
        db, user.family_id, "wish_advice"
    )  # W4 (Plan B T7): savings change the wish fingerprint
    db.commit()
    db.refresh(log)
    db.refresh(wish)
    return log


def list_savings(
    db: Session,
    user: User,
    wish_id: str,
    page: int = 1,
    size: int = 50,
) -> Sequence[WishSavingsLog]:
    """List a wish's savings logs, newest log_date first (family-scoped)."""
    # Family-scope via get_wish (raises NOT_FOUND if the wish isn't in the family).
    get_wish(db, user, int(wish_id))
    offset = (page - 1) * size
    return (
        db.query(WishSavingsLog)
        .filter(WishSavingsLog.wish_id == int(wish_id))
        .order_by(WishSavingsLog.log_date.desc(), WishSavingsLog.created_at.desc())
        .offset(offset)
        .limit(size)
        .all()
    )


def delete_savings(
    db: Session,
    user: User,
    wish_id: str,
    log_id: str,
) -> None:
    """Delete a savings log + reverse its amount from saved_amount in-transaction.

    AUTHZ: the recorder (log.user_id == caller.id) or the family owner. A
    different family adult is FORBIDDEN (savings deletion is destructive — it
    reverses another member's recorded deposit).
    """
    wish = (
        db.query(Wish)
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .with_for_update()
        .first()
    )
    if not wish:
        raise AppError(ErrorCode.NOT_FOUND)
    log = (
        db.query(WishSavingsLog)
        .filter(WishSavingsLog.id == log_id, WishSavingsLog.wish_id == int(wish_id))
        .first()
    )
    if not log:
        raise AppError(ErrorCode.NOT_FOUND)
    # AUTHZ: recorder or family owner.
    is_owner = getattr(user, "role", None) == "owner"
    if log.user_id != user.id and not is_owner:
        raise AppError(ErrorCode.FORBIDDEN)

    db.delete(log)
    wish.saved_amount = (wish.saved_amount or Decimal("0")) - log.amount
    invalidate_skill(db, user.family_id, "finance_coach")
    invalidate_skill(
        db, user.family_id, "wish_advice"
    )  # W4 (Plan B T7): savings change the wish fingerprint
    db.commit()


def recompute_saved_amount(db: Session, wish_id: int | str) -> Decimal:
    """Reconciliation helper: saved_amount := SUM(log.amount). Does NOT commit
    (caller commits) — used by CI canary + admin fix + bulk-import backfill.

    spec §2.2: any future write path touching savings must either maintain the
    counter in-transaction or call this.
    """
    total = db.execute(
        select(func.coalesce(func.sum(WishSavingsLog.amount), Decimal("0"))).where(
            WishSavingsLog.wish_id == int(wish_id)
        )
    ).scalar_one()
    wish = db.query(Wish).filter(Wish.id == int(wish_id)).first()
    if wish is not None:
        wish.saved_amount = Decimal(total)
    return Decimal(total)
