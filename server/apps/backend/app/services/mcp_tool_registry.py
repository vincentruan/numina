"""MCP Tool Registry — centralized metadata SSOT for all MCP tools.

Each tool declares allowed_roles and requires_write upfront.
list_tools_for_role() filters at protocol layer; call_tool() re-checks at enforcement layer.
"""

from dataclasses import dataclass
from typing import Any

_VALID_ROLES = frozenset({"owner", "member", "child"})


@dataclass(frozen=True)
class MCPToolMeta:
    name: str
    description: str
    input_schema: dict[str, Any]
    allowed_roles: frozenset[str]
    requires_write: bool


_REGISTRY: dict[str, MCPToolMeta] = {
    "get_family_overview": MCPToolMeta(
        name="get_family_overview",
        description="获取家庭财务总览：净资产、总资产、总负债、配置占比、近期变化。",
        input_schema={"type": "object", "properties": {}, "required": []},
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_assets": MCPToolMeta(
        name="get_assets",
        description="查询家庭资产列表。支持按类别过滤、限制条数。",
        input_schema={
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "资产类别（可选）"},
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_liabilities": MCPToolMeta(
        name="get_liabilities",
        description="查询家庭负债列表（贷款、信用卡等）。",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
            "required": [],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_members": MCPToolMeta(
        name="get_members",
        description="查询家庭成员列表。",
        input_schema={"type": "object", "properties": {}, "required": []},
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_recent_alerts": MCPToolMeta(
        name="get_recent_alerts",
        description="查询家庭最近的资产预警和处置建议。",
        input_schema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": [],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
}


def get_tool(name: str) -> MCPToolMeta | None:
    return _REGISTRY.get(name)


def list_tools_for_role(role: str) -> list[MCPToolMeta]:
    return [meta for meta in _REGISTRY.values() if role in meta.allowed_roles]


def validate_registry() -> None:
    for name, meta in _REGISTRY.items():
        if not meta.allowed_roles:
            raise RuntimeError(
                f"MCP tool registry invalid: '{name}' has empty allowed_roles"
            )
        invalid = meta.allowed_roles - _VALID_ROLES
        if invalid:
            raise RuntimeError(
                f"MCP tool registry invalid: '{name}' has unknown roles: {invalid}"
            )
