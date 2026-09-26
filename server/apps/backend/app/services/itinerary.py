"""Itinerary item service — CRUD with expense ledger integration."""

import logging

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.expense_entry import ExpenseEntryCreate
from apps.backend.app.schemas.itinerary_item import (
    ItineraryItemCreate,
    ItineraryItemUpdate,
)
from apps.backend.app.services import expense_ledger
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.itinerary_item_type import ItineraryItemType
from packages.db.models.trip import Trip

logger = logging.getLogger(__name__)


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
    _validate_type_and_custom_type(db, data.type, data.custom_type_id, trip.family_id)

    item = ItineraryItem(
        trip_id=trip.id,
        family_id=trip.family_id,
        date=data.date,
        end_date=data.end_date,
        type=data.type,
        sort_order=data.sort_order,
        start_time=data.start_time,
        end_time=data.end_time,
        location=data.location,
        description=data.description,
        cost_amount=data.cost_amount,
        cost_currency=data.cost_currency,
        purchase_date=data.purchase_date,
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
    *,
    trip: Trip | None = None,
) -> ItineraryItem:
    """Update an itinerary item. Sync expense ledger if cost changed."""
    update_fields = data.model_dump(exclude_unset=True)

    # Validate custom type reference if type changed
    new_type = update_fields.get("type", item.type)
    new_custom_type_id = update_fields.get("custom_type_id", item.custom_type_id)
    _validate_type_and_custom_type(db, new_type, new_custom_type_id, item.family_id)

    # Check if cost, currency, or purchase_date changed
    old_cost = item.cost_amount
    new_cost = update_fields.get("cost_amount", old_cost)
    old_currency = item.cost_currency
    new_currency = update_fields.get("cost_currency", old_currency)
    old_purchase_date = item.purchase_date
    new_purchase_date = update_fields.get("purchase_date", old_purchase_date)
    cost_changed = new_cost != old_cost or new_currency != old_currency
    purchase_date_changed = new_purchase_date != old_purchase_date
    expense_needs_recreate = cost_changed or purchase_date_changed

    # Handle cost removal (set to None or 0)
    if expense_needs_recreate and old_cost and old_cost > 0:
        if not new_cost or new_cost <= 0:
            # Cost removed — reverse old expense (defer commit to outer scope)
            _delete_linked_expense(db, item, user_id, no_commit=True)
            update_fields["cost_amount"] = None
            update_fields["cost_currency"] = None
        else:
            # Cost or purchase_date changed — reverse old (defer commit to outer scope)
            _delete_linked_expense(db, item, user_id, no_commit=True)

    # Update item fields
    for field, value in update_fields.items():
        setattr(item, field, value)

    # Service-level cross-field validation: schema validator cannot check
    # end_date >= date on partial PATCH (date may not be in payload).
    if item.end_date and item.date and item.end_date < item.date:
        raise ValueError("end_date must be >= date")

    db.flush()

    # Create new expense if cost/purchase_date changed and cost is positive (defer commit)
    if expense_needs_recreate and new_cost and new_cost > 0:
        if trip is None:
            trip = db.query(Trip).filter(Trip.id == item.trip_id, Trip.family_id == item.family_id).first()
        _create_linked_expense(db, trip, user_id, item, no_commit=True)

    # Single commit wraps the entire update atomically
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
            _delete_linked_expense(db, item, user_id)
            # Null itinerary_item_id on original entries so FK allows item deletion
            _unlink_expense_entries(db, item)
        elif mode == "unlink":
            _unlink_expense_entries(db, item)

    db.delete(item)
    db.commit()


def _validate_type_and_custom_type(
    db: Session, item_type: str, custom_type_id: int | None, family_id: int,
) -> None:
    """Validate item type and custom type reference."""
    if item_type == "custom":
        if not custom_type_id:
            raise AppError(ErrorCode.INVALID_ITEM_TYPE)
        _validate_custom_type(db, custom_type_id, family_id)


def _validate_custom_type(db: Session, custom_type_id: int, family_id: int) -> None:
    """Validate that a custom type exists and belongs to this family."""
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
    *,
    no_commit: bool = False,
) -> None:
    """Create a debit/credit expense pair linked to an itinerary item."""
    req = ExpenseEntryCreate(
        amount=item.cost_amount,
        currency=item.cost_currency or trip.currency,
        expense_date=item.purchase_date or item.date,
        ref_id=trip.id,
        ref_type="trip",
        description=item.description or item.location or f"{item.type} expense",
        itinerary_item_id=item.id,
    )
    expense_ledger.create_expense(db, trip.family_id, user_id, req, no_commit=no_commit)


def _delete_linked_expense(
    db: Session,
    item: ItineraryItem,
    user_id: int,
    *,
    no_commit: bool = False,
) -> None:
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
        expense_ledger.delete_expense(
            db, debit.id, item.family_id, user_id, no_commit=no_commit,
        )
    elif item.cost_amount and item.cost_amount > 0:
        logger.warning(
            "Orphaned itinerary item %s: cost_amount=%s but no linked debit expense",
            item.id, item.cost_amount,
        )


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
