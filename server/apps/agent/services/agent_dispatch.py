"""Agent-first execution entry point — Gateway path.

Replaces the old DeerFlowAdapter path with:
  BackendClient queries → EffectiveConfigBuilder → RunnableConfig
  → make_lead_agent() → astream() → NDJSON events.

No global singleton mutation. No ContextVar. No reload_app_config().
"""

import time
import uuid
from collections.abc import AsyncGenerator, Generator
from typing import Any

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.stream_events import EventStreamBuilder
from packages.core import get_path_manager
from packages.core.effective_config import EffectiveConfigBuilder
from packages.core.logging import get_logger

logger = get_logger(__name__)

# Lazy imports — deerflow and orchestrator may not be available in all environments.
# Module-level names allow patching in tests.
try:
    from deerflow.agents.lead_agent.agent import make_lead_agent
except ImportError:
    make_lead_agent = None

try:
    from deerflow.config.app_config import AppConfig
except ImportError:
    AppConfig = None

try:
    from apps.agent.services.orchestrator import _select_model
except ImportError:
    _select_model = None


# ── Tool Type Mapping: tool_name → (tool_type, display_name, icon) ───────────────────

# Backend is source of truth for tool_type/display_name/icon.
# Frontend toolTypeRegistry only maps tool_type → summaryTemplate.
# This mapping covers known DeerFlow/Numina tools; unknown tools fallback to generic.

TOOL_TYPE_MAP: dict[str, tuple[str, str, str]] = {
    # Asset-related tools
    "query_assets": ("asset_query", "资产查询", "asset"),
    "get_asset_details": ("asset_query", "资产查询", "asset"),
    "list_assets": ("asset_query", "资产查询", "asset"),
    "get_dashboard_overview": ("asset_query", "资产概览", "asset"),
    # Report generation
    "generate_report": ("report_gen", "报告生成", "report"),
    "health_report": ("report_gen", "健康报告", "report"),
    "create_scorecard": ("report_gen", "评分卡生成", "report"),
    # Trend/calculation tools
    "get_dashboard_trend": ("trend_calc", "趋势计算", "trend"),
    "calculate_trend": ("trend_calc", "趋势计算", "trend"),
    "projection": ("trend_calc", "趋势预测", "trend"),
    # Wish/心愿 analysis (family-specific)
    "analyze_wishes": ("wish_analysis", "心愿分析", "wish"),
    "wish_checkup": ("wish_analysis", "心愿分析", "wish"),
    # Liability analysis
    "analyze_liabilities": ("liability_analysis", "负债分析", "liability"),
    "liability_checkup": ("liability_analysis", "负债分析", "liability"),
    # Allocation analysis
    "allocation_drift": ("allocation_analysis", "配置分析", "allocation"),
    "get_allocation": ("allocation_analysis", "配置分析", "allocation"),
}


def _map_tool_type(tool_name: str) -> tuple[str, str, str]:
    """Map tool_name to (tool_type, display_name, icon).

    Returns fallback for unknown tools.
    """
    return TOOL_TYPE_MAP.get(tool_name, ("unknown", tool_name, "tool"))


def _resolve_skills(
    agent_skills: list[str] | None,
    family_enabled_skills: list[dict],
) -> list[dict]:
    """Resolve which skills an agent dispatches with, enforcing R5/R6/R15.

    Branches:
    - ``agent_skills == ["chat"]`` → ``[]`` (R5: AI问答 reserved chat capability,
      pure LLM mode, no business skill catalog injection).
    - ``"*" in agent_skills`` → all of ``family_enabled_skills`` (R6: 数鸣 sentinel).
    - non-empty specific list → intersection with ``family_enabled_skills`` by
      ``skill_id`` (R15: custom agents).
    - ``None`` / ``[]`` → ``[]`` (defensive default).

    The resolved list preserves the original dict shape from BackendClient
    (``{"skill_id": ..., "skill_type": ..., ...}``) so downstream consumers
    (EffectiveConfigBuilder) see the same fields they would without resolution.
    """
    if not agent_skills:
        return []
    # Chat-reserved capability handling must come before the sentinel branch
    # so an agent with skills=["chat"] never accidentally inherits family skills.
    if agent_skills == ["chat"]:
        return []
    if "*" in agent_skills:
        return list(family_enabled_skills)
    allowed = set(agent_skills)
    return [s for s in family_enabled_skills if s.get("skill_id") in allowed]


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    user_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
    reasoning_effort: str | None = None,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events.

    Args:
        agent_id: Agent ID to dispatch
        family_id: Family ID
        user_id: User ID
        thread_id: Conversation thread ID (optional, generated if None)
        message: User message/question
        enable_thinking: Enable extended thinking mode
        reasoning_effort: Thinking depth when enable_thinking=True ("low"|"medium"|"high")
    """
    t_start = time.monotonic()
    task_id = str(uuid.uuid4())
    builder_events = EventStreamBuilder(
        capability_id=f"agent-{agent_id}", task_id=task_id
    )

    # 1. Fetch agent config
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        yield builder_events.error(
            f"获取智能体配置失败: {e}", code="AGENT_CONFIG_ERROR"
        ).to_ndjson()
        return

    if not agent_config.get("is_enabled", True):
        yield builder_events.error("智能体已禁用", code="AGENT_DISABLED").to_ndjson()
        return

    agent_name = agent_config["agent_name"]

    # 2. Fetch AI provider config + skills + MCP in parallel-safe sequence
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        yield builder_events.error(
            f"获取 AI 配置失败: {e}", code="AI_CONFIG_ERROR"
        ).to_ndjson()
        return

    try:
        enabled_skills = await client.get_enabled_skills()
    except Exception as e:
        logger.warning("get_enabled_skills failed for family %s: %s", family_id, type(e).__name__)
        enabled_skills = []

    # Apply per-agent skill scope: AI问答 (chat-only) → no business skills;
    # 数鸣 (sentinel "*") → all family-enabled; custom → intersect declared with family.
    resolved_skills = _resolve_skills(agent_config.get("skills"), enabled_skills)

    try:
        mcp_servers = await client.get_enabled_mcp_servers()
    except Exception:
        mcp_servers = []

    # 3. Multi-slot provider selection
    providers = ai_config.get("providers", [])
    if not providers:
        yield builder_events.error("未配置 AI 供应商", code="NO_PROVIDER").to_ndjson()
        return

    task_type = "thinking" if enable_thinking else "text"
    if _select_model is None:
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return
    try:
        selected_provider, model_id, caps = _select_model(providers, task_type)
    except ValueError as e:
        yield builder_events.error(
            f"无匹配的 AI 模型: {e}", code="NO_MATCHING_MODEL"
        ).to_ndjson()
        return

    # 4. Build effective config
    pm = get_path_manager()
    config_builder = EffectiveConfigBuilder(pm)

    skill_entries = [
        {"skill_name": s["skill_id"], "is_builtin": s.get("skill_type") == "builtin"}
        for s in resolved_skills
    ]

    try:
        effective = config_builder.build(
            family_id=int(family_id),
            agent_name=agent_name,
            ai_provider=selected_provider,
            agent_config=agent_config,
            enabled_skills=skill_entries,
            mcp_servers=mcp_servers,
        )
    except Exception as e:
        yield builder_events.error(
            f"生成运行配置失败: {e}", code="CONFIG_BUILD_ERROR"
        ).to_ndjson()
        return

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. RunnableConfig with AppConfig injection
    # U2: reasoning_effort controls thinking depth (low/medium/high).
    # Only meaningful when enable_thinking=True; default "medium" if omitted.
    # Passed via configurable so DeerFlow agent can access it.
    effective_reasoning_effort = (reasoning_effort or "medium") if enable_thinking else None

    # DeerFlow expects an AppConfig pydantic instance, not a dict.
    # SandboxConfig.use is required (no default), so seed it before validation.
    if AppConfig is None:
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return
    app_config_dict = dict(effective.config_dict)
    app_config_dict.setdefault(
        "sandbox", {"use": "deerflow.sandbox.local:LocalSandboxProvider"}
    )
    try:
        app_config_obj = AppConfig.model_validate(app_config_dict)
    except Exception as e:
        yield builder_events.error(
            f"生成运行配置失败: {e}", code="CONFIG_BUILD_ERROR"
        ).to_ndjson()
        return

    runnable_config = {
        "configurable": {
            "thread_id": thread_id,
            "app_config": app_config_obj,
            "user_id": user_id,
            "reasoning_effort": effective_reasoning_effort,
        }
    }

    # 7. Emit session start
    yield builder_events.phase("connecting", {"agent_name": agent_name}).to_ndjson()

    # 8. Create agent graph and stream
    if make_lead_agent is None:
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return

    try:
        agent_graph = make_lead_agent(runnable_config)
    except Exception as e:
        yield builder_events.error(
            f"创建智能体失败: {e}", code="AGENT_CREATE_ERROR"
        ).to_ndjson()
        return

    # 9. Stream events with message-type dispatch
    # Track pending tool calls for result matching
    pending_tool_calls: dict[str, str] = {}  # tool_call_id -> tool_name
    answer_parts: list[str] = []
    emitted_phases: set[str] = set()  # ensure each phase emitted at most once

    state = {"messages": [{"role": "user", "content": message}]}

    try:
        async for event in agent_graph.astream(state, runnable_config):
            if not isinstance(event, dict):
                continue
            for _node_name, node_output in event.items():
                if not isinstance(node_output, dict) or "messages" not in node_output:
                    continue
                for msg in node_output["messages"]:
                    for line in _process_message(
                        msg,
                        builder_events,
                        pending_tool_calls,
                        answer_parts,
                        emitted_phases,
                    ):
                        yield line
    except Exception as e:
        yield builder_events.error(str(e), code="STREAM_ERROR").to_ndjson()
        return

    # 10. Emit end
    elapsed_ms = int((time.monotonic() - t_start) * 1000)
    yield builder_events.end(
        summary="".join(answer_parts)[:200],
        tokens_used=0,
        execution_time_ms=elapsed_ms,
        tools_used=None,
    ).to_ndjson()


def _process_message(
    msg: Any,
    builder: EventStreamBuilder,
    pending_tool_calls: dict[str, str],
    answer_parts: list[str],
    emitted_phases: set[str],
) -> Generator[str, None, None]:
    """Process a single message from LangGraph astream and emit NDJSON events.

    Message type dispatch:
    - AIMessage with reasoning_content or thinking blocks → phase.thinking + token(is_thinking=True)
    - AIMessage with tool_calls → tool.call events
    - ToolMessage → tool.result events
    - AIMessage with text content → phase.answering + token(is_thinking=False)
    """
    msg_type = _get_msg_type(msg)

    if msg_type == "ai":
        yield from _process_ai_message(
            msg, builder, pending_tool_calls, answer_parts, emitted_phases
        )
    elif msg_type == "tool":
        yield from _process_tool_message(msg, builder, pending_tool_calls)


def _get_msg_type(msg: Any) -> str:
    """Get the message type identifier."""
    if isinstance(msg, dict):
        return msg.get("type", "unknown")
    if hasattr(msg, "type"):
        return msg.type
    return "unknown"


def _process_ai_message(
    msg: Any,
    builder: EventStreamBuilder,
    pending_tool_calls: dict[str, str],
    answer_parts: list[str],
    emitted_phases: set[str],
) -> Generator[str, None, None]:
    """Process AIMessage: reasoning → tool_calls → text content."""

    # 1. Check for reasoning/thinking content
    reasoning_content = _extract_reasoning_content(msg)
    if reasoning_content:
        if "thinking" not in emitted_phases:
            emitted_phases.add("thinking")
            yield builder.phase("thinking").to_ndjson()
        yield builder.token(reasoning_content, is_thinking=True).to_ndjson()

    # 2. Check for tool_calls
    tool_calls = _extract_tool_calls(msg)
    for tc in tool_calls:
        tool_id = tc.get("id", "")
        tool_name = tc.get("name", "unknown")
        args = tc.get("args", {})
        tool_type, display_name, icon = _map_tool_type(tool_name)

        # Track for result matching
        pending_tool_calls[tool_id] = tool_name

        yield builder.tool_call(
            tool_name=tool_name,
            arguments=args,
            tool_type=tool_type,
            display_name=display_name,
            icon=icon,
        ).to_ndjson()

    # 3. Check for text content (answer)
    text_content = _extract_text_content(msg)
    if text_content:
        if "answering" not in emitted_phases:
            emitted_phases.add("answering")
            yield builder.phase("answering").to_ndjson()
        answer_parts.append(text_content)
        yield builder.token(text_content, is_thinking=False).to_ndjson()


def _process_tool_message(
    msg: Any,
    builder: EventStreamBuilder,
    pending_tool_calls: dict[str, str],
) -> Generator[str, None, None]:
    """Process ToolMessage: emit tool.result event."""

    tool_call_id = _get_tool_call_id(msg)
    content = _extract_content(msg)

    # Determine success from message content/status
    success = _is_tool_success(msg)

    # Get tool_name from pending calls if available
    tool_name = pending_tool_calls.pop(tool_call_id, "unknown")

    yield builder.tool_result(
        tool_id=tool_call_id,
        success=success,
        execution_time_ms=0,  # Timing not available at message level
        data={"content": content, "tool_name": tool_name},
    ).to_ndjson()


def _extract_reasoning_content(msg: Any) -> str | None:
    """Extract reasoning/thinking content from AIMessage.

    Formats:
    - additional_kwargs["reasoning_content"] (Anthropic extended thinking)
    - content as list with {"type": "thinking", "thinking": "..."} blocks
    """
    additional_kwargs = _get_additional_kwargs(msg)
    if additional_kwargs:
        reasoning = additional_kwargs.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning:
            return reasoning

    content = _get_content(msg)
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking":
                thinking = block.get("thinking")
                if isinstance(thinking, str) and thinking:
                    return thinking
    return None


def _extract_tool_calls(msg: Any) -> list[dict]:
    """Extract tool_calls from AIMessage."""
    if isinstance(msg, dict):
        return msg.get("tool_calls", [])
    if hasattr(msg, "tool_calls"):
        return list(msg.tool_calls) if msg.tool_calls else []
    return []


def _extract_text_content(msg: Any) -> str | None:
    """Extract text content from AIMessage (excluding thinking blocks)."""
    content = _get_content(msg)
    if isinstance(content, str):
        return content if content else None
    if isinstance(content, list):
        text_parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
        return "".join(text_parts) if text_parts else None
    return None


def _extract_content(msg: Any) -> str | None:
    """Extract raw content from any message type."""
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
    return None


def _get_content(msg: Any) -> Any:
    """Get content field from message."""
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        return msg.content
    return None


def _get_additional_kwargs(msg: Any) -> dict | None:
    """Get additional_kwargs from message."""
    if isinstance(msg, dict):
        return msg.get("additional_kwargs")
    if hasattr(msg, "additional_kwargs"):
        return msg.additional_kwargs
    return None


def _get_tool_call_id(msg: Any) -> str:
    """Get tool_call_id from ToolMessage."""
    if isinstance(msg, dict):
        return msg.get("tool_call_id", "")
    if hasattr(msg, "tool_call_id"):
        return msg.tool_call_id
    return ""


def _is_tool_success(msg: Any) -> bool:
    """Determine if tool execution succeeded."""
    # Check status field if present
    if isinstance(msg, dict):
        status = msg.get("status")
        if status == "error":
            return False
    if hasattr(msg, "status") and msg.status == "error":
        return False
    # Default: presence of any content (str, list, dict) means success
    content = _get_content(msg)
    return content is not None and content != ""
