"""Shared message classification and extraction utilities.

Extracted from agent_dispatch.py so both the agent-first dispatch path and
the DeerFlow adapter path can import from a single source of truth.

All functions handle both LangChain BaseMessage objects and plain dicts —
that flexibility is intentional and must be preserved.
"""

from typing import Any

# ── Tool registry: tool_name → (tool_type, display_name, icon, i18n_key) ──────────
# Backend is the source of truth for these mappings; the frontend only owns
# summary template text. Add new entries here when introducing a tool.
# i18n_key is used by frontend for translation; display_name is fallback for
# legacy clients or when i18n is unavailable.
# Icons use emojis following deerflow pattern (ChainOfThoughtStep icon style).
_TOOL_REGISTRY: dict[str, tuple[str, str, str, str]] = {
    # Asset queries
    "get_assets": ("asset_query", "查询资产", "💰", "toolName.getAssets"),
    "get_dashboard_overview": ("asset_query", "读取资产概览", "📊", "toolName.getDashboardOverview"),
    "get_dashboard_allocation": ("asset_query", "读取资产配置", "📈", "toolName.getDashboardAllocation"),
    "get_dashboard_trend": ("trend_calc", "计算资产趋势", "📈", "toolName.getDashboardTrend"),
    "get_low_usage_assets": ("asset_query", "扫描闲置资产", "🔍", "toolName.getLowUsageAssets"),
    "get_liabilities": ("asset_query", "查询负债", "📋", "toolName.getLiabilities"),
    # Reports
    "generate_report": ("report_gen", "生成家庭报告", "📄", "toolName.generateReport"),
    "compose_summary": ("report_gen", "生成摘要", "📝", "toolName.composeSummary"),
    # Wish / spending analysis
    "analyze_wishes": ("wish_analysis", "分析心愿计划", "💭", "toolName.analyzeWishes"),
    "analyze_spending_leaks": ("wish_analysis", "分析支出漏洞", "💸", "toolName.analyzeSpendingLeaks"),
    # Web search (smart mode tool)
    "web_search": ("web_search", "搜索网络", "🔍", "toolName.webSearch"),
    "tavily_search": ("web_search", "搜索网络", "🔍", "toolName.webSearch"),
    # MCP tools (numina-family-data server)
    "numina-family-data_get_family_overview": ("data_collect", "获取家庭概览", "📊", "toolName.getFamilyOverview"),
    "numina-family-data_get_assets": ("data_collect", "查询资产数据", "💰", "toolName.getAssetsData"),
    "numina-family-data_get_liabilities": ("data_collect", "查询负债数据", "📋", "toolName.getLiabilitiesData"),
    "numina-family-data_get_members": ("data_collect", "获取家庭成员", "👥", "toolName.getMembers"),
    "numina-family-data_get_recent_alerts": ("data_collect", "获取近期预警", "🔔", "toolName.getRecentAlerts"),
    # DeerFlow built-in tools
    "execute_code": ("execution", "执行分析代码", "⚙️", "toolName.executeCode"),
    "bash": ("execution", "执行命令", "⚙️", "toolName.bash"),
    "write": ("execution", "写入结果", "📝", "toolName.write"),
    "read": ("execution", "读取数据", "📖", "toolName.read"),
    "search": ("web_search", "搜索信息", "🔍", "toolName.search"),
    "load_skill": ("internal", "加载分析能力", "🧩", "toolName.loadSkill"),
    "write_file": ("execution", "保存文件", "💾", "toolName.writeFile"),
    "read_file": ("execution", "读取文件", "📂", "toolName.readFile"),
}

# DeerFlow built-in tool suffixes that are safe to match on namespaced variants
# These are specifically the DeerFlow sandbox tools where suffix matching is intentional
_SUFFIX_MATCH_WHITELIST = frozenset({
    "execute_code",
    "bash",
    "write",
    "read",
    "search",
    "load_skill",
    "write_file",
    "read_file",
})


def resolve_tool_metadata(tool_name: str) -> tuple[str, str, str, str]:
    """Resolve (tool_type, display_name, icon, i18n_key) for a tool name.

    Unknown tools fall back to ("unknown", <name>, "tool", "") so the UI can
    still render a generic step. Suffix matching is restricted to a whitelist
    of DeerFlow built-in tools to prevent false positives from generic suffixes.
    """
    if tool_name in _TOOL_REGISTRY:
        return _TOOL_REGISTRY[tool_name]
    # Suffix match only for whitelisted DeerFlow built-in tool names
    # Prevents false positives like "audit_log_read" matching "read"
    if "_" in tool_name:
        suffix = tool_name.rsplit("_", 1)[-1]
        if suffix in _SUFFIX_MATCH_WHITELIST:
            return _TOOL_REGISTRY[suffix]
    return ("unknown", tool_name, "tool", None)


def classify_message(msg: Any) -> str:
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
    if extract_reasoning(msg):
        return "thinking"

    if extract_content(msg):
        return "text"
    return "unknown"


def extract_reasoning(msg: Any) -> str | None:
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


def extract_tool_calls(msg: Any) -> list[dict]:
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


def extract_tool_result(msg: Any) -> tuple[str, Any]:
    """Pull (tool_call_id, content) from a ToolMessage-shaped object."""
    if isinstance(msg, dict):
        return str(msg.get("tool_call_id") or ""), msg.get("content")
    return (
        str(getattr(msg, "tool_call_id", "") or ""),
        getattr(msg, "content", None),
    )


def extract_content(msg: Any) -> str | None:
    """Pull plain text content from an AIMessage-shaped object."""
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
    return None
