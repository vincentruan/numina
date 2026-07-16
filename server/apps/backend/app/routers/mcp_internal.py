"""Internal MCP SSE endpoint — agent → backend tool calls for family data."""
import logging

from fastapi import APIRouter, Header, Request
from starlette.responses import Response

from apps.backend.app.config import settings
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.mcp_session import MCPSession

router = APIRouter(prefix="/internal/mcp", tags=["internal-mcp"])
logger = logging.getLogger(__name__)

# Module-level shared transport — handles session routing internally.
# Both the SSE GET and messages POST endpoints must share the same instance
# so that SseServerTransport can route POST bodies to the correct SSE session
# via the session_id query parameter it embeds in the endpoint URL.
_transport = None


def _get_transport():
    global _transport
    if _transport is None:
        from mcp.server.sse import SseServerTransport

        _transport = SseServerTransport(endpoint="/api/v1/internal/mcp/messages")
    return _transport


def _verify_agent_token(token: str | None) -> None:
    if not settings.AGENT_INTERNAL_TOKEN:
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE, "agent token not configured")
    if not token or token != settings.AGENT_INTERNAL_TOKEN:
        raise AppError(ErrorCode.AUTH_INVALID_CREDENTIALS, "invalid agent token")


class MCPSSEResponse(Response):
    """Custom ASGI response that delegates to MCP SSE transport."""

    def __init__(self, session: MCPSession, family_id: str):
        self.session = session
        self.family_id = family_id
        super().__init__()

    async def __call__(self, scope, receive, send):
        transport = _get_transport()
        try:
            async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
                init_opts = self.session.server.create_initialization_options()
                await self.session.server.run(read_stream, write_stream, init_opts)
        except Exception as e:
            logger.error("[mcp_sse] family=%s connection error: %s", self.family_id, e)


class MCPMessageResponse(Response):
    """Custom ASGI response that delegates POST body to the shared transport."""

    async def __call__(self, scope, receive, send):
        transport = _get_transport()
        await transport.handle_post_message(scope, receive, send)


@router.get("/{family_id}/sse")
async def mcp_sse(
    family_id: str,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
    x_family_id: str | None = Header(None, alias="X-Family-Id"),
    x_caller_user_id: str | None = Header(None, alias="X-Caller-User-Id"),
    x_thread_id: str | None = Header(None, alias="X-Thread-Id"),
):
    """SSE endpoint that speaks MCP protocol for the given family_id."""
    _verify_agent_token(x_agent_token)
    if x_family_id and x_family_id != family_id:
        raise AppError(ErrorCode.FORBIDDEN, "family_id mismatch")
    if not x_caller_user_id:
        raise AppError(ErrorCode.FORBIDDEN, "missing caller_user_id")

    from apps.backend.app.database import SessionLocal
    from apps.backend.app.models.user import User

    with SessionLocal() as db:
        user = db.query(User).filter(User.id == x_caller_user_id).first()
        if not user:
            logger.warning(
                "[mcp_sse] caller not found: family=%s caller_user_id=%s",
                family_id, x_caller_user_id,
            )
            raise AppError(ErrorCode.FORBIDDEN, "caller invalid")
        if not user.is_active:
            logger.warning(
                "[mcp_sse] caller inactive: family=%s caller_user_id=%s",
                family_id, x_caller_user_id,
            )
            raise AppError(ErrorCode.FORBIDDEN, "caller invalid")
        if str(user.family_id) != str(family_id):
            logger.warning(
                "[mcp_sse] caller cross-family: family=%s caller_user_id=%s actual_family=%s",
                family_id, x_caller_user_id, user.family_id,
            )
            raise AppError(ErrorCode.FORBIDDEN, "caller invalid")
        if user.role == "child":
            logger.warning(
                "[mcp_sse] child caller rejected: family=%s caller_user_id=%s",
                family_id, x_caller_user_id,
            )
            raise AppError(ErrorCode.FORBIDDEN, "caller invalid")

        caller_role = user.role

    session = MCPSession(
        family_id=family_id,
        caller_user_id=x_caller_user_id,
        caller_role=caller_role,
        thread_id=x_thread_id,
    )
    return MCPSSEResponse(session=session, family_id=family_id)


@router.post("/messages")
async def mcp_messages(
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
):
    """Inbound messages channel — delegates to SseServerTransport.handle_post_message."""
    _verify_agent_token(x_agent_token)
    return MCPMessageResponse()
