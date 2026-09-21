"""Split group router — nested under /trips/{trip_id}/split."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.split_group import (
    SplitGroupResponse,
    SplitParticipantResponse,
    SplitSettlementResponse,
)
from apps.backend.app.services import settlement as settlement_service
from apps.backend.app.services import split_group as split_group_service

router = APIRouter(prefix="/trips/{trip_id}/split", tags=["travel"])


@router.post("", response_model=SplitGroupResponse, status_code=201)
def create_group(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return split_group_service.create_group(db, trip_id, user.family_id, user.id)


@router.get("", response_model=SplitGroupResponse)
def get_group(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    result = split_group_service.get_group_with_participants(
        db, trip_id, user.family_id
    )
    group = result["group"]
    participants = result["participants"]
    # Build response with participants
    return SplitGroupResponse(
        id=group.id,
        trip_id=group.trip_id,
        invite_code=group.invite_code,
        created_by_user_id=group.created_by_user_id,
        is_active=group.is_active,
        created_at=group.created_at,
        participants=[
            SplitParticipantResponse(
                id=p.id,
                group_id=p.group_id,
                name=p.name,
                family_id=p.family_id,
                joined_at=p.joined_at,
            )
            for p in participants
        ],
    )


@router.post("/settle", response_model=list[SplitSettlementResponse])
def simplify_debts(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if not split_group_service.is_organizer_or_co(db, trip_id, user.id):
        from apps.backend.app.errors import AppError, ErrorCode

        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)
    return settlement_service.simplify_debts(db, trip_id, user.family_id)


@router.get("/settlements", response_model=list[SplitSettlementResponse])
def get_settlements(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return settlement_service.get_settlements(db, trip_id, user.family_id)


@router.patch(
    "/settlements/{settlement_id}/complete", response_model=SplitSettlementResponse
)
def mark_settlement_complete(
    trip_id: int,
    settlement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return settlement_service.mark_settlement_complete(
        db, settlement_id, user.family_id, user.id
    )


@router.delete(
    "/settlements/{settlement_id}/complete", response_model=SplitSettlementResponse
)
def reverse_settlement(
    trip_id: int,
    settlement_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return settlement_service.reverse_settlement(
        db, settlement_id, user.family_id, user.id
    )


# ---------------------------------------------------------------------------
# Co-organizer endpoints
# ---------------------------------------------------------------------------


@router.post("/co-organizers", status_code=201)
def add_co_organizer(
    trip_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    co = split_group_service.add_co_organizer(
        db, trip_id, user.family_id, user.id, target_user_id
    )
    return {"id": co.id, "trip_id": co.trip_id, "user_id": co.user_id}


@router.delete("/co-organizers/{target_user_id}")
def remove_co_organizer(
    trip_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    split_group_service.remove_co_organizer(
        db, trip_id, user.family_id, user.id, target_user_id
    )
    return {"detail": "已删除"}
