"""CRUD router for family MCP external API tokens. Owner-only."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.mcp_token import (
    MCPTokenGenerateResponse,
    MCPTokenResponse,
    MCPTokenUpdate,
)
from apps.backend.app.services import mcp_token as token_svc

router = APIRouter(prefix="/ai/mcp-token", tags=["ai-mcp-token"])


@router.get("", response_model=MCPTokenResponse)
def get_token(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPTokenResponse:
    """Return token metadata. 404 if no active token exists."""
    row = token_svc.get_active_token(current_user.family_id, db)
    if row is None:
        raise AppError(ErrorCode.NOT_FOUND)
    return MCPTokenResponse.model_validate(row)


@router.post("", response_model=MCPTokenGenerateResponse, status_code=201)
def generate_token(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPTokenGenerateResponse:
    """Generate a new token (or rotate existing). Returns plaintext **once**."""
    plaintext, row = token_svc.generate_token(current_user.family_id, db)
    db.commit()

    base = MCPTokenResponse.model_validate(row)
    return MCPTokenGenerateResponse(
        **base.model_dump(),
        token=plaintext,
    )


@router.patch("", response_model=MCPTokenResponse)
def update_token(
    body: MCPTokenUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPTokenResponse:
    """Update allow_external, allow_write, and/or expires_at.

    ``expires_at`` is cleared (set to NULL = never expire) only when the field is
    explicitly present in the request body; omitting it leaves the value unchanged.
    """
    row = token_svc.update_access(
        current_user.family_id,
        db,
        allow_external=body.allow_external,
        allow_write=body.allow_write,
    )
    if "expires_at" in body.model_fields_set:
        row.expires_at = body.expires_at
    db.commit()
    db.refresh(row)
    return MCPTokenResponse.model_validate(row)


@router.delete("", status_code=204)
def delete_token(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> Response:
    """Revoke (soft-deactivate) the active token."""
    token_svc.revoke_token(current_user.family_id, db)
    db.commit()
    return Response(status_code=204)
