"""MCP Session — caller-bound tool registry for AI Chat data access.

Tenant + caller isolation via __slots__:
- _family_id, _caller_user_id, _caller_role are captured at construction and frozen
- Tool handlers NEVER read family_id/caller from tool args — only from self
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import TextContent, Tool
from sqlalchemy.orm import Session

from apps.backend.app.database import SessionLocal
from apps.backend.app.models.user import User

logger = logging.getLogger(__name__)


def _get_caller_user(family_id: str, caller_user_id: str, db: Session) -> User:
    """Return the caller user, validating family membership and active status."""
    user = (
        db.query(User)
        .filter(User.id == caller_user_id)
        .first()
    )
    if not user or not user.is_active or str(user.family_id) != str(family_id):
        raise RuntimeError(
            f"caller invalid: user_id={caller_user_id} family={family_id}"
        )
    return user


class MCPSession:
    """Per-connection MCP session bound to a single family_id and caller.

    Tenant + caller isolation via __slots__:
    - _family_id, _caller_user_id, _caller_role are frozen at construction
    - Tool handlers NEVER read these from tool args — only from self
    """

    __slots__ = ("_family_id", "_caller_user_id", "_caller_role", "_server")

    def __init__(self, family_id: str, caller_user_id: str, caller_role: str) -> None:
        if not family_id:
            raise ValueError("family_id must not be empty")
        if not caller_user_id:
            raise ValueError("caller_user_id must not be empty")
        if not caller_role:
            raise ValueError("caller_role must not be empty")
        self._family_id = family_id
        self._caller_user_id = caller_user_id
        self._caller_role = caller_role
        self._server = Server(f"numina-family-{family_id}")
        self._register_tools()

    @property
    def family_id(self) -> str:
        return self._family_id

    @property
    def caller_user_id(self) -> str:
        return self._caller_user_id

    @property
    def caller_role(self) -> str:
        return self._caller_role

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
        from apps.backend.app.services.mcp_tool_registry import list_tools_for_role

        return [
            Tool(
                name=meta.name,
                description=meta.description,
                inputSchema=meta.input_schema,
            )
            for meta in list_tools_for_role(self._caller_role)
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> list[TextContent]:
        # SECURITY: ignore any family_id/caller_user_id/role in arguments — slots are the only truth
        from apps.backend.app.services import asset as asset_service
        from apps.backend.app.services import dashboard as dashboard_service
        from apps.backend.app.services import family as family_service
        from apps.backend.app.services import liability as liability_service
        from apps.backend.app.services.mcp_tool_registry import get_tool

        meta = get_tool(name)
        if not meta or self._caller_role not in meta.allowed_roles:
            logger.warning(
                "[mcp_session] permission_denied family=%s caller_user_id=%s caller_role=%s attempted_tool=%s",
                self._family_id,
                self._caller_user_id,
                self._caller_role,
                name,
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "error": "permission_denied",
                            "retryable": False,
                            "reason": "该工具对当前角色不可用",
                        },
                        ensure_ascii=False,
                    ),
                )
            ]

        with SessionLocal() as db:
            user = _get_caller_user(self._family_id, self._caller_user_id, db)
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
                    "[mcp_session] family=%s caller_user_id=%s caller_role=%s tool=%s args=%s ok",
                    self._family_id,
                    self._caller_user_id,
                    self._caller_role,
                    name,
                    arguments,
                )
                return [TextContent(type="text", text=json.dumps(data, ensure_ascii=False, default=str))]
            except Exception as e:
                logger.error(
                    "[mcp_session] family=%s caller_user_id=%s caller_role=%s tool=%s failed: %s",
                    self._family_id,
                    self._caller_user_id,
                    self._caller_role,
                    name,
                    e,
                )
                return [TextContent(type="text", text=json.dumps({"error": "查询失败，请稍后重试"}, ensure_ascii=False))]
