"""Expense ledger — double-entry bookkeeping for travel expenses."""

from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.expense_entry import ExpenseEntryCreate
from packages.core.snowflake import next_id
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.split_group import SplitGroup, SplitParticipant
from packages.db.models.trip import Trip
from packages.domain.exchange_rate.service import ExchangeRateService


def create_expense(
    db: Session,
    family_id: int,
    user_id: int,
    req: ExpenseEntryCreate,
) -> dict[str, ExpenseEntry]:
    """Create a debit/credit pair for a single expense.

    Returns {"debit": entry, "credit": entry}.
    """
    # Convert to CNY
    converted = ExchangeRateService.convert(float(req.amount), req.currency, "CNY", db)
    amount_cny = Decimal(str(converted))

    transfer_id = next_id()

    common = dict(
        family_id=family_id,
        transfer_id=transfer_id,
        ref_id=req.ref_id,
        ref_type=req.ref_type,
        amount=req.amount,
        currency=req.currency,
        amount_cny=amount_cny,
        expense_date=req.expense_date,
        description=req.description,
        receipt_image_url=req.receipt_image_url,
        split_type=req.split_type,
        user_id=user_id,
    )

    debit = ExpenseEntry(
        **common,
        leg_type="debit",
        category_id=req.category_id,
    )
    credit = ExpenseEntry(
        **common,
        leg_type="credit",
    )

    db.add(debit)
    db.add(credit)

    # Update trip actual_spend if linked to a trip
    if req.ref_type == "trip" and req.ref_id is not None:
        trip = (
            db.query(Trip)
            .filter(Trip.id == req.ref_id, Trip.family_id == family_id)
            .with_for_update()
            .first()
        )
        if trip:
            spend_amount = _family_proportional_share(db, trip.id, amount_cny)
            trip.actual_spend = (trip.actual_spend or Decimal("0")) + spend_amount

    db.commit()
    db.refresh(debit)
    db.refresh(credit)

    return {"debit": debit, "credit": credit}


def delete_expense(
    db: Session,
    entry_id: int,
    family_id: int,
    user_id: int,
) -> None:
    """Reverse an expense by creating offsetting entries."""
    entry = (
        db.query(ExpenseEntry)
        .filter(
            ExpenseEntry.id == entry_id,
            ExpenseEntry.family_id == family_id,
        )
        .first()
    )
    if not entry:
        raise AppError(ErrorCode.EXPENSE_NOT_FOUND)

    # Find the paired leg (validate it exists)
    pair = (
        db.query(ExpenseEntry)
        .filter(
            ExpenseEntry.transfer_id == entry.transfer_id,
            ExpenseEntry.id != entry_id,
        )
        .first()
    )
    if not pair:
        raise AppError(ErrorCode.EXPENSE_NOT_FOUND)

    # Create offsetting entries (reverse)
    reverse_transfer_id = next_id()

    reverse_debit = ExpenseEntry(
        family_id=family_id,
        transfer_id=reverse_transfer_id,
        leg_type="debit",
        ref_id=entry.ref_id,
        ref_type=entry.ref_type,
        category_id=entry.category_id,
        amount=-entry.amount,
        currency=entry.currency,
        amount_cny=-entry.amount_cny,
        expense_date=entry.expense_date,
        description=f"冲销: {entry.description or ''}".strip(),
        user_id=user_id,
    )
    reverse_credit = ExpenseEntry(
        family_id=family_id,
        transfer_id=reverse_transfer_id,
        leg_type="credit",
        ref_id=entry.ref_id,
        ref_type=entry.ref_type,
        amount=-entry.amount,
        currency=entry.currency,
        amount_cny=-entry.amount_cny,
        expense_date=entry.expense_date,
        description=f"冲销: {entry.description or ''}".strip(),
        user_id=user_id,
    )

    db.add(reverse_debit)
    db.add(reverse_credit)

    # Revert trip actual_spend if linked
    if entry.ref_type == "trip" and entry.ref_id is not None:
        trip = (
            db.query(Trip)
            .filter(Trip.id == entry.ref_id, Trip.family_id == family_id)
            .with_for_update()
            .first()
        )
        if trip:
            spend_amount = _family_proportional_share(db, trip.id, entry.amount_cny)
            trip.actual_spend = (trip.actual_spend or Decimal("0")) - spend_amount

    db.commit()


def list_expenses(
    db: Session,
    family_id: int,
    ref_id: int | None = None,
    ref_type: str | None = None,
    limit: int = 50,
) -> list[ExpenseEntry]:
    """List expenses (debit legs only) for a family, optionally filtered."""
    query = db.query(ExpenseEntry).filter(
        ExpenseEntry.family_id == family_id,
        ExpenseEntry.leg_type == "debit",
    )
    if ref_id is not None:
        query = query.filter(ExpenseEntry.ref_id == ref_id)
    if ref_type is not None:
        query = query.filter(ExpenseEntry.ref_type == ref_type)
    return query.order_by(ExpenseEntry.expense_date.desc()).limit(limit).all()


def get_expense(
    db: Session,
    entry_id: int,
    family_id: int,
) -> ExpenseEntry:
    """Get a single expense entry."""
    entry = (
        db.query(ExpenseEntry)
        .filter(
            ExpenseEntry.id == entry_id,
            ExpenseEntry.family_id == family_id,
        )
        .first()
    )
    if not entry:
        raise AppError(ErrorCode.EXPENSE_NOT_FOUND)
    return entry


def _family_proportional_share(
    db: Session, trip_id: int, amount_cny: Decimal
) -> Decimal:
    """Calculate the family's proportional share of an expense.

    If the trip has an active split group, the family's share is
    amount_cny / total_participants. Otherwise returns the full amount.
    Per R7a: trip.actual_spend reflects the family's proportional share
    of shared expenses plus 100% of non-shared expenses.
    """
    group = (
        db.query(SplitGroup)
        .filter(SplitGroup.trip_id == trip_id, SplitGroup.is_active == True)  # noqa: E712
        .first()
    )
    if not group:
        return amount_cny

    num_participants = (
        db.query(SplitParticipant)
        .filter(SplitParticipant.group_id == group.id)
        .count()
    )
    if num_participants <= 1:
        return amount_cny

    return (amount_cny / num_participants).quantize(Decimal("0.01"))
