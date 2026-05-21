"""Internal MCP SSE endpoint — agent → backend tool calls for family data."""
import logging

from fastapi import APIRouter, Header, HTTPException, Request
from starlette.responses import Response

from apps.backend.app.config import settings
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
        raise HTTPException(status_code=503, detail="agent token not configured")
    if not token or token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid agent token")


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
):
    """SSE endpoint that speaks MCP protocol for the given family_id."""
    _verify_agent_token(x_agent_token)
    session = MCPSession(family_id=family_id)
    return MCPSSEResponse(session=session, family_id=family_id)


@router.post("/messages")
async def mcp_messages(
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
):
    """Inbound messages channel — delegates to SseServerTransport.handle_post_message."""
    _verify_agent_token(x_agent_token)
    return MCPMessageResponse()
