"""Public MCP SSE endpoint — external clients authenticate via API Token."""

import asyncio
import contextlib
import threading

from fastapi import APIRouter, Query, Request
from starlette.responses import Response

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.mcp_audit import write_mcp_access_log
from apps.backend.app.services.mcp_session import MCPSession
from packages.core.logging import get_logger
from packages.core.settings import settings

router = APIRouter(prefix="/mcp/public", tags=["mcp-public"])
logger = get_logger(__name__)


async def _check_mcp_rate_limit(token_prefix: str, client_ip: str) -> None:
    """Per-token rate limit: 30 req/min keyed by (token_prefix, client_ip).

    Applied AFTER token validation so invalid tokens don't consume slots.
    Raises AppError(429) when limit is exceeded.
    """
    from packages.core.cache import get_cache
    from packages.core.cache.keys import RATE_LIMIT

    cache = get_cache()
    key = f"{RATE_LIMIT}:mcp_public:{token_prefix}:{client_ip}"
    count = await cache.increment(key, ttl=60)
    limit = settings.MCP_PUBLIC_RATE_LIMIT_PER_MINUTE
    if count > limit:
        raise AppError(ErrorCode.RATE_LIMITED)

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
        import json as _json

        raw_tools = row.allowed_tools
        parsed_tools = _json.loads(raw_tools) if raw_tools else None
        result = (
            {
                "allow_external": row.allow_external,
                "allow_write": row.allow_write,
                "allowed_tools": parsed_tools,
                "is_active": row.is_active,
                "token_id": row.id,
            },
            str(synthetic_user.id),
        )
        db.commit()
        return result


class PublicMCPSSEResponse(Response):
    """Custom ASGI response that delegates to the public MCP SSE transport."""

    def __init__(self, session: MCPSession, family_id: str, audit_ctx: dict | None = None):
        self.session = session
        self.family_id = family_id
        self.audit_ctx = audit_ctx or {}
        super().__init__()

    async def __call__(self, scope, receive, send):
        transport = _get_public_transport()
        # Write connect event
        if self.audit_ctx:
            write_mcp_access_log(
                family_id=int(self.audit_ctx.get("family_id", 0)),
                token_id=self.audit_ctx.get("token_id"),
                event_type="connect",
                status="success",
                client_ip=self.audit_ctx.get("client_ip", "unknown"),
                user_agent=self.audit_ctx.get("user_agent"),
            )
        try:
            async with transport.connect_sse(scope, receive, send) as (
                read_stream,
                write_stream,
            ):
                init_opts = self.session.server.create_initialization_options()
                await self.session.server.run(read_stream, write_stream, init_opts)
        except Exception:
            logger.exception("[mcp_public] family=%s connection error", self.family_id)
        finally:
            # Best-effort disconnect event
            if self.audit_ctx:
                with contextlib.suppress(Exception):
                    write_mcp_access_log(
                        family_id=int(self.audit_ctx.get("family_id", 0)),
                        token_id=self.audit_ctx.get("token_id"),
                        event_type="disconnect",
                        status="success",
                        client_ip=self.audit_ctx.get("client_ip", "unknown"),
                        user_agent=self.audit_ctx.get("user_agent"),
                    )


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

    # Per-token rate limit (after validation so invalid tokens don't consume slots)
    client_ip = request.client.host if request.client else "unknown"
    await _check_mcp_rate_limit(raw_token[:8], client_ip)

    # Build audit context for connect/disconnect events
    user_agent = request.headers.get("user-agent", "")[:512]
    audit_ctx = {
        "family_id": family_id,
        "token_id": token_info.get("token_id"),
        "client_ip": client_ip,
        "user_agent": user_agent,
    }

    # Build audit callback for tool_call events
    def _audit_tool_call(
        *, event_type: str, tool_name: str, status: str,
        duration_ms: int = 0, args_digest: dict | None = None,
        error_code: str | None = None,
    ) -> None:
        write_mcp_access_log(
            family_id=int(family_id),
            token_id=token_info.get("token_id"),
            event_type=event_type,
            tool_name=tool_name,
            status=status,
            duration_ms=duration_ms,
            client_ip=client_ip,
            user_agent=user_agent,
            args_digest=args_digest,
            error_code=error_code,
        )

    session = MCPSession(
        family_id=family_id,
        caller_user_id=synthetic_user_id,
        caller_role="external_token",
        allow_write=token_info["allow_write"],
        allowed_tools=token_info["allowed_tools"],
        audit_callback=_audit_tool_call,
    )
    return PublicMCPSSEResponse(session=session, family_id=family_id, audit_ctx=audit_ctx)


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

    # Per-token rate limit (after validation)
    _client_ip = request.client.host if request.client else "unknown"
    await _check_mcp_rate_limit(raw_token[:8], _client_ip)

    return PublicMCPMessageResponse()
