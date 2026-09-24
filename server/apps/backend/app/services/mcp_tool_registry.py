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
    # Resolved-3 (U5 cleanup): the domain-specific ``write_numina_report`` /
    # ``read_numina_report`` MCP tools were deleted — asset-report now uses
    # DeerFlow's native ``write_file``/``read_file``/``str_replace`` sandbox
    # tools (NuminaLocalSandboxProvider, family-scoped) via the ``asset-report``
    # skill. No MCP report tools remain.
    #
    # #11 (U8 follow-up): batch-write tools for the import-parse pipeline.
    # The agent parses a financial document into structured items and calls
    # these to persist them in one shot (plan U8 step 4-5). They reuse the
    # service-layer ``create_asset``/``create_liability`` paths so validation,
    # notification dispatch, and snowflake IDs match the REST endpoints.
    # ``requires_write=True`` → owner/member only (no child role).
    "import_assets_batch": MCPToolMeta(
        name="import_assets_batch",
        description=(
            "批量创建金融资产条目（导入持仓用）。一次写入多条，返回每条的创建"
            "结果（id/temp_id/status）。category_hint 自动匹配系统分类"
            "（股票/基金/债券/存款/理财产品/数字货币/其他），匹配不到则跳过该条。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "待创建的资产条目列表",
                    "items": {
                        "type": "object",
                        "properties": {
                            "temp_id": {
                                "type": "string",
                                "description": "调用方生成的临时 ID，回传以便对应结果",
                            },
                            "name": {"type": ["string", "null"]},
                            "asset_type": {
                                "type": ["string", "null"],
                                "description": "固定 financial（导入仅处理金融资产）",
                            },
                            "category_hint": {
                                "type": ["string", "null"],
                                "description": "股票|基金|债券|存款|理财产品|数字货币|其他",
                            },
                            "current_value": {"type": ["number", "null"]},
                            "currency": {"type": ["string", "null"], "default": "CNY"},
                            "quantity": {"type": ["number", "null"]},
                            "notes": {"type": ["string", "null"]},
                        },
                        "required": ["temp_id"],
                    },
                }
            },
            "required": ["items"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=True,
    ),
    "import_liabilities_batch": MCPToolMeta(
        name="import_liabilities_batch",
        description=(
            "批量创建负债条目（贷款等）。一次写入多条，返回每条创建结果。"
            "category 为负债类型字符串（如 mortgage/car_loan/other）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "temp_id": {"type": "string"},
                            "category": {"type": "string"},
                            "name": {"type": "string"},
                            "original_amount": {"type": "number"},
                            "remaining_amount": {"type": "number"},
                            "monthly_payment": {"type": "number"},
                            "interest_rate": {"type": "number"},
                            "start_date": {
                                "type": "string",
                                "description": "YYYY-MM-DD",
                            },
                            "end_date": {"type": "string", "description": "YYYY-MM-DD"},
                            "institution": {"type": "string"},
                            "currency": {"type": "string", "default": "CNY"},
                            "notes": {"type": "string"},
                        },
                        "required": [
                            "temp_id",
                            "category",
                            "name",
                            "original_amount",
                            "remaining_amount",
                        ],
                    },
                }
            },
            "required": ["items"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=True,
    ),
    "import_credit_cards_batch": MCPToolMeta(
        name="import_credit_cards_batch",
        description=(
            "批量创建信用卡负债条目（category 固定为 credit_card 的 import_liabilities_batch 特化）。"
            "用于导入信用卡账单。original_amount=额度/账单金额，remaining_amount=未还金额。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "temp_id": {"type": "string"},
                            "name": {
                                "type": "string",
                                "description": "信用卡名称（如招商银行信用卡）",
                            },
                            "original_amount": {
                                "type": "number",
                                "description": "额度或账单金额",
                            },
                            "remaining_amount": {
                                "type": "number",
                                "description": "未还金额",
                            },
                            "monthly_payment": {"type": "number"},
                            "interest_rate": {"type": "number"},
                            "end_date": {
                                "type": "string",
                                "description": "到期日 YYYY-MM-DD",
                            },
                            "institution": {"type": "string"},
                            "currency": {"type": "string", "default": "CNY"},
                            "notes": {"type": "string"},
                        },
                        "required": [
                            "temp_id",
                            "name",
                            "original_amount",
                            "remaining_amount",
                        ],
                    },
                }
            },
            "required": ["items"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=True,
    ),
    "get_child_literacy_profile": MCPToolMeta(
        name="get_child_literacy_profile",
        description=(
            "获取家庭中孩子的财商启蒙档案：昵称、年龄段、当前徽章等级、"
            "累计场景完成数、本周周报状态。支持按 child_id 过滤。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {
                    "type": "string",
                    "description": "孩子的 user ID（可选，不传则返回所有孩子）",
                },
            },
            "required": [],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_literacy_weekly_data": MCPToolMeta(
        name="get_literacy_weekly_data",
        description=(
            "获取指定孩子某周的财商启蒙数据：家务完成率、星星币收支、"
            "场景完成情况、徽章变化、与上周的趋势对比。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {
                    "type": "string",
                    "description": "孩子的 user ID",
                },
                "week_start": {
                    "type": "string",
                    "description": "周起始日 ISO 格式（Sunday），不传则返回最近一周",
                },
            },
            "required": ["child_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_travel_trips": MCPToolMeta(
        name="get_travel_trips",
        description="查询家庭旅行列表。支持按状态过滤、限制条数。",
        input_schema={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "description": "行程状态过滤 (planning/active/settled/archived)",
                },
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
    "get_travel_expenses": MCPToolMeta(
        name="get_travel_expenses",
        description="查询指定行程的费用明细。支持按类别过滤。",
        input_schema={
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "行程ID"},
                "limit": {
                    "type": "integer",
                    "default": 50,
                    "minimum": 1,
                    "maximum": 200,
                },
            },
            "required": ["trip_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_travel_split_balances": MCPToolMeta(
        name="get_travel_split_balances",
        description="查询指定行程的分摊余额和结算状态。仅返回家庭自身数据，不含外部参与者信息。",
        input_schema={
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "行程ID"},
            },
            "required": ["trip_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    # ── Learning-tutor skill (Task 4 SDD) ──────────────────────────────
    "get_learning_topic": MCPToolMeta(
        name="get_learning_topic",
        description=(
            "获取学习知识点详情及孩子的掌握程度。返回知识点名称、描述、证据标准、"
            "评估提示，以及孩子当前的掌握级别。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer", "description": "知识点 ID"},
                "child_id": {"type": "integer", "description": "孩子用户 ID"},
            },
            "required": ["topic_id", "child_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "get_child_learning_profile": MCPToolMeta(
        name="get_child_learning_profile",
        description=(
            "获取孩子的学习档案统计：已掌握、学习中、可用的知识点数量，"
            "以及最近的学习活动。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {"type": "integer", "description": "孩子用户 ID"},
                "subject": {"type": "string", "description": "可选：按科目过滤"},
            },
            "required": ["child_id"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=False,
    ),
    "record_learning_result": MCPToolMeta(
        name="record_learning_result",
        description=("记录 AI 辅导评估结果。更新学习进度、触发金币/徽章奖励。"),
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "学习会话 ID"},
                "evaluation": {
                    "type": "object",
                    "description": "评估结果 JSON",
                    "properties": {
                        "evidence_results": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "evidence": {"type": "string"},
                                    "met": {"type": "boolean"},
                                    "notes": {"type": "string"},
                                },
                                "required": ["evidence", "met"],
                            },
                        },
                        "overall_score": {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "recommendation": {
                            "type": "string",
                            "enum": ["mastered", "needs_review", "keep_learning"],
                        },
                    },
                    "required": ["evidence_results", "overall_score", "recommendation"],
                },
            },
            "required": ["session_id", "evaluation"],
        },
        allowed_roles=frozenset({"owner", "member"}),
        requires_write=True,
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
