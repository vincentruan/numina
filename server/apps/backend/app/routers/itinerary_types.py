"""Itinerary item type router — family-scoped custom types."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.itinerary_item import (
    ItineraryItemTypeCreate,
    ItineraryItemTypeResponse,
    ItineraryItemTypeUpdate,
)
from apps.backend.app.services import itinerary_type as itinerary_type_service

router = APIRouter(prefix="/itinerary-types", tags=["travel"])


@router.get("", response_model=list[ItineraryItemTypeResponse])
def list_types(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return itinerary_type_service.list_types(db, user.family_id)


@router.post("", response_model=ItineraryItemTypeResponse, status_code=201)
def create_type(
    req: ItineraryItemTypeCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return itinerary_type_service.create_type(db, user.family_id, req)


@router.get("/{type_id}", response_model=ItineraryItemTypeResponse)
def get_type(
    type_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return itinerary_type_service.get_type(db, type_id, user.family_id)


@router.patch("/{type_id}", response_model=ItineraryItemTypeResponse)
def update_type(
    type_id: int,
    req: ItineraryItemTypeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    iit = itinerary_type_service.get_type(db, type_id, user.family_id)
    return itinerary_type_service.update_type(db, iit, req)


@router.delete("/{type_id}")
def delete_type(
    type_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    itinerary_type_service.delete_type(db, type_id, user.family_id)
    return {"detail": "已删除"}
