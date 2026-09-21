"""Settlement service — debt simplification for shared travel expenses."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services import split_group as split_group_service
from apps.backend.app.services import trip as trip_service
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.split_group import SplitParticipant, SplitSettlement
from packages.db.models.user import User

_REVERSE_WINDOW_HOURS = 24


def _get_trip(db: Session, trip_id: int, family_id: int):
    """Delegate to trip_service.get_trip for consistency."""
    return trip_service.get_trip(db, trip_id, family_id)


def simplify_debts(db: Session, trip_id: int, family_id: int) -> list[SplitSettlement]:
    """Calculate and persist simplified settlement records for a trip.

    Algorithm:
    1. Get all shared expenses (debit legs) for the trip.
    2. Compute each participant's net balance (paid - owed share).
    3. Greedy max-creditor / max-debtor matching to minimise transfers.
    4. Delete any previous settlements for this trip and persist new ones.
    """
    # Verify trip exists and belongs to family
    _get_trip(db, trip_id, family_id)

    # Get all debit expenses for this trip
    expenses = (
        db.query(ExpenseEntry)
        .filter(
            ExpenseEntry.family_id == family_id,
            ExpenseEntry.ref_id == trip_id,
            ExpenseEntry.ref_type == "trip",
            ExpenseEntry.leg_type == "debit",
        )
        .all()
    )

    # Get split participants
    participants = split_group_service.get_group_with_participants(
        db, trip_id, family_id
    )
    participant_list: list[SplitParticipant] = participants["participants"]
    num_participants = len(participant_list)

    if num_participants == 0 or not expenses:
        return []

    # Build user_id -> participant_name mapping
    user_ids = {e.user_id for e in expenses}
    user_name_map: dict[int, str] = {}
    if user_ids:
        users = db.query(User).filter(User.id.in_(user_ids)).all()
        user_name_map = {u.id: u.display_name for u in users}

    # Calculate net balances
    net: dict[str, Decimal] = {}
    for p in participant_list:
        net[p.name] = Decimal("0")

    for expense in expenses:
        payer_name = user_name_map.get(expense.user_id, f"User_{expense.user_id}")
        # Ensure payer exists in net (they may not be a split participant)
        if payer_name not in net:
            net[payer_name] = Decimal("0")

        # Use amount_cny for arithmetic to avoid cross-currency errors
        amount_cny = expense.amount_cny
        share = amount_cny / num_participants
        net[payer_name] = net[payer_name] + amount_cny
        for p in participant_list:
            net[p.name] = net[p.name] - share

    # Greedy algorithm — separate creditors and debtors
    creditors = sorted(
        [(name, bal) for name, bal in net.items() if bal > Decimal("0.005")],
        key=lambda x: -x[1],
    )
    debtors = sorted(
        [(name, -bal) for name, bal in net.items() if bal < Decimal("-0.005")],
        key=lambda x: -x[1],
    )

    # Prevent recalculation when completed settlements exist (audit trail protection)
    completed_count = (
        db.query(SplitSettlement)
        .filter(
            SplitSettlement.trip_id == trip_id,
            SplitSettlement.is_complete == True,  # noqa: E712
        )
        .count()
    )
    if completed_count > 0:
        raise AppError(ErrorCode.SETTLEMENT_HAS_COMPLETED)

    # Delete previous non-completed settlements for this trip
    db.query(SplitSettlement).filter(
        SplitSettlement.trip_id == trip_id,
        SplitSettlement.is_complete == False,  # noqa: E712
    ).delete()

    settlements: list[SplitSettlement] = []
    debtor_idx, creditor_idx = 0, 0
    while debtor_idx < len(debtors) and creditor_idx < len(creditors):
        amount = min(debtors[debtor_idx][1], creditors[creditor_idx][1])
        if amount <= Decimal("0"):
            break

        settlement = SplitSettlement(
            trip_id=trip_id,
            from_participant_name=debtors[debtor_idx][0],
            to_participant_name=creditors[creditor_idx][0],
            amount=amount.quantize(Decimal("0.01")),
            currency="CNY",
        )
        db.add(settlement)
        settlements.append(settlement)

        debtors[debtor_idx] = (debtors[debtor_idx][0], debtors[debtor_idx][1] - amount)
        creditors[creditor_idx] = (creditors[creditor_idx][0], creditors[creditor_idx][1] - amount)
        if debtors[debtor_idx][1] <= Decimal("0.005"):
            debtor_idx += 1
        if creditors[creditor_idx][1] <= Decimal("0.005"):
            creditor_idx += 1

    db.commit()
    for s in settlements:
        db.refresh(s)
    return settlements


def mark_settlement_complete(
    db: Session, settlement_id: int, family_id: int, user_id: int
) -> SplitSettlement:
    """Mark a settlement as complete. User must be organizer or co-organizer."""
    settlement = (
        db.query(SplitSettlement).filter(SplitSettlement.id == settlement_id).first()
    )
    if not settlement:
        raise AppError(ErrorCode.SETTLEMENT_NOT_FOUND)

    _get_trip(db, settlement.trip_id, family_id)

    if not split_group_service.is_organizer_or_co(db, settlement.trip_id, user_id):
        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)

    settlement.is_complete = True
    settlement.settled_at = datetime.now(UTC)
    settlement.settled_by_user_id = user_id
    db.commit()
    db.refresh(settlement)
    return settlement


def reverse_settlement(
    db: Session, settlement_id: int, family_id: int, user_id: int
) -> SplitSettlement:
    """Reverse a completed settlement within 24h window."""
    settlement = (
        db.query(SplitSettlement).filter(SplitSettlement.id == settlement_id).first()
    )
    if not settlement:
        raise AppError(ErrorCode.SETTLEMENT_NOT_FOUND)

    _get_trip(db, settlement.trip_id, family_id)

    if not split_group_service.is_organizer_or_co(db, settlement.trip_id, user_id):
        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)

    if settlement.settled_at is None:
        raise AppError(ErrorCode.SETTLEMENT_NOT_FOUND)

    cutoff = settlement.settled_at + timedelta(hours=_REVERSE_WINDOW_HOURS)
    if datetime.now(UTC) > cutoff:
        raise AppError(ErrorCode.SETTLEMENT_REVERSE_EXPIRED)

    settlement.is_complete = False
    settlement.settled_at = None
    settlement.settled_by_user_id = None
    db.commit()
    db.refresh(settlement)
    return settlement


def get_settlements(db: Session, trip_id: int, family_id: int) -> list[SplitSettlement]:
    """List all settlements for a trip."""
    _get_trip(db, trip_id, family_id)
    return (
        db.query(SplitSettlement)
        .filter(SplitSettlement.trip_id == trip_id)
        .order_by(SplitSettlement.created_at)
        .all()
    )
