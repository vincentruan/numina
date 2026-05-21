"""MCP Session — family_id-bound tool registry for AI Chat data access."""
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from sqlalchemy.orm import Session

from apps.backend.app.database import SessionLocal
from apps.backend.app.models.user import User

logger = logging.getLogger(__name__)


def _get_owner_user(family_id: str, db: Session) -> User:
    """Return the family's owner user for service-layer authorization."""
    user = (
        db.query(User)
        .filter(User.family_id == family_id, User.role == "owner", User.is_active.is_(True))
        .first()
    )
    if not user:
        user = (
            db.query(User)
            .filter(User.family_id == family_id, User.is_active.is_(True))
            .first()
        )
    if not user:
        raise RuntimeError(f"No active member found for family={family_id}")
    return user


class MCPSession:
    """Per-connection MCP session bound to a single family_id.

    Tenant isolation via __slots__:
    - _family_id is captured at construction and frozen
    - Tool handlers NEVER read family_id from tool args — only from self
    """

    __slots__ = ("_family_id", "_server")

    def __init__(self, family_id: str) -> None:
        self._family_id = family_id
        self._server = Server(f"numina-family-{family_id}")
        self._register_tools()

    @property
    def family_id(self) -> str:
        return self._family_id

    @property
    def server(self) -> Server:
        return self._server

    def _register_tools(self) -> None:
        server = self._server

        @server.list_tools()
        async def _list_tools() -> list[Tool]:
            return await self.list_tools()

        @server.call_tool()
        async def _call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
            return await self.call_tool(name, arguments)

    async def list_tools(self) -> list[Tool]:
        return [
            Tool(
                name="get_family_overview",
                description="获取家庭财务总览：净资产、总资产、总负债、配置占比、近期变化。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="get_assets",
                description="查询家庭资产列表。支持按类别过滤、限制条数。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "资产类别（可选）"},
                        "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_liabilities",
                description="查询家庭负债列表（贷款、信用卡等）。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 100},
                    },
                    "required": [],
                },
            ),
            Tool(
                name="get_members",
                description="查询家庭成员列表。",
                inputSchema={"type": "object", "properties": {}, "required": []},
            ),
            Tool(
                name="get_recent_alerts",
                description="查询家庭最近的资产预警和处置建议。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
                    },
                    "required": [],
                },
            ),
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # SECURITY: ignore any family_id in arguments — always use bound self._family_id
        from apps.backend.app.services import asset as asset_service
        from apps.backend.app.services import dashboard as dashboard_service
        from apps.backend.app.services import family as family_service
        from apps.backend.app.services import liability as liability_service

        with SessionLocal() as db:
            user = _get_owner_user(self._family_id, db)
            try:
                if name == "get_family_overview":
                    data = dashboard_service.get_overview(db, user)
                elif name == "get_assets":
                    category = arguments.get("category")
                    limit = int(arguments.get("limit", 20))
                    data = asset_service.list_assets_for_family(
                        db, self._family_id, category=category, limit=limit
                    )
                elif name == "get_liabilities":
                    limit = int(arguments.get("limit", 20))
                    data = liability_service.list_liabilities_for_family(
                        db, self._family_id, limit=limit
                    )
                elif name == "get_members":
                    data = family_service.list_members(db, self._family_id)
                elif name == "get_recent_alerts":
                    limit = int(arguments.get("limit", 10))
                    data = dashboard_service.get_recent_alerts(db, user, limit=limit)
                else:
                    raise ValueError(f"Unknown tool: {name}")

                logger.info(
                    "[mcp_session] family=%s tool=%s args=%s ok",
                    self._family_id, name, arguments,
                )
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, default=str))]
            except Exception as e:
                logger.error(
                    "[mcp_session] family=%s tool=%s failed: %s",
                    self._family_id, name, e,
                )
                return [TextContent(type="text", text=json.dumps({"error": "查询失败，请稍后重试"}, ensure_ascii=False))]