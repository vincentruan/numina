"""Trip CRUD service."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.trip import _VALID_TRANSITIONS, TripCreate, TripUpdate
from apps.backend.app.services import expense_ledger
from packages.db.models.split_group import SplitGroup
from packages.db.models.trip import Trip
from packages.db.models.wish import Wish


def list_trips(
    db: Session,
    family_id: int,
    status: str | None = None,
    active_only: bool | None = None,
) -> list[Trip]:
    """List trips for a family with optional filters."""
    query = db.query(Trip).filter(Trip.family_id == family_id)
    if status is not None:
        query = query.filter(Trip.status == status)
    if active_only is not None:
        query = query.filter(Trip.is_active == active_only)
    return query.order_by(Trip.departure_date.desc()).all()


def get_trip(db: Session, trip_id: int, family_id: int) -> Trip:
    """Get a single trip, 404 if not found or wrong family."""
    trip = (
        db.query(Trip).filter(Trip.id == trip_id, Trip.family_id == family_id).first()
    )
    if not trip:
        raise AppError(ErrorCode.TRIP_NOT_FOUND)
    return trip


def create_trip(
    db: Session,
    family_id: int,
    user_id: int,
    req: TripCreate,
) -> Trip:
    """Create a new trip."""
    trip = Trip(
        family_id=family_id,
        user_id=user_id,
        name=req.name,
        destination=req.destination,
        departure_date=req.departure_date,
        return_date=req.return_date,
        planned_budget=req.planned_budget,
        currency=req.currency,
        timezone=req.timezone,
        wish_id=req.wish_id,
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


def update_trip(
    db: Session,
    trip_id: int,
    family_id: int,
    req: TripUpdate,
) -> Trip:
    """Update trip fields."""
    trip = get_trip(db, trip_id, family_id)
    update_data = req.model_dump(exclude_unset=True)

    # Enforce status transition rules
    if "status" in update_data:
        new_status = update_data["status"]
        current_status = trip.status
        allowed_next = _VALID_TRANSITIONS.get(current_status)
        if allowed_next and new_status != allowed_next:
            raise AppError(
                ErrorCode.TRIP_STATUS_CONFLICT,
                details=f"Cannot transition from '{current_status}' to '{new_status}'",
            )

    for key, value in update_data.items():
        setattr(trip, key, value)
    db.commit()
    db.refresh(trip)
    return trip


def delete_trip(db: Session, trip_id: int, family_id: int) -> None:
    """Soft delete — set is_active=False."""
    trip = get_trip(db, trip_id, family_id)
    trip.is_active = False
    db.commit()


def cancel_trip(db: Session, trip_id: int, family_id: int) -> None:
    """Cancel a trip: revert wish, reverse expenses, invalidate split group."""
    trip = get_trip(db, trip_id, family_id)

    if trip.status != "planning":
        raise AppError(ErrorCode.TRIP_STATUS_CONFLICT)

    # Revert wish to pending if linked
    if trip.wish_id is not None:
        wish = db.query(Wish).filter(Wish.id == trip.wish_id).first()
        if wish and wish.status == "realized":
            wish.status = "pending"

    # Reverse all expenses for this trip
    expenses = expense_ledger.list_expenses(
        db, family_id, ref_id=trip_id, ref_type="trip", limit=1000
    )
    for exp in expenses:
        expense_ledger.delete_expense(db, exp.id, family_id, trip.user_id)

    # Invalidate split groups
    split_groups = (
        db.query(SplitGroup)
        .filter(SplitGroup.trip_id == trip_id, SplitGroup.is_active == True)  # noqa: E712
        .all()
    )
    for sg in split_groups:
        sg.is_active = False

    trip.status = "cancelled"
    trip.is_active = False
    db.commit()
