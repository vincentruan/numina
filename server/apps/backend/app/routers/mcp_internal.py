"""Internal MCP SSE endpoint — agent → backend tool calls for family data."""
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session
from starlette.responses import Response

from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.services.mcp_session import MCPSession

router = APIRouter(prefix="/internal/mcp", tags=["internal-mcp"])
logger = logging.getLogger(__name__)


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
        """ASGI entry point - delegate to MCP SSE transport."""
        from mcp.server.sse import SseServerTransport

        transport = SseServerTransport(
            endpoint=f"/api/v1/internal/mcp/{self.family_id}/messages"
        )

        try:
            async with transport.connect_sse(scope, receive, send) as (read_stream, write_stream):
                init_opts = self.session.server.create_initialization_options()
                await self.session.server.run(read_stream, write_stream, init_opts)
        except Exception as e:
            logger.error("[mcp_sse] family=%s connection error: %s", self.family_id, e)


@router.get("/{family_id}/sse")
async def mcp_sse(
    family_id: str,
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
    db: Session = Depends(get_db),
):
    """SSE endpoint that speaks MCP protocol for the given family_id."""
    _verify_agent_token(x_agent_token)

    session = MCPSession(family_id=family_id, db=db)
    return MCPSSEResponse(session=session, family_id=family_id)


@router.post("/{family_id}/messages")
async def mcp_messages(
    family_id: str,
    request: Request,
    x_agent_token: str | None = Header(None, alias="X-Agent-Token"),
):
    """Inbound messages channel for SSE transport — validates token and returns 202."""
    _verify_agent_token(x_agent_token)
    return {"status": "accepted"}