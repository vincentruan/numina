"""Itinerary item type service — family-scoped custom type CRUD."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.itinerary_item import (
    ItineraryItemTypeCreate,
    ItineraryItemTypeUpdate,
)
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.itinerary_item_type import ItineraryItemType


def list_types(db: Session, family_id: int) -> list[ItineraryItemType]:
    """List custom types for a family (including system-level types with family_id=null)."""
    return (
        db.query(ItineraryItemType)
        .filter(
            (ItineraryItemType.family_id == family_id)
            | (ItineraryItemType.family_id.is_(None))
        )
        .order_by(ItineraryItemType.sort_order, ItineraryItemType.id)
        .all()
    )


def create_type(
    db: Session,
    family_id: int,
    data: ItineraryItemTypeCreate,
) -> ItineraryItemType:
    """Create a family-scoped custom type."""
    iit = ItineraryItemType(
        family_id=family_id,
        name=data.name,
        icon=data.icon,
        sort_order=data.sort_order,
    )
    db.add(iit)
    db.commit()
    db.refresh(iit)
    return iit


def get_type(db: Session, type_id: int, family_id: int) -> ItineraryItemType:
    """Get a single custom type."""
    iit = (
        db.query(ItineraryItemType)
        .filter(
            ItineraryItemType.id == type_id,
            (ItineraryItemType.family_id == family_id)
            | (ItineraryItemType.family_id.is_(None)),
        )
        .first()
    )
    if not iit:
        raise AppError(ErrorCode.ITINERARY_TYPE_NOT_FOUND)
    return iit


def update_type(
    db: Session,
    iit: ItineraryItemType,
    data: ItineraryItemTypeUpdate,
) -> ItineraryItemType:
    """Update a custom type."""
    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(iit, field, value)
    db.commit()
    db.refresh(iit)
    return iit


def delete_type(db: Session, type_id: int, family_id: int) -> None:
    """Delete a custom type. Reject if in use by any ItineraryItem."""
    iit = get_type(db, type_id, family_id)

    # Check if in use
    in_use = (
        db.query(ItineraryItem)
        .filter(ItineraryItem.custom_type_id == type_id)
        .first()
    )
    if in_use:
        raise AppError(ErrorCode.ITINERARY_TYPE_IN_USE)

    db.delete(iit)
    db.commit()
