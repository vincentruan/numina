"""MCP Tool Registry — centralized metadata SSOT for all MCP tools.

Each tool declares allowed_roles and requires_write upfront.
list_tools_for_role() filters at protocol layer; call_tool() re-checks at enforcement layer.
"""

from dataclasses import dataclass
from typing import Any

_VALID_ROLES = frozenset({"owner", "member", "child", "external_token"})


@dataclass(frozen=True)
class MCPToolMeta:
    name: str
    description: str
    input_schema: dict[str, Any]
    allowed_roles: frozenset[str]
    requires_write: bool


TOOL_REGISTRY: dict[str, MCPToolMeta] = {
    "get_family_overview": MCPToolMeta(
        name="get_family_overview",
        description="获取家庭财务总览：净资产、总资产、总负债、配置占比、近期变化。",
        input_schema={"type": "object", "properties": {}, "required": []},
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    "get_members": MCPToolMeta(
        name="get_members",
        description="查询家庭成员列表。",
        input_schema={"type": "object", "properties": {}, "required": []},
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
        allowed_roles=frozenset({"owner", "member", "external_token"}),
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
    # ── Smart-tutor skill (Issue #191 — Socratic guidance) ─────────────
    "get_guided_question": MCPToolMeta(
        name="get_guided_question",
        description=(
            "获取一道智能题的完整引导方案：题目内容、引导策略、常见错误模式。"
            "不只是题目本身，还有教师引导计划。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "question_id": {"type": "integer", "description": "题目 ID"},
                "child_id": {"type": "integer", "description": "孩子用户 ID"},
                "topic_id": {"type": "integer", "description": "知识点 ID"},
            },
            "required": ["question_id", "child_id", "topic_id"],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
    "submit_guided_answer": MCPToolMeta(
        name="submit_guided_answer",
        description=(
            "提交孩子在苏格拉底引导过程中的一步回答。AI 判断理解程度并决定"
            "下一步引导策略。返回诊断结果和建议的下一步引导方向。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "question_id": {"type": "integer", "description": "题目 ID"},
                "child_id": {"type": "integer", "description": "孩子用户 ID"},
                "session_id": {"type": "integer", "description": "学习会话 ID"},
                "answer_text": {"type": "string", "description": "孩子的回答文本"},
                "step_number": {
                    "type": "integer",
                    "description": "当前引导步骤编号（从1开始）",
                },
            },
            "required": [
                "question_id",
                "child_id",
                "session_id",
                "answer_text",
                "step_number",
            ],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
    "get_knowledge_bridge": MCPToolMeta(
        name="get_knowledge_bridge",
        description=(
            "获取当前题目到前置知识的桥接路径。返回 prerequisite chain，"
            "每个节点包含掌握状态，帮助教师找到真正的知识断点。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer", "description": "当前知识点 ID"},
                "child_id": {"type": "integer", "description": "孩子用户 ID"},
                "depth": {
                    "type": "integer",
                    "description": "回溯深度（默认2，最大3）",
                    "default": 2,
                },
            },
            "required": ["topic_id", "child_id"],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
    "get_teacher_persona": MCPToolMeta(
        name="get_teacher_persona",
        description=(
            "根据学科和年龄段获取教师人格配置。返回教学风格、语气、策略等。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject": {
                    "type": "string",
                    "description": "学科（math/chinese/english/science）",
                },
                "age_group": {
                    "type": "string",
                    "description": "年龄段（low/mid/high）",
                    "enum": ["low", "mid", "high"],
                },
            },
            "required": ["subject", "age_group"],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
    "record_tutoring_step": MCPToolMeta(
        name="record_tutoring_step",
        description=(
            "记录一次苏格拉底引导交互的步骤数据。包括引导阶段、孩子回答质量、"
            "AI 策略评估。用于后续自适应选题和学情分析。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "integer", "description": "学习会话 ID"},
                "question_id": {"type": "integer", "description": "题目 ID"},
                "step_number": {"type": "integer", "description": "步骤编号"},
                "phase": {
                    "type": "string",
                    "description": "引导阶段",
                    "enum": [
                        "diagnose",
                        "focused_guidance",
                        "prerequisite_retrace",
                        "misconception_correction",
                        "verify",
                        "consolidate",
                    ],
                },
                "child_response_quality": {
                    "type": "string",
                    "description": "孩子回答质量",
                    "enum": ["correct", "partial", "incorrect", "no_response"],
                },
                "ai_strategy": {
                    "type": "string",
                    "description": "AI 使用的引导策略",
                },
                "next_phase": {
                    "type": "string",
                    "description": "下一步引导阶段",
                    "enum": [
                        "focused_guidance",
                        "prerequisite_retrace",
                        "misconception_correction",
                        "verify",
                        "consolidate",
                        "end",
                    ],
                },
            },
            "required": [
                "session_id",
                "question_id",
                "step_number",
                "phase",
                "child_response_quality",
                "next_phase",
            ],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=True,
    ),
    # ── Learning-topic-generator skill (Issue #190) ───────────────────
    "get_taxonomy_topic": MCPToolMeta(
        name="get_taxonomy_topic",
        description=(
            "获取知识点详情（名称、描述、证据标准、评估提示、年龄组、学科、领域）。"
            "通过 topic_key 查询。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic_key": {"type": "string", "description": "知识点唯一标识"},
                "source_taxonomy": {
                    "type": "string",
                    "description": "分类体系名称（可选，默认自动选择）",
                },
            },
            "required": ["topic_key"],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    "get_taxonomy_dependencies": MCPToolMeta(
        name="get_taxonomy_dependencies",
        description=(
            "获取知识点的前置依赖关系列表。返回前置知识点的 topic_key、"
            "依赖强度和原因。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic_key": {"type": "string", "description": "知识点唯一标识"},
            },
            "required": ["topic_key"],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    "list_taxonomy_topics": MCPToolMeta(
        name="list_taxonomy_topics",
        description=(
            "按条件列出知识点索引。支持按学科、领域、年龄组筛选。"
            "返回轻量级列表（id、topic_key、name、subject、domain、age_group）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "学科名称"},
                "domain": {"type": "string", "description": "领域名称（可选）"},
                "age_group": {
                    "type": "string",
                    "enum": ["low", "mid", "high"],
                    "description": "年龄组（可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回数量",
                    "default": 50,
                    "maximum": 200,
                },
            },
            "required": ["subject"],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    "validate_question": MCPToolMeta(
        name="validate_question",
        description=(
            "验证生成的题目是否符合格式要求（L1 格式验证）。"
            "检查题干非空、答案存在、知识点存在、题型特定字段。"
            "返回验证结果和错误详情。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "topic_id": {"type": "integer", "description": "知识点 ID"},
                "question_type": {
                    "type": "string",
                    "enum": [
                        "calculation",
                        "multiple_choice",
                        "fill_blank",
                        "true_false",
                    ],
                    "description": "题目类型",
                },
                "stem": {"type": "string", "description": "题干"},
                "answer": {"type": "object", "description": "答案 JSON"},
                "options": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "选项（仅 multiple_choice）",
                },
                "age_group": {
                    "type": "string",
                    "enum": ["low", "mid", "high"],
                    "description": "目标年龄组",
                },
            },
            "required": [
                "topic_id",
                "question_type",
                "stem",
                "answer",
                "age_group",
            ],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    "get_child_weak_points": MCPToolMeta(
        name="get_child_weak_points",
        description=(
            "获取儿童薄弱知识点列表，按掌握度从低到高排序。"
            "包含知识断点（前置已掌握但当前未掌握的知识点）。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {"type": "integer", "description": "儿童用户 ID"},
                "subject": {
                    "type": "string",
                    "description": "可选：按科目过滤",
                },
                "limit": {
                    "type": "integer",
                    "description": "最大返回数量",
                    "default": 10,
                    "maximum": 100,
                },
            },
            "required": ["child_id"],
        },
        allowed_roles=frozenset({"owner", "member", "external_token"}),
        requires_write=False,
    ),
    # ── Adaptive question selection (Issue #191 Phase 3) ────────────────
    "select_adaptive_question": MCPToolMeta(
        name="select_adaptive_question",
        description=(
            "自适应选题：根据儿童薄弱点、历史表现和难度偏好，推荐最合适的题目。"
            "优先从薄弱知识点选题，避免重复已做过的题目。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "child_id": {"type": "integer", "description": "儿童用户 ID"},
                "topic_id": {
                    "type": "integer",
                    "description": "可选：限定知识点范围",
                },
                "subject": {
                    "type": "string",
                    "description": "可选：按科目过滤（当不指定 topic_id 时）",
                },
                "min_difficulty": {
                    "type": "integer",
                    "description": "最低难度（1-5）",
                    "default": 1,
                    "minimum": 1,
                    "maximum": 5,
                },
                "max_difficulty": {
                    "type": "integer",
                    "description": "最高难度（1-5）",
                    "default": 3,
                    "minimum": 1,
                    "maximum": 5,
                },
                "bloom_level": {
                    "type": "string",
                    "enum": [
                        "remember",
                        "understand",
                        "apply",
                        "analyze",
                        "evaluate",
                        "create",
                    ],
                    "description": "可选：布鲁姆认知层次",
                },
                "exclude_question_ids": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "可选：排除的题目 ID 列表（避免重复）",
                },
            },
            "required": ["child_id"],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
    # ── Hint generation (Issue #191 Phase 4) ────────────────────────────
    "generate_hint": MCPToolMeta(
        name="generate_hint",
        description=(
            "根据儿童的错误模式和薄弱点，生成针对性的引导提示。"
            "不直接给出答案，而是提供思考方向或关联已掌握知识。"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "question_id": {"type": "integer", "description": "题目 ID"},
                "child_id": {"type": "integer", "description": "儿童用户 ID"},
                "error_pattern": {
                    "type": "string",
                    "enum": [
                        "computation",
                        "concept",
                        "reading",
                        "partial",
                        "guessing",
                        "unknown",
                    ],
                    "description": "检测到的错误模式",
                },
                "attempt_number": {
                    "type": "integer",
                    "description": "当前尝试次数（1-5）",
                    "default": 1,
                },
                "hint_type": {
                    "type": "string",
                    "enum": ["conceptual", "procedural", "encouragement", "bridge"],
                    "description": "提示类型（可选，不传则自动选择）",
                },
            },
            "required": ["question_id", "child_id", "error_pattern"],
        },
        allowed_roles=frozenset({"owner", "member", "child", "external_token"}),
        requires_write=False,
    ),
}


def get_tool(name: str) -> MCPToolMeta | None:
    return TOOL_REGISTRY.get(name)


def list_tools_for_role(role: str) -> list[MCPToolMeta]:
    return [meta for meta in TOOL_REGISTRY.values() if role in meta.allowed_roles]


def validate_registry() -> None:
    for name, meta in TOOL_REGISTRY.items():
        if not meta.allowed_roles:
            raise RuntimeError(
                f"MCP tool registry invalid: '{name}' has empty allowed_roles"
            )
        invalid = meta.allowed_roles - _VALID_ROLES
        if invalid:
            raise RuntimeError(
                f"MCP tool registry invalid: '{name}' has unknown roles: {invalid}"
            )
