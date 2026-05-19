"""ChallengeGrant router for parent and child endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user, require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.challenge_grant import (
    ChallengeGrantCreate,
    ChallengeGrantResponse,
    ChallengeListResponse,
    ChildChallengeListResponse,
    ChildChallengeResponse,
)
from apps.backend.app.services import challenge_grants as svc

router = APIRouter(prefix="/challenges", tags=["challenges"])


# ---------------------------------------------------------------------------
# Parent endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=ChallengeListResponse)
def list_challenges(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List all family challenges."""
    items = svc.list_family_challenges(db, user.family_id)
    return ChallengeListResponse(items=[ChallengeGrantResponse.model_validate(c) for c in items])


@router.post("", response_model=ChallengeGrantResponse, status_code=201)
def create_challenge(
    req: ChallengeGrantCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Create a new challenge for a child."""
    try:
        challenge = svc.create_challenge(
            db, user, req.child_user_id, req.target_type, req.target_value,
            req.deadline, req.message, req.chore_template_id,
        )
        return ChallengeGrantResponse.model_validate(challenge)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None  # noqa: allow-http-exception


@router.post("/{challenge_id}/cancel", response_model=ChallengeGrantResponse)
def cancel_challenge(
    challenge_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Cancel an active challenge."""
    try:
        challenge = svc.cancel_challenge(db, user, challenge_id)
        return ChallengeGrantResponse.model_validate(challenge)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from None  # noqa: allow-http-exception


# ---------------------------------------------------------------------------
# Child endpoints (mounted at /child/challenges)
# ---------------------------------------------------------------------------

child_router = APIRouter(prefix="/child/challenges", tags=["child-challenges"])


@child_router.get("/active", response_model=ChildChallengeListResponse)
def list_active_challenges(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    """List child's active challenges for progress display."""
    items = svc.list_child_active_challenges(db, user.id, user.family_id)
    return ChildChallengeListResponse(items=[ChildChallengeResponse.model_validate(c) for c in items])