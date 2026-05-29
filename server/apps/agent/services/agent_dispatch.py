"""Agent-first execution entry point — Gateway path.

Replaces the old DeerFlowAdapter path with:
  BackendClient queries → EffectiveConfigBuilder → RunnableConfig
  → make_lead_agent() → astream() → NDJSON events.

No global singleton mutation. No ContextVar. No reload_app_config().
"""

import time
import uuid
from collections.abc import AsyncGenerator
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


# ── Tool registry: tool_name → (tool_type, display_name, icon) ──────────────
# Backend is the source of truth for these mappings; the frontend only owns
# summary template text. Add new entries here when introducing a tool.
_TOOL_REGISTRY: dict[str, tuple[str, str, str]] = {
    # Asset queries
    "get_assets": ("asset_query", "查询资产", "wallet"),
    "get_dashboard_overview": ("asset_query", "读取资产概览", "wallet"),
    "get_dashboard_allocation": ("asset_query", "读取资产配置", "wallet"),
    "get_dashboard_trend": ("trend_calc", "计算资产趋势", "trending-up"),
    "get_low_usage_assets": ("asset_query", "扫描闲置资产", "wallet"),
    "get_liabilities": ("asset_query", "查询负债", "wallet"),
    # Reports
    "generate_report": ("report_gen", "生成家庭报告", "file-text"),
    "compose_summary": ("report_gen", "生成摘要", "file-text"),
    # Wish / spending analysis
    "analyze_wishes": ("wish_analysis", "分析心愿计划", "heart"),
    "analyze_spending_leaks": ("wish_analysis", "分析支出漏洞", "heart"),
    # Web search (smart mode tool)
    "web_search": ("web_search", "搜索网络", "search"),
    "tavily_search": ("web_search", "搜索网络", "search"),
}


def _resolve_tool_metadata(tool_name: str) -> tuple[str, str, str]:
    """Resolve (tool_type, display_name, icon) for a tool name.

    Unknown tools fall back to ("unknown", <name>, "tool") so the UI can
    still render a generic step.
    """
    return _TOOL_REGISTRY.get(tool_name, ("unknown", tool_name, "tool"))


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


def _classify_message(msg: Any) -> str:
    """Detect message kind from a langchain BaseMessage / dict.

    Returns one of: "thinking" | "tool_call" | "tool_result" | "text" | "unknown".
    """
    # ToolMessage carries `tool_call_id` and the tool's return value.
    if hasattr(msg, "tool_call_id") and getattr(msg, "tool_call_id", None):
        return "tool_result"
    if isinstance(msg, dict) and msg.get("tool_call_id"):
        return "tool_result"

    # AIMessage may carry pending tool_calls.
    tool_calls = getattr(msg, "tool_calls", None)
    if not tool_calls and isinstance(msg, dict):
        tool_calls = msg.get("tool_calls")
    if tool_calls:
        return "tool_call"

    # Reasoning content can live on the message or in additional_kwargs.
    if _extract_reasoning(msg):
        return "thinking"

    if _extract_content(msg):
        return "text"
    return "unknown"


def _extract_reasoning(msg: Any) -> str | None:
    """Pull thinking / reasoning content from a message, if present."""
    if isinstance(msg, dict):
        if msg.get("reasoning_content"):
            return str(msg["reasoning_content"])
        kwargs = msg.get("additional_kwargs") or {}
        if isinstance(kwargs, dict) and kwargs.get("reasoning_content"):
            return str(kwargs["reasoning_content"])
        return None

    direct = getattr(msg, "reasoning_content", None)
    if direct:
        return str(direct)
    kwargs = getattr(msg, "additional_kwargs", None) or {}
    if isinstance(kwargs, dict) and kwargs.get("reasoning_content"):
        return str(kwargs["reasoning_content"])
    return None


def _extract_tool_calls(msg: Any) -> list[dict]:
    """Normalize tool_calls into a list of {name, args, id} dicts."""
    raw = getattr(msg, "tool_calls", None)
    if raw is None and isinstance(msg, dict):
        raw = msg.get("tool_calls")
    if not raw:
        return []
    out: list[dict] = []
    for item in raw:
        if isinstance(item, dict):
            name = item.get("name") or ""
            args = item.get("args") or item.get("arguments") or {}
            tid = item.get("id") or ""
        else:
            name = getattr(item, "name", "") or ""
            args = getattr(item, "args", None) or getattr(item, "arguments", None) or {}
            tid = getattr(item, "id", "") or ""
        if not isinstance(args, dict):
            args = {"_raw": args}
        out.append({"name": name, "args": args, "id": tid})
    return out


def _extract_tool_result(msg: Any) -> tuple[str, Any]:
    """Pull (tool_call_id, content) from a ToolMessage-shaped object."""
    if isinstance(msg, dict):
        return str(msg.get("tool_call_id") or ""), msg.get("content")
    return (
        str(getattr(msg, "tool_call_id", "") or ""),
        getattr(msg, "content", None),
    )


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    user_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
    reasoning_effort: str | None = None,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events."""
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
    selected_provider, model_id, caps = _select_model(providers, task_type)

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
    # reasoning_effort only takes effect under deep-think mode. Surface it to
    # DeerFlow's app_config so model providers that honor it (OpenAI o-series,
    # Claude extended thinking) receive the directive.
    if enable_thinking and reasoning_effort:
        model_section = app_config_dict.setdefault("model", {})
        if isinstance(model_section, dict):
            model_section["reasoning_effort"] = reasoning_effort
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

    # 9. Stream events — dispatch by message kind so the UI can render
    # phase.thinking, tool.call/result, and answer tokens distinctly.
    answer_parts: list[str] = []
    thinking_started = False
    answering_started = False
    tools_used: list[str] = []
    # Map provider tool_call_id → backend-issued tool_id so the .result event
    # references the same step the .call event opened.
    tool_call_id_map: dict[str, str] = {}

    state = {"messages": [{"role": "user", "content": message}]}

    try:
        async for event in agent_graph.astream(state, runnable_config):
            if not isinstance(event, dict):
                continue
            for _node_name, node_output in event.items():
                if not isinstance(node_output, dict) or "messages" not in node_output:
                    continue
                for msg in node_output["messages"]:
                    kind = _classify_message(msg)

                    if kind == "thinking":
                        reasoning = _extract_reasoning(msg) or ""
                        if not thinking_started:
                            yield builder_events.phase("thinking").to_ndjson()
                            thinking_started = True
                        if reasoning:
                            yield builder_events.token(
                                reasoning, is_thinking=True
                            ).to_ndjson()
                        continue

                    if kind == "tool_call":
                        for call in _extract_tool_calls(msg):
                            tname = call["name"]
                            ttype, tdisplay, ticon = _resolve_tool_metadata(tname)
                            tools_used.append(tname)
                            evt = builder_events.tool_call(
                                tool_name=tname,
                                arguments=call["args"],
                                display_name=tdisplay,
                                icon=ticon,
                                tool_type=ttype,
                            )
                            # Remember the mapping so .result can target this step.
                            backend_id = evt.payload["tool"]["id"]
                            if call["id"]:
                                tool_call_id_map[str(call["id"])] = backend_id
                            yield evt.to_ndjson()
                        continue

                    if kind == "tool_result":
                        provider_id, content = _extract_tool_result(msg)
                        backend_id = tool_call_id_map.get(provider_id, provider_id)
                        # Tool messages from langchain don't carry success/timing —
                        # we report success when content is present, no exception
                        # bubbled up; failures arrive via the surrounding except.
                        yield builder_events.tool_result(
                            tool_id=backend_id,
                            success=True,
                            execution_time_ms=0,
                            data=content,
                        ).to_ndjson()
                        continue

                    if kind == "text":
                        content = _extract_content(msg)
                        if not content:
                            continue
                        if not answering_started:
                            yield builder_events.phase("answering").to_ndjson()
                            answering_started = True
                        answer_parts.append(content)
                        yield builder_events.token(
                            content, is_thinking=False
                        ).to_ndjson()
    except Exception as e:
        yield builder_events.error(str(e), code="STREAM_ERROR").to_ndjson()
        return

    # 10. Emit end
    elapsed_ms = int((time.monotonic() - t_start) * 1000)
    yield builder_events.end(
        summary="".join(answer_parts)[:200],
        tokens_used=0,
        execution_time_ms=elapsed_ms,
        tools_used=tools_used or None,
    ).to_ndjson()


def _extract_content(msg) -> str | None:
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
    return None
