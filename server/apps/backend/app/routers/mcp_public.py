"""Public MCP SSE endpoint — external clients authenticate via API Token."""

import asyncio
import threading

from fastapi import APIRouter, Query, Request
from starlette.responses import Response

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.mcp_session import MCPSession
from packages.core.logging import get_logger

router = APIRouter(prefix="/mcp/public", tags=["mcp-public"])
logger = get_logger(__name__)

# Separate transport instance for the public path — avoids cross-contamination
# with the internal transport's session routing.
_public_transport = None
_transport_lock = threading.Lock()


def _get_public_transport():
    global _public_transport
    if _public_transport is None:
        with _transport_lock:
            if _public_transport is None:
                from mcp.server.sse import SseServerTransport

                _public_transport = SseServerTransport(endpoint="/api/v1/mcp/public/messages")
    return _public_transport


def _extract_token(request: Request) -> tuple[str | None, bool]:
    """Extract token from Bearer header or query param.

    Returns ``(token, from_query_param)``.
    """
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip(), False

    token = request.query_params.get("token")
    if token:
        return token, True

    return None, False


def _validate_and_resolve(family_id: str, raw_token: str):
    """Validate the token and return the synthetic user.

    Raises AppError on failure. Returns ``(token_row, synthetic_user_id)``.
    """
    from apps.backend.app.database import SessionLocal
    from apps.backend.app.models.user import User
    from apps.backend.app.services import mcp_token as token_svc

    with SessionLocal() as db:
        row = token_svc.verify_token(int(family_id), raw_token, db)
        if row is None:
            # Distinguish expired vs invalid — try to find the row
            from apps.backend.app.models.family_mcp_token import FamilyMCPToken

            prefix = raw_token[:8]
            existing = (
                db.query(FamilyMCPToken)
                .filter(
                    FamilyMCPToken.family_id == int(family_id),
                    FamilyMCPToken.token_prefix == prefix,
                )
                .first()
            )
            if existing is not None and not existing.is_active:
                raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "token revoked")
            if existing is not None and existing.expires_at is not None:
                from datetime import UTC, datetime

                if datetime.now(UTC) > (
                    existing.expires_at
                    if existing.expires_at.tzinfo
                    else existing.expires_at.replace(tzinfo=UTC)
                ):
                    raise AppError(ErrorCode.AUTH_TOKEN_EXPIRED, "token expired")
            raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "invalid token")

        if not row.allow_external:
            raise AppError(ErrorCode.FORBIDDEN, "external access not enabled")

        # Resolve the synthetic user
        from packages.core.roles import UserRole

        synthetic_user = (
            db.query(User)
            .filter(
                User.family_id == int(family_id),
                User.role == UserRole.EXTERNAL_TOKEN,
            )
            .first()
        )
        if synthetic_user is None:
            raise AppError(ErrorCode.FORBIDDEN, "synthetic user not found")

        # Capture what we need before session close (objects detach)
        result = (
            {
                "allow_external": row.allow_external,
                "allow_write": row.allow_write,
                "is_active": row.is_active,
            },
            str(synthetic_user.id),
        )
        db.commit()
        return result


class PublicMCPSSEResponse(Response):
    """Custom ASGI response that delegates to the public MCP SSE transport."""

    def __init__(self, session: MCPSession, family_id: str):
        self.session = session
        self.family_id = family_id
        super().__init__()

    async def __call__(self, scope, receive, send):
        transport = _get_public_transport()
        try:
            async with transport.connect_sse(scope, receive, send) as (
                read_stream,
                write_stream,
            ):
                init_opts = self.session.server.create_initialization_options()
                await self.session.server.run(read_stream, write_stream, init_opts)
        except Exception:
            logger.exception("[mcp_public] family=%s connection error", self.family_id)


class PublicMCPMessageResponse(Response):
    """Custom ASGI response that delegates POST body to the public transport."""

    async def __call__(self, scope, receive, send):
        transport = _get_public_transport()
        await transport.handle_post_message(scope, receive, send)


@router.get("/{family_id}/sse")
async def mcp_public_sse(
    family_id: str,
    request: Request,
    token: str | None = Query(None),
):
    """Public SSE endpoint — token auth via Bearer header or query param."""
    raw_token, from_query = _extract_token(request)
    if not raw_token:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "missing token")

    if from_query:
        logger.warning(
            "[mcp_public] query_param_auth family=%s token_prefix=%s client_ip=%s",
            family_id,
            raw_token[:8],
            request.client.host if request.client else "unknown",
        )

    # Offload sync DB work to thread pool to avoid blocking the event loop
    token_info, synthetic_user_id = await asyncio.to_thread(
        _validate_and_resolve, family_id, raw_token
    )

    session = MCPSession(
        family_id=family_id,
        caller_user_id=synthetic_user_id,
        caller_role="external_token",
        allow_write=token_info["allow_write"],
    )
    return PublicMCPSSEResponse(session=session, family_id=family_id)


@router.post("/messages")
async def mcp_public_messages(
    request: Request,
    token: str | None = Query(None),
):
    """Public messages endpoint — token auth via Bearer header or query param."""
    raw_token, from_query = _extract_token(request)
    if not raw_token:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "missing token")

    if from_query:
        logger.warning(
            "[mcp_public] query_param_auth messages token_prefix=%s client_ip=%s",
            raw_token[:8],
            request.client.host if request.client else "unknown",
        )

    # Offload sync DB work to thread pool to avoid blocking the event loop
    def _validate_post():
        from apps.backend.app.database import SessionLocal
        from apps.backend.app.models.family_mcp_token import FamilyMCPToken
        from apps.backend.app.services import mcp_token as token_svc

        with SessionLocal() as db:
            row = token_svc.verify_token_by_prefix(raw_token, db)
            if row is None:
                # Distinguish expired vs invalid for better error messages
                prefix = raw_token[:8]
                existing = (
                    db.query(FamilyMCPToken)
                    .filter(FamilyMCPToken.token_prefix == prefix)
                    .first()
                )
                if existing is not None and not existing.is_active:
                    raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "token revoked")
                if existing is not None and existing.expires_at is not None:
                    from datetime import UTC, datetime

                    if datetime.now(UTC) > (
                        existing.expires_at
                        if existing.expires_at.tzinfo
                        else existing.expires_at.replace(tzinfo=UTC)
                    ):
                        raise AppError(ErrorCode.AUTH_TOKEN_EXPIRED, "token expired")
                raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "invalid token")

    await asyncio.to_thread(_validate_post)

    return PublicMCPMessageResponse()
