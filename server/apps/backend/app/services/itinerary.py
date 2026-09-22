"""Itinerary item service — CRUD with expense ledger integration."""

from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.expense_entry import ExpenseEntryCreate
from apps.backend.app.schemas.itinerary_item import ItineraryItemCreate, ItineraryItemUpdate
from apps.backend.app.services import expense_ledger
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.trip import Trip


def list_items(db: Session, trip_id: int, family_id: int) -> list[ItineraryItem]:
    """List all itinerary items for a trip, ordered by date + sort_order."""
    return (
        db.query(ItineraryItem)
        .filter(
            ItineraryItem.trip_id == trip_id,
            ItineraryItem.family_id == family_id,
        )
        .order_by(ItineraryItem.date, ItineraryItem.sort_order, ItineraryItem.created_at)
        .all()
    )


def get_item(db: Session, item_id: int, family_id: int) -> ItineraryItem:
    """Get a single itinerary item."""
    item = (
        db.query(ItineraryItem)
        .filter(
            ItineraryItem.id == item_id,
            ItineraryItem.family_id == family_id,
        )
        .first()
    )
    if not item:
        raise AppError(ErrorCode.ITINERARY_ITEM_NOT_FOUND)
    return item


def create_item(
    db: Session,
    trip: Trip,
    user_id: int,
    data: ItineraryItemCreate,
) -> ItineraryItem:
    """Create an itinerary item. If cost is set, auto-create linked expense."""
    # Validate custom type reference
    if data.type == "custom" and data.custom_type_id:
        _validate_custom_type(db, data.custom_type_id, trip.family_id)
    elif data.type == "custom" and not data.custom_type_id:
        raise AppError(ErrorCode.INVALID_ITEM_TYPE)

    item = ItineraryItem(
        trip_id=trip.id,
        family_id=trip.family_id,
        date=data.date,
        type=data.type,
        sort_order=data.sort_order,
        start_time=data.start_time,
        end_time=data.end_time,
        location=data.location,
        description=data.description,
        cost_amount=data.cost_amount,
        cost_currency=data.cost_currency,
        custom_type_id=data.custom_type_id,
        type_metadata=data.type_metadata,
    )
    db.add(item)
    db.flush()  # Get item.id for expense linking

    # Auto-create linked expense if cost is set
    if data.cost_amount and data.cost_amount > 0:
        _create_linked_expense(db, trip, user_id, item)

    db.commit()
    db.refresh(item)
    return item


def update_item(
    db: Session,
    item: ItineraryItem,
    user_id: int,
    data: ItineraryItemUpdate,
) -> ItineraryItem:
    """Update an itinerary item. Sync expense ledger if cost changed."""
    update_fields = data.model_dump(exclude_unset=True)

    # Validate custom type reference if type changed
    new_type = update_fields.get("type", item.type)
    new_custom_type_id = update_fields.get("custom_type_id", item.custom_type_id)
    if new_type == "custom" and new_custom_type_id:
        _validate_custom_type(db, new_custom_type_id, item.family_id)
    elif new_type == "custom" and not new_custom_type_id:
        raise AppError(ErrorCode.INVALID_ITEM_TYPE)

    # Check if cost changed
    old_cost = item.cost_amount
    new_cost = update_fields.get("cost_amount", old_cost)
    cost_changed = new_cost != old_cost

    # Handle cost removal (set to None or 0)
    if cost_changed and old_cost and old_cost > 0:
        if not new_cost or new_cost <= 0:
            # Cost removed — reverse old expense
            _delete_linked_expense(db, item)
            update_fields["cost_amount"] = None
            update_fields["cost_currency"] = None
        else:
            # Cost changed — reverse old, create new
            _delete_linked_expense(db, item)

    # Update item fields
    for field, value in update_fields.items():
        setattr(item, field, value)

    db.flush()

    # Create new expense if cost changed and new cost is positive
    if cost_changed and new_cost and new_cost > 0:
        trip = db.query(Trip).filter(Trip.id == item.trip_id).first()
        _create_linked_expense(db, trip, user_id, item)

    db.commit()
    db.refresh(item)
    return item


def delete_item(
    db: Session,
    item: ItineraryItem,
    user_id: int,
    mode: str,
) -> None:
    """Delete an itinerary item.

    mode='cascade': reverse linked expense entries + delete item
    mode='unlink': null itinerary_item_id on entries + delete item
    """
    has_cost = item.cost_amount and item.cost_amount > 0

    if has_cost:
        if mode == "cascade":
            _delete_linked_expense(db, item)
        elif mode == "unlink":
            _unlink_expense_entries(db, item)
        # mode validation is done at router level

    db.delete(item)
    db.commit()


def _validate_custom_type(db: Session, custom_type_id: int, family_id: int) -> None:
    """Validate that a custom type exists and belongs to this family."""
    from packages.db.models.itinerary_item_type import ItineraryItemType

    iit = (
        db.query(ItineraryItemType)
        .filter(
            ItineraryItemType.id == custom_type_id,
        )
        .first()
    )
    if not iit:
        raise AppError(ErrorCode.ITINERARY_TYPE_NOT_FOUND)
    # Allow family-scoped or system-level (family_id=null) types
    if iit.family_id is not None and iit.family_id != family_id:
        raise AppError(ErrorCode.ITINERARY_TYPE_NOT_FOUND)


def _create_linked_expense(
    db: Session,
    trip: Trip,
    user_id: int,
    item: ItineraryItem,
) -> None:
    """Create a debit/credit expense pair linked to an itinerary item."""
    req = ExpenseEntryCreate(
        amount=item.cost_amount,
        currency=item.cost_currency or trip.currency,
        expense_date=item.date,
        ref_id=trip.id,
        ref_type="trip",
        description=item.description or item.location or f"{item.type} expense",
        itinerary_item_id=item.id,
    )
    expense_ledger.create_expense(db, trip.family_id, user_id, req)


def _delete_linked_expense(db: Session, item: ItineraryItem) -> None:
    """Reverse the expense entries linked to an itinerary item (cascade delete)."""
    debit = (
        db.query(ExpenseEntry)
        .filter(
            ExpenseEntry.itinerary_item_id == item.id,
            ExpenseEntry.leg_type == "debit",
        )
        .first()
    )
    if debit:
        expense_ledger.delete_expense(db, debit.id, item.family_id, item.family_id)


def _unlink_expense_entries(db: Session, item: ItineraryItem) -> None:
    """Null itinerary_item_id on all linked expense entries (unlink mode)."""
    entries = (
        db.query(ExpenseEntry)
        .filter(ExpenseEntry.itinerary_item_id == item.id)
        .all()
    )
    for entry in entries:
        entry.itinerary_item_id = None
    db.flush()
