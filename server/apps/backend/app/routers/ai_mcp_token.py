"""CRUD router for family MCP external API tokens. Owner-only."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.mcp_access_log import MCPAccessLog
from apps.backend.app.models.user import User
from apps.backend.app.schemas.mcp_access_log import (
    MCPAccessLogListResponse,
    MCPAccessLogResponse,
    MCPStatsResponse,
)
from apps.backend.app.schemas.mcp_token import (
    MCPTokenGenerateResponse,
    MCPTokenResponse,
    MCPTokenUpdate,
)
from apps.backend.app.services import mcp_token as token_svc
from apps.backend.app.services.mcp_stats import get_mcp_stats

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
    """Update allow_external, allow_write, allowed_tools, and/or expires_at.

    ``expires_at`` is cleared (set to NULL = never expire) only when the field is
    explicitly present in the request body; omitting it leaves the value unchanged.

    ``allowed_tools``: null resets to all-available, list sets exact whitelist.
    """
    # Build kwargs — only pass allowed_tools if it was explicitly set in the body
    kwargs = {}
    if body.allow_external is not None:
        kwargs["allow_external"] = body.allow_external
    if body.allow_write is not None:
        kwargs["allow_write"] = body.allow_write
    if "allowed_tools" in body.model_fields_set:
        kwargs["allowed_tools"] = body.allowed_tools

    row = token_svc.update_access(
        current_user.family_id,
        db,
        **kwargs,
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


@router.get("/access-logs", response_model=MCPAccessLogListResponse)
def list_access_logs(
    event_type: str | None = Query(None),
    tool_name: str | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPAccessLogListResponse:
    """Paginated access logs for the current family, newest-first."""
    q = db.query(MCPAccessLog).filter(
        MCPAccessLog.family_id == current_user.family_id
    )
    if event_type is not None:
        q = q.filter(MCPAccessLog.event_type == event_type)
    if tool_name is not None:
        q = q.filter(MCPAccessLog.tool_name == tool_name)
    if date_from is not None:
        q = q.filter(MCPAccessLog.created_at >= date_from)
    if date_to is not None:
        q = q.filter(MCPAccessLog.created_at <= date_to)

    total = q.count()
    offset = (page - 1) * page_size
    rows = (
        q.order_by(MCPAccessLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return MCPAccessLogListResponse(
        items=[MCPAccessLogResponse.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats", response_model=MCPStatsResponse)
def get_stats(
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> MCPStatsResponse:
    """Aggregate usage stats for the current family (default: last 7 days)."""
    return get_mcp_stats(
        current_user.family_id,
        db,
        date_from=date_from,
        date_to=date_to,
    )
