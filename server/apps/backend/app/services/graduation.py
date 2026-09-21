"""Wish-to-Trip graduation pipeline (U5)."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from apps.backend.app.services.wish import complete_wish
from packages.db.models.trip import Trip


def graduate_to_trip(
    db: Session,
    wish_id: int,
    user: User,
) -> Trip:
    """Convert a pending travel wish into a Trip and mark the wish realized.

    Validates ownership, status, and converts_to_asset=False before creating
    the Trip.  Delegates wish realization to ``complete_wish`` so cache
    invalidation (finance-coach, dashboard-narrative, wish-advice) is handled
    in one place.
    """
    wish = (
        db.query(Wish)
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .first()
    )
    if not wish:
        raise AppError(ErrorCode.WISH_NOT_FOUND)

    if wish.user_id != user.id:
        raise AppError(ErrorCode.FORBIDDEN)

    if wish.status != "pending":
        raise AppError(ErrorCode.VALIDATION_ERROR)

    if wish.converts_to_asset:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    trip = Trip(
        family_id=wish.family_id,
        user_id=wish.user_id,
        name=wish.name,
        destination="",
        departure_date=wish.target_date,
        planned_budget=wish.expected_price,
        initial_funding=wish.saved_amount,
        currency=wish.currency,
        wish_id=wish.id,
        status="planning",
    )
    db.add(trip)
    db.flush()  # populate trip.id before completing the wish

    # complete_wish commits the transaction and invalidates caches
    complete_wish(db, user, wish_id)

    db.refresh(trip)
    return trip
