"""Trip CRUD router."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.split_group import GraduationRequest
from apps.backend.app.schemas.trip import (
    TripCreate,
    TripResponse,
    TripUpdate,
)
from apps.backend.app.services import graduation as graduation_service
from apps.backend.app.services import trip as trip_service

router = APIRouter(prefix="/trips", tags=["travel"])


@router.get("", response_model=list[TripResponse])
def list_trips(
    status: str | None = Query(None),
    active_only: bool | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return trip_service.list_trips(db, user.family_id, status, active_only)


@router.post("", response_model=TripResponse, status_code=201)
def create_trip(
    req: TripCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return trip_service.create_trip(db, user.family_id, user.id, req)


@router.post("/graduate", response_model=TripResponse, status_code=201)
def graduate_wish_to_trip(
    req: GraduationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return graduation_service.graduate_to_trip(db, req.wish_id, user)


@router.get("/{trip_id}", response_model=TripResponse)
def get_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return trip_service.get_trip(db, trip_id, user.family_id)


@router.patch("/{trip_id}", response_model=TripResponse)
def update_trip(
    trip_id: int,
    req: TripUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return trip_service.update_trip(db, trip_id, user.family_id, req)


@router.delete("/{trip_id}")
def delete_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.delete_trip(db, trip_id, user.family_id)
    return {"detail": "已删除"}


@router.post("/{trip_id}/cancel", response_model=TripResponse)
def cancel_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.cancel_trip(db, trip_id, user.family_id)
    return trip_service.get_trip(db, trip_id, user.family_id)
