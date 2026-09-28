"""Split group router — nested under /trips/{trip_id}/split."""

from fastapi import APIRouter, Body, Depends
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

import logging

logger = logging.getLogger(__name__)


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
        expires_at=group.expires_at,
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


@router.delete("/participants/{participant_id}", status_code=204)
def remove_participant(
    trip_id: int,
    participant_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Remove a participant from the split group. Organizer or co-organizer only."""
    if not split_group_service.is_organizer_or_co(db, trip_id, user.id):
        from apps.backend.app.errors import AppError, ErrorCode

        raise AppError(ErrorCode.CO_ORGANIZER_NOT_ALLOWED)
    split_group_service.remove_participant(db, participant_id, user.family_id)


@router.post("/regenerate-code", response_model=SplitGroupResponse)
def regenerate_invite_code(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Regenerate the invite code. Organizer only."""
    result = split_group_service.get_group_with_participants(
        db, trip_id, user.family_id
    )
    group = result["group"]
    participants = result["participants"]
    updated = split_group_service.regenerate_code(db, group.id, user.family_id)
    return SplitGroupResponse(
        id=updated.id,
        trip_id=updated.trip_id,
        invite_code=updated.invite_code,
        created_by_user_id=updated.created_by_user_id,
        is_active=updated.is_active,
        expires_at=updated.expires_at,
        created_at=updated.created_at,
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


@router.post("/settle", response_model=list[SplitSettlementResponse], status_code=201)
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
    target_user_id: int = Body(..., embed=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    co = split_group_service.add_co_organizer(
        db, trip_id, user.family_id, user.id, target_user_id
    )
    return {"id": co.id, "trip_id": co.trip_id, "user_id": co.user_id}


@router.get("/co-organizers")
def get_co_organizers(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List co-organizers for a trip."""
    from apps.backend.app.models.split_group import TripCoOrganizer

    # Verify access (raises AppError if user has no permission)
    split_group_service._get_trip(db, trip_id, user.family_id)
    cos = (
        db.query(TripCoOrganizer)
        .filter(TripCoOrganizer.trip_id == trip_id)
        .all()
    )
    # Enrich with user display_name
    user_ids = [co.user_id for co in cos]
    user_map = {
        u.id: u.display_name
        for u in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    return [
        {"user_id": co.user_id, "display_name": user_map.get(co.user_id, "")}
        for co in cos
    ]


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


# ---------------------------------------------------------------------------
# Share link endpoint
# ---------------------------------------------------------------------------


@router.post("/share-link")
async def create_share_link(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Generate a short.io share link for the split group invite code."""
    from short_io_api_client import AuthenticatedClient
    from short_io_api_client.api.link_management import post_links
    from short_io_api_client.models import PostLinksBody

    from packages.core.settings import settings
    from apps.backend.app.errors import AppError, ErrorCode

    if not settings.SHORTIO_API_KEY or not settings.SHORTIO_DOMAIN:
        raise AppError(ErrorCode.SHARE_LINK_NOT_CONFIGURED)

    # Get the split group to verify it exists and user has access
    result = split_group_service.get_group_with_participants(
        db, trip_id, user.family_id
    )
    group = result["group"]

    # Derive the public base URL from CORS_ORIGINS (first entry, typically the production domain)
    base_url = ""
    if settings.CORS_ORIGINS:
        import re
        match = re.match(r"(https?://[^/]+)", settings.CORS_ORIGINS[0])
        if match:
            base_url = match.group(1)
    if not base_url:
        raise AppError(ErrorCode.SHARE_LINK_NOT_CONFIGURED)

    original_url = f"{base_url}/travel/shared/{group.invite_code}"

    client = AuthenticatedClient(
        base_url="https://api.short.io",
        token=settings.SHORTIO_API_KEY,
        prefix="",
    )

    try:
        result = await post_links.asyncio(
            client=client,
            body=PostLinksBody(
                original_url=original_url,
                domain=settings.SHORTIO_DOMAIN,
            ),
        )
    except Exception as exc:
        logger.warning("short.io API call failed: %s", exc)
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED) from exc

    if result is None:
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    # short.io returns error responses (403, 400, etc.) as typed result objects
    # rather than raising exceptions. Detect these and log the actual error.
    result_class_name = type(result).__name__
    if "Response4" in result_class_name or "Response5" in result_class_name:
        error_msg = getattr(result, "message", None) or str(result)
        logger.warning(
            "short.io rejected link creation: %s (domain=%s)",
            error_msg,
            settings.SHORTIO_DOMAIN,
        )
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    # The auto-generated response model stores most fields in additional_properties
    short_url = None
    if hasattr(result, "additional_properties"):
        short_url = (
            result.additional_properties.get("shortURL")
            or result.additional_properties.get("secureShortURL")
        )

    if not short_url:
        logger.warning(
            "short.io response had no shortURL field: %s",
            result_class_name,
        )
        raise AppError(ErrorCode.SHARE_LINK_CREATION_FAILED)

    return {"short_url": short_url}
