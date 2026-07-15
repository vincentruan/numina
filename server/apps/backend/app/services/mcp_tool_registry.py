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
    # Domain-specific report tools — named to avoid collision with DeerFlow's
    # built-in read_file/write_file sandbox tools.  The built-in tools operate
    # on absolute virtual paths (/mnt/user-data/...) for general file I/O;
    # these tools are scoped to the tenant report directory and accept simple
    # filenames, so the agent should always prefer these for report operations.
    "write_numina_report": MCPToolMeta(
        name="write_numina_report",
        description="将内容写入租户报告目录的文件。仅支持 markdown 报告文件。",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "文件名，必须符合 report_*.md 格式",
                    "pattern": "^report_[a-zA-Z0-9_-]+\\.md$",
                },
                "content": {
                    "type": "string",
                    "description": "文件内容（markdown 格式）",
                },
            },
            "required": ["filename", "content"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=True,
    ),
    "read_numina_report": MCPToolMeta(
        name="read_numina_report",
        description="读取租户报告目录中的文件内容。仅支持 markdown 报告文件。",
        input_schema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "文件名，必须符合 report_*.md 格式",
                    "pattern": "^report_[a-zA-Z0-9_-]+\\.md$",
                },
            },
            "required": ["filename"],
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
