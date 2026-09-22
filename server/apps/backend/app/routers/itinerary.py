"""Itinerary item router — scoped under a trip."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.itinerary_item import (
    ItineraryItemCreate,
    ItineraryItemResponse,
    ItineraryItemUpdate,
)
from apps.backend.app.services import itinerary as itinerary_service
from apps.backend.app.services import trip as trip_service

router = APIRouter(prefix="/trips/{trip_id}/itinerary", tags=["travel"])


@router.get("", response_model=list[ItineraryItemResponse])
def list_items(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    return itinerary_service.list_items(db, trip_id, user.family_id)


@router.post("", response_model=ItineraryItemResponse, status_code=201)
def create_item(
    trip_id: int,
    req: ItineraryItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip = trip_service.get_trip(db, trip_id, user.family_id)
    return itinerary_service.create_item(db, trip, user.id, req)


@router.get("/{item_id}", response_model=ItineraryItemResponse)
def get_item(
    trip_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    return itinerary_service.get_item(db, item_id, user.family_id)


@router.patch("/{item_id}", response_model=ItineraryItemResponse)
def update_item(
    trip_id: int,
    item_id: int,
    req: ItineraryItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip = trip_service.get_trip(db, trip_id, user.family_id)
    item = itinerary_service.get_item(db, item_id, user.family_id)
    return itinerary_service.update_item(db, item, user.id, req, trip=trip)


@router.delete("/{item_id}")
def delete_item(
    trip_id: int,
    item_id: int,
    mode: str = Query(..., pattern="^(cascade|unlink)$"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    item = itinerary_service.get_item(db, item_id, user.family_id)
    itinerary_service.delete_item(db, item, user.id, mode)

    return {"detail": "已删除"}
