"""Shared expense router — public endpoints for external participants via invite code."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.middleware.rate_limit import _get_real_client_ip
from apps.backend.app.schemas.split_group import (
    SharedExpenseItem,
    SharedExpenseResponse,
    SplitParticipantCreate,
    SplitParticipantResponse,
)
from apps.backend.app.services import split_group as split_group_service

router = APIRouter(prefix="/travel/shared", tags=["travel"])

_JOIN_RATE_LIMIT_PER_MINUTE = 10
_VIEW_RATE_LIMIT_PER_MINUTE = 20


async def _check_rate_limit(ip: str, key_prefix: str, limit: int) -> None:
    """Generic per-IP rate limiter using the rate-limit cache backend."""
    try:
        from packages.core.cache import get_cache
        from packages.core.cache.keys import RATE_LIMIT

        cache = get_cache()
        key = f"{key_prefix}:{ip}"
        count = await cache.get(key)
        if count is not None and int(count) >= limit:
            raise AppError(ErrorCode.RATE_LIMITED)
        new_count = await cache.increment(key)
        if new_count == 1:
            await cache.set(key, 1, ttl=60)
    except AppError:
        raise
    except Exception:
        # Fail closed on cache errors
        raise AppError(ErrorCode.RATE_LIMITED) from None


@router.get("/{invite_code}", response_model=SharedExpenseResponse)
async def get_shared_expense_view(
    invite_code: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Get sanitized shared expense view for external participants. No auth required."""
    client_ip = _get_real_client_ip(request)
    await _check_rate_limit(client_ip, "shared_view", _VIEW_RATE_LIMIT_PER_MINUTE)

    data = split_group_service.get_shared_expense_view(db, invite_code)
    trip = data["trip"]
    user_name_map = data["user_name_map"]

    expense_items = [
        SharedExpenseItem(
            id=e.id,
            amount=e.amount,
            currency=e.currency,
            amount_cny=e.amount_cny,
            expense_date=e.expense_date,
            payer_name=user_name_map.get(e.user_id, f"User_{e.user_id}"),
        )
        for e in data["expenses"]
    ]

    return SharedExpenseResponse(
        trip_name=trip.name,
        destination=trip.destination,
        departure_date=trip.departure_date,
        return_date=trip.return_date,
        trip_status=trip.status,
        expenses=expense_items,
        participants=[
            SplitParticipantResponse(
                id=p.id,
                group_id=p.group_id,
                name=p.name,
                family_id=p.family_id,
                joined_at=p.joined_at,
            )
            for p in data["participants"]
        ],
    )


@router.post("/{invite_code}/join", response_model=SplitParticipantResponse)
async def join_group(
    invite_code: str,
    req: SplitParticipantCreate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Join a split group via invite code. No auth required. Rate-limited by IP."""
    client_ip = _get_real_client_ip(request)
    await _check_rate_limit(client_ip, "shared_join", _JOIN_RATE_LIMIT_PER_MINUTE)

    participant, _group = split_group_service.join_group(db, invite_code, req.name)
    return SplitParticipantResponse(
        id=participant.id,
        group_id=participant.group_id,
        name=participant.name,
        family_id=participant.family_id,
        joined_at=participant.joined_at,
    )
