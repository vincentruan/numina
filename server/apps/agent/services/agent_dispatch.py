"""Agent-first execution entry point — Gateway path.

Replaces the old DeerFlowAdapter path with:
  BackendClient queries → EffectiveConfigBuilder → RunnableConfig
  → make_lead_agent() → astream() → NDJSON events.

No global singleton mutation. No ContextVar. No reload_app_config().
"""

import asyncio
import contextlib
import hashlib
import os
import re
import time
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from apps.agent.services.session_journal import session_journal
from apps.agent.services.stream_events import EventStreamBuilder

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient, report_web_search_circuit
from apps.agent.schemas.policy import CapabilityPolicy
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.message_classifier import (
    classify_message,
    extract_content,
    extract_reasoning,
    extract_tool_calls,
    extract_tool_result,
    resolve_tool_metadata,
)
from apps.agent.services.pii_redactor import pii_redactor
from apps.agent.services.policy_guard import policy_guard
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
    from apps.agent.services.orchestrator import _fire_and_forget, _select_model
except ImportError:
    _select_model = None
    _fire_and_forget = None  # type: ignore[assignment]


# IDs for system agents seeded by alembic migrations.
# numina is the brand-primary system agent (b6745e8a2c14_demote_builtin_agents_seed_numina).
# ai-assistant was the legacy chat-only system agent (a53453cf574b_unified_agent_model)
# and is removed by the follow-up migration. Requests pinned to the legacy ID
# fall back to numina so old client links keep working.
_NUMINA_AGENT_ID: int = 100000000000005
_LEGACY_AI_ASSISTANT_AGENT_ID: int = 100000000000003

# Skills that are reserved for internal system use only — never dispatched to any agent.
_INTERNAL_ONLY_SKILLS: frozenset[str] = frozenset({"skill-creator", "skill-installer"})


def _classify_stream_error(e: Exception) -> str:
    """Map a Python exception to a web search circuit failure_type enum value.

    The backend circuit endpoint expects one of the enum literals defined in
    WebSearchCircuitReportRequest.failure_type. Python exception class names
    (e.g. 'ConnectionError') are not valid values there.
    """

    try:
        import httpx as _httpx
    except ImportError:
        _httpx = None  # type: ignore[assignment]

    if isinstance(e, (TimeoutError, asyncio.TimeoutError)):
        return "transient_timeout"
    if _httpx is not None:
        if isinstance(e, _httpx.HTTPStatusError):
            status = e.response.status_code
            if status in (401, 403):
                return "permanent_auth"
            if status == 429:
                return "transient_rate_limit"
            if status >= 500:
                return "transient_server"
        if isinstance(e, _httpx.ConnectError):
            return "transient_network"
    if isinstance(e, ConnectionError):
        return "transient_network"
    return "transient_network"



# ── Classification helpers — delegated to shared message_classifier module ───
# Private aliases kept for readability of stream_agent_dispatch internals.
_classify_message = classify_message
_extract_reasoning = extract_reasoning
_extract_tool_calls = extract_tool_calls
_extract_tool_result = extract_tool_result
_extract_content = extract_content
_resolve_tool_metadata = resolve_tool_metadata


def _generate_tool_result_summary(content: Any) -> str | None:
    """Generate a brief summary of tool result for frontend display.

    DeerFlow pattern: show concise result summary instead of raw output.
    Truncates long content, handles dict/list results with key counts.
    """
    if content is None:
        return None
    if isinstance(content, str):
        # Truncate to 50 chars for display (deerflow pattern)
        if len(content) > 50:
            return content[:50] + "…"
        return content if content.strip() else None
    if isinstance(content, dict):
        # Show key count for dict results
        keys = list(content.keys())
        if not keys:
            return "空结果"
        # Filter out internal/technical keys
        display_keys = [k for k in keys if not k.startswith("_") and k not in ("raw", "data")]
        if not display_keys:
            return f"{len(keys)} 项数据"
        if len(display_keys) <= 3:
            return f"返回: {', '.join(display_keys)}"
        return f"{len(keys)} 项数据"
    if isinstance(content, list):
        count = len(content)
        if count == 0:
            return "无数据"
        if count <= 5:
            return f"返回 {count} 项"
        return f"返回 {count} 项数据"
    # Fallback for other types
    return "执行完成"


def _resolve_skills(
    agent_skills: list[str] | str | None,
    family_enabled_skills: list[dict],
) -> list[dict]:
    """Resolve which skills an agent dispatches with, enforcing R5/R6/R15 + U9.

    Branches:
    - ``agent_skills == ["chat"]`` → ``[]`` (R5: AI问答 reserved chat capability,
      pure LLM mode, no business skill catalog injection).
    - ``"*" in agent_skills`` → ``family_enabled_skills`` minus
      ``_INTERNAL_ONLY_SKILLS`` (R6: sentinel + U9 exclusion).
    - non-empty specific list → intersection with ``family_enabled_skills`` by
      ``skill_id``, excluding ``_INTERNAL_ONLY_SKILLS`` (R15 + U9 exclusion).
    - ``None`` / ``[]`` → ``[]`` (defensive default).

    The resolved list preserves the original dict shape from BackendClient
    (``{"skill_id": ..., "skill_type": ..., ...}``) so downstream consumers
    (EffectiveConfigBuilder) see the same fields they would without resolution.

    Defensive: if agent_skills is a JSON string (legacy DB bug), deserialize it.
    """
    # Defensive: handle JSON string from legacy DB storage bug
    if isinstance(agent_skills, str):
        try:
            import json
            agent_skills = json.loads(agent_skills)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "[agent_dispatch] agent_skills is a non-JSON string: %s, treating as empty",
                agent_skills[:50] if agent_skills else "",
            )
            return []

    if not agent_skills:
        return []
    # Chat-reserved capability handling must come before the sentinel branch
    # so an agent with skills=["chat"] never accidentally inherits family skills.
    if agent_skills == ["chat"]:
        return []
    if "*" in agent_skills:
        return [s for s in family_enabled_skills if s.get("skill_id") not in _INTERNAL_ONLY_SKILLS]
    allowed = set(agent_skills) - _INTERNAL_ONLY_SKILLS
    return [s for s in family_enabled_skills if s.get("skill_id") in allowed]




async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    user_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
    web_search: bool = False,
    reasoning_effort: str | None = None,
    # DeerFlow execution mode parameters (Phase 2)
    is_plan_mode: bool = False,
    subagent_enabled: bool = False,
    cancellation_event: asyncio.Event | None = None,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events."""
    t_start = time.monotonic()
    task_id = str(uuid.uuid4())
    audit_id = str(uuid.uuid4())
    # Mutable holders so the finally-block audit emit can reflect the latest
    # state regardless of which early-return path the function took.
    audit_state: dict[str, Any] = {
        "agent_name": None,
        "error_type": None,
        "deerflow_attempted": False,
        "success": False,
    }
    builder_events = EventStreamBuilder(
        capability_id=f"agent-{agent_id}", task_id=task_id
    )

    def _emit_audit(error_type: str | None) -> None:
        """Emit one AuditEntry — wraps audit_logger.log_call so the audit
        invariant from agent/CLAUDE.md Key Invariants #3 is satisfied on
        every code path (success, denial, exception). Never raises."""
        # Audit must never break the main path. Mirrors AuditLogger.log_call's
        # internal swallow.
        with contextlib.suppress(Exception):
            audit_logger.log_call(
                AuditEntry(
                    family_id=family_id,
                    audit_id=audit_id,
                    user_id=user_id,
                    capability=audit_state["agent_name"] or f"agent-{agent_id}",
                    success=error_type is None,
                    error_type=error_type,
                    deerflow_attempted=audit_state["deerflow_attempted"],
                    duration_ms=int((time.monotonic() - t_start) * 1000),
                )
            )

    # 1. Fetch agent config — fall back to numina when legacy ai-assistant ID is requested.
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        if agent_id == _LEGACY_AI_ASSISTANT_AGENT_ID:
            logger.info(
                "agent_id=%s removed; falling back to numina (id=%s)",
                agent_id,
                _NUMINA_AGENT_ID,
            )
            try:
                agent_config = await client.get_agent_config(_NUMINA_AGENT_ID)
            except Exception as fallback_err:
                logger.warning(
                    "[agent_dispatch] agent_config fetch failed family=%s err_type=%s",
                    family_id,
                    type(fallback_err).__name__,
                )
                _emit_audit("AgentConfigError")
                yield builder_events.error(
                    "获取智能体配置失败", code="AGENT_CONFIG_ERROR"
                ).to_ndjson()
                return
        else:
            logger.warning(
                "[agent_dispatch] agent_config fetch failed family=%s agent_id=%s err_type=%s",
                family_id,
                agent_id,
                type(e).__name__,
            )
            _emit_audit("AgentConfigError")
            yield builder_events.error(
                "获取智能体配置失败", code="AGENT_CONFIG_ERROR"
            ).to_ndjson()
            return

    if not agent_config.get("is_enabled", True):
        _emit_audit("AgentDisabled")
        yield builder_events.error("智能体已禁用", code="AGENT_DISABLED").to_ndjson()
        return

    agent_name = agent_config["agent_name"]
    audit_state["agent_name"] = agent_name

    # 2. Fetch AI provider config + skills + MCP in parallel-safe sequence
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        logger.warning(
            "[agent_dispatch] ai_config fetch failed family=%s err_type=%s",
            family_id,
            type(e).__name__,
        )
        _emit_audit("AiConfigError")
        yield builder_events.error(
            "获取 AI 配置失败", code="AI_CONFIG_ERROR"
        ).to_ndjson()
        return

    # 2a. Policy guard — required by agent/CLAUDE.md Key Invariants #2.
    # CapabilityPolicy fields come from BackendClient.get_family_ai_config; the
    # capability scoped to this dispatch is the agent_name (e.g. "numina"), so
    # families can whitelist agents by name in allowed_capabilities.
    policy = CapabilityPolicy(
        ai_enabled=ai_config.get("ai_enabled", True),
        allowed_capabilities=ai_config.get("allowed_capabilities", []),
        admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
        member_role=ai_config.get("member_role", "member"),
    )
    decision = policy_guard.check(policy, agent_name)
    if not decision.allowed:
        _emit_audit("PolicyDenied")
        yield builder_events.error(
            decision.reason or "该功能不可用", code="POLICY_DENIED"
        ).to_ndjson()
        return

    try:
        enabled_skills = await client.get_enabled_skills()
    except Exception as e:
        logger.warning("get_enabled_skills failed for family %s: %s", family_id, type(e).__name__)
        enabled_skills = []

    # Apply per-agent skill scope: AI问答 (chat-only) → no business skills;
    # 小鸣 (sentinel "*") → all family-enabled; custom → intersect declared with family.
    resolved_skills = _resolve_skills(agent_config.get("skills"), enabled_skills)

    try:
        mcp_servers = await client.get_enabled_mcp_servers()
        logger.info(
            "[agent_dispatch] fetched MCP servers for family=%s count=%s servers=%s",
            family_id,
            len(mcp_servers),
            [s.get("name") for s in mcp_servers],
        )

        # [Security] Validate backend-type MCP servers — their URL must match
        # the configured backend base URL. This prevents a compromised owner
        # from redirecting the agent's internal MCP connection to an external
        # server, which would leak AGENT_INTERNAL_TOKEN.
        for srv in mcp_servers:
            if srv.get("name") == "Numina Backend MCP":
                expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
                actual_url = (srv.get("url") or "").rstrip("/")
                if not actual_url.startswith(expected_prefix):
                    logger.warning(
                        "[agent_dispatch] backend MCP URL mismatch! "
                        "family=%s expected_prefix=%s actual_url=%s — correcting",
                        family_id,
                        expected_prefix,
                        actual_url,
                    )
                    srv["url"] = settings.BACKEND_BASE_URL.rstrip("/") + "/api/v1/internal/mcp/" + family_id + "/sse"
                    logger.info(
                        "[agent_dispatch] corrected backend MCP URL for family=%s url=%s",
                        family_id,
                        srv["url"],
                    )
                break
    except Exception as e:
        logger.warning(
            "[agent_dispatch] get_enabled_mcp_servers failed family=%s err_type=%s err=%s",
            family_id,
            type(e).__name__,
            e,
        )
        mcp_servers = []

    # 3a. Inject auth headers into MCP servers (required for SSE handshake)
    # The backend API returns MCP servers without auth headers; we add them here.
    from apps.agent.app.config import settings as agent_settings
    mcp_headers: dict[str, str] = {
        "X-Agent-Token": agent_settings.AGENT_INTERNAL_TOKEN,
        "X-Family-Id": family_id,
    }
    if user_id:
        mcp_headers["X-Caller-User-Id"] = user_id
    for srv in mcp_servers:
        srv["headers"] = mcp_headers

    # 3. Multi-slot provider selection
    providers = ai_config.get("providers", [])
    if not providers:
        _emit_audit("NoProvider")
        yield builder_events.error("未配置 AI 供应商", code="NO_PROVIDER").to_ndjson()
        return

    task_type = "thinking" if enable_thinking else "text"
    if _select_model is None:
        _emit_audit("RuntimeUnavailable")
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
            ai_config=ai_config,
        )
    except Exception as e:
        logger.warning(
            "[agent_dispatch] effective config build failed family=%s err_type=%s",
            family_id,
            type(e).__name__,
        )
        _emit_audit("ConfigBuildError")
        yield builder_events.error(
            "生成运行配置失败", code="CONFIG_BUILD_ERROR"
        ).to_ndjson()
        return

    # 4a. Prepare extensions_config.json for MCP tool loading
    # DeerFlow reads MCP servers from extensions_config.json via DEER_FLOW_EXTENSIONS_CONFIG_PATH.
    extensions_config_path = effective.extensions_config_path
    prev_extensions_env: str | None = None

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. RunnableConfig with AppConfig injection
    # DeerFlow expects an AppConfig pydantic instance, not a dict.
    # SandboxConfig.use is required (no default), so seed it before validation.
    if AppConfig is None:
        _emit_audit("RuntimeUnavailable")
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return
    # [Integrated with Numina Multi-Tenant] — use Numina's sandbox provider
    # that scopes sandbox IDs and paths by family_id.
    from apps.agent.services.runtime.sandbox_provider import (
        set_family_sandbox_context,
    )
    set_family_sandbox_context(family_id)

    app_config_dict = dict(effective.config_dict)
    app_config_dict.setdefault(
        "sandbox",
        {
            "use": "apps.agent.services.runtime.sandbox_provider:NuminaLocalSandboxProvider"
        },
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
        logger.warning(
            "[agent_dispatch] AppConfig.model_validate failed family=%s err_type=%s",
            family_id,
            type(e).__name__,
        )
        _emit_audit("ConfigBuildError")
        yield builder_events.error(
            "生成运行配置失败", code="CONFIG_BUILD_ERROR"
        ).to_ndjson()
        return

    runnable_config = {
        "configurable": {
            "thread_id": thread_id,
            "app_config": app_config_obj,
            "user_id": user_id,
            # DeerFlow execution mode parameters (Phase 2)
            "is_plan_mode": is_plan_mode,
            "subagent_enabled": subagent_enabled,
        }
    }

    # 7. Emit session start
    yield builder_events.phase("connecting", {"agent_name": agent_name}).to_ndjson()

    # 8. Create agent graph and stream
    if make_lead_agent is None:
        _emit_audit("RuntimeUnavailable")
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return

    # 8a. Set DEER_FLOW_EXTENSIONS_CONFIG_PATH for MCP tool loading
    # DeerFlow reads MCP server configs from this file. Must be set before make_lead_agent.
    # CRITICAL: Reset MCP tools cache because the cache tracks mtime of a SINGLE file path.
    # In multi-family architecture, each family gets a DIFFERENT temp config file path.
    # Without reset, the cache would keep using stale tools from a previous family's config.
    if extensions_config_path:
        try:
            from deerflow.config.extensions_config import reset_extensions_config
            from deerflow.mcp.cache import reset_mcp_tools_cache

            # Reset both caches: MCP tools cache and ExtensionsConfig singleton.
            # Without this, DeerFlow would reuse stale config from a previous family.
            reset_mcp_tools_cache()
            reset_extensions_config()
            logger.debug(
                "[agent_dispatch] reset MCP tools cache for new family=%s config_path=%s",
                family_id,
                extensions_config_path,
            )
        except ImportError:
            logger.warning(
                "[agent_dispatch] deerflow cache reset functions not available"
            )
        prev_extensions_env = os.environ.get("DEER_FLOW_EXTENSIONS_CONFIG_PATH")
        os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = extensions_config_path

    # All control flow from here lives inside `try/finally` so the persistence
    # hook + audit emit fire whether the stream completes, errors, or returns
    # early. From here on we treat DeerFlow as attempted; the audit log will
    # reflect that even if make_lead_agent itself raises.
    audit_state["deerflow_attempted"] = True
    answer_parts: list[str] = []
    success = False
    agent_graph: Any = None
    stream_error_type: str | None = None
    try:
        try:
            agent_graph = make_lead_agent(runnable_config)
        except Exception as e:
            stream_error_type = type(e).__name__
            logger.warning(
                "[agent_dispatch] make_lead_agent failed session=%s err_type=%s",
                thread_id,
                stream_error_type,
            )
            yield builder_events.error(
                "创建智能体失败", code="AGENT_CREATE_ERROR"
            ).to_ndjson()
            return

        # Decision 6 (plan §Decisions): make_lead_agent returns a graph with
        # checkpointer=None — verified by U1 step 1. Bind the shared SqliteSaver
        # post-compile so aget_state(...) below can read the title that
        # TitleMiddleware writes via aafter_model. Reuses the same instance
        # the orchestrator path holds, so thread_id namespace is shared.
        try:
            from apps.agent.services.deerflow_adapter.family_adapter_cache import (
                _get_shared_checkpointer,
            )
            agent_graph.checkpointer = _get_shared_checkpointer()
        except Exception:
            # Non-fatal: stream still works; aget_state will raise later and
            # the persistence hook falls back to the date-based title.
            logger.warning(
                "[agent_dispatch] checkpointer bind failed session=%s", thread_id
            )

        # Synchronous journal writes — must land before astream so event
        # replay order is correct. Both writes go through pii_redactor;
        # session_journal.append_event swallows file errors internally.
        user_segment = user_id if user_id else "_shared"
        try:
            jsonl_path = str(
                session_journal.resolve_path(
                    family_id=family_id,
                    session_id=thread_id,
                    capability="agent",
                    user_id=user_segment,
                )
            )
        except ValueError:
            # Invalid family_id / user_id / session_id slug — skip journal but
            # let the rest of the dispatch continue. The persistence hook
            # still fires (journal write is skipped, repo.upsert no longer takes jsonl_path).
            logger.warning(
                "[agent_dispatch] resolve_path rejected ids session=%s", thread_id
            )
            jsonl_path = ""
        if jsonl_path:
            session_journal.write_session_start(
                family_id=family_id,
                session_id=thread_id,
                user_id=user_id,
                capability="agent",
                model_name=model_id,
                jsonl_path=jsonl_path,
            )
            redacted_user_msg, _ = pii_redactor.redact_text(message or "")
            session_journal.write_user_message(
                family_id=family_id,
                session_id=thread_id,
                user_id=user_id,
                content=redacted_user_msg,
            )

        # 9. Stream events — dispatch by message kind so the UI can render
        # phase.thinking, tool.call/result, and answer tokens distinctly.
        # Dedup tracking: LangGraph may emit duplicate messages from different nodes.
        thinking_started = False
        answering_started = False
        tools_used: list[str] = []
        # Map provider tool_call_id → backend-issued tool_id so the .result event
        # references the same step the .call event opened.
        tool_call_id_map: dict[str, str] = {}
        # Track seen tool_call_ids to skip duplicates (root cause of stuck 'running' status)
        seen_tool_call_ids: set[str] = set()
        # Track last answer content hash to skip duplicate tokens
        last_answer_hash: str = ""

        # Web-search behavioral guidance lives in the skill files:
        # chat-search/SKILL.md ("联网搜索使用原则") and chat/SKILL.md ("不要尝试联网搜索").
        # The skill is selected based on web_search, so no runtime injection is
        # needed — and injecting here would leak internal guidance into
        # user-visible prompts.
        messages = []

        messages.append({"role": "user", "content": message})

        state = {"messages": messages}

        try:
            # ``context`` is the LangGraph 0.6+ Runtime context. The harness's
            # ``ThreadDataMiddleware.before_agent`` reads ``runtime.context.get
            # ("run_id")`` without a None guard (vendored harness
            # ``thread_data_middleware.py:110``), so we seed thread_id +
            # run_id here. Locked by U1 step 3.
            run_id = str(uuid.uuid4())
            astream_context = {"thread_id": thread_id, "run_id": run_id}
            async for event in agent_graph.astream(
                state, runnable_config, context=astream_context
            ):
                if cancellation_event and cancellation_event.is_set():
                    logger.info("[agent_dispatch] cancelled session=%s", thread_id)
                    break
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
                                # Include timestamp metadata for frontend duration calculation
                                # and shimmer animation activation (deerflow pattern)
                                yield builder_events.phase(
                                    "thinking",
                                    {"timestamp": time.time()}
                                ).to_ndjson()
                                thinking_started = True
                            if reasoning:
                                yield builder_events.token(
                                    reasoning, is_thinking=True
                                ).to_ndjson()
                            continue

                        if kind == "tool_call":
                            for call in _extract_tool_calls(msg):
                                tname = call["name"]
                                # Skip duplicate tool calls (same call_id already processed)
                                call_id = str(call["id"]) if call["id"] else str(uuid.uuid4())
                                if call_id in seen_tool_call_ids:
                                    logger.debug(
                                        "[agent_dispatch] Skipping duplicate tool.call id=%s name=%s",
                                        call_id, tname
                                    )
                                    continue
                                seen_tool_call_ids.add(call_id)

                                ttype, tdisplay, ticon, tkey = _resolve_tool_metadata(tname)
                                tools_used.append(tname)
                                evt = builder_events.tool_call(
                                    tool_name=tname,
                                    arguments=call["args"],
                                    display_name=tdisplay,
                                    icon=ticon,
                                    tool_type=ttype,
                                    display_key=tkey,
                                )
                                backend_id = evt.payload["tool"]["id"]
                                # Map call_id to backend_id for tool_result matching
                                tool_call_id_map[call_id] = backend_id
                                # Journal write BEFORE yield to ensure persistence on disconnect
                                try:
                                    session_journal.write_tool_call(
                                        family_id=family_id,
                                        session_id=thread_id,
                                        tool_name=tname,
                                        tool_id=backend_id,
                                        arguments=call["args"],
                                    )
                                except Exception as e:
                                    logger.warning("[agent_dispatch] journal write_tool_call failed: %s", e)
                                yield evt.to_ndjson()
                            continue

                        if kind == "tool_result":
                            provider_id, content = _extract_tool_result(msg)
                            # Generate UUID if provider_id missing to match tool_call behavior
                            if not provider_id:
                                provider_id = str(uuid.uuid4())
                            backend_id = tool_call_id_map.get(provider_id, provider_id)
                            # Generate result_summary for frontend display (deerflow pattern)
                            result_summary = _generate_tool_result_summary(content)

                            # Detect tool errors from content (DeerFlow pattern)
                            # Tools return errors in specific formats:
                            # - JSON with "error" field: {"error": "message"}
                            # - String starting with "Error:" or "Error "
                            tool_success = True
                            if content:
                                content_str = str(content)
                                # Check for JSON error format
                                try:
                                    import json
                                    parsed = json.loads(content_str)
                                    if isinstance(parsed, dict) and "error" in parsed:
                                        tool_success = False
                                except (json.JSONDecodeError, TypeError):
                                    # Not JSON, check for string error patterns
                                    if content_str.startswith("Error:") or content_str.startswith("Error "):
                                        tool_success = False

                            # Journal write BEFORE yield to ensure persistence on disconnect
                            try:
                                session_journal.write_tool_result(
                                    family_id=family_id,
                                    session_id=thread_id,
                                    tool_id=backend_id,
                                    success=tool_success,
                                    execution_time_ms=0,  # streaming path lacks timing metadata
                                )
                            except Exception as e:
                                logger.warning("[agent_dispatch] journal write_tool_result failed: %s", e)
                            # Tool messages from langchain don't carry success/timing —
                            # we detect success from content patterns (JSON error field or "Error:" prefix)
                            yield builder_events.tool_result(
                                tool_id=backend_id,
                                success=tool_success,
                                execution_time_ms=0,
                                data=content,
                                result_summary=result_summary,
                            ).to_ndjson()
                            continue

                        if kind == "text":
                            content = _extract_content(msg)
                            if not content:
                                continue
                            # Skip duplicate answer content (same hash as previous)
                            # This prevents the UI from showing duplicated text blocks
                            content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                            if content_hash == last_answer_hash and len(content) > 20:
                                logger.debug(
                                    "[agent_dispatch] Skipping duplicate answer content hash=%s len=%s",
                                    content_hash, len(content)
                                )
                                continue
                            last_answer_hash = content_hash

                            if not answering_started:
                                yield builder_events.phase("answering").to_ndjson()
                                answering_started = True
                            answer_parts.append(content)
                            yield builder_events.token(
                                content, is_thinking=False
                            ).to_ndjson()
        except Exception as e:
            stream_error_type = type(e).__name__
            logger.warning(
                "[agent_dispatch] astream failed session=%s err_type=%s",
                thread_id,
                stream_error_type,
            )

            # Report web search circuit failure if providers are configured
            # This triggers the circuit breaker backend to track failures
            web_search_providers = ai_config.get("web_search_providers", [])
            if web_search_providers:
                first_provider = web_search_providers[0]
                provider_id = first_provider.get("provider_id")
                if provider_id:
                    # Fire-and-forget circuit report — never blocks the error response
                    try:
                        await report_web_search_circuit(
                            family_id=family_id,
                            provider_id=int(provider_id),
                            failure_type=_classify_stream_error(e),
                        )
                    except Exception as exc:
                        logger.warning(
                            "circuit report failed family=%s provider=%s: %s",
                            family_id,
                            provider_id,
                            type(exc).__name__,
                        )

            yield builder_events.error(
                "智能体执行失败", code="STREAM_ERROR"
            ).to_ndjson()
            return

        # 10. Emit end
        elapsed_ms = int((time.monotonic() - t_start) * 1000)
        yield builder_events.end(
            summary="".join(answer_parts)[:200],
            tokens_used=0,
            execution_time_ms=elapsed_ms,
            tools_used=tools_used or None,
        ).to_ndjson()
        success = True
    finally:
        # Restore DEER_FLOW_EXTENSIONS_CONFIG_PATH env var
        if extensions_config_path and prev_extensions_env is not None:
            os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = prev_extensions_env
        elif extensions_config_path:
            os.environ.pop("DEER_FLOW_EXTENSIONS_CONFIG_PATH", None)

        audit_state["success"] = success
        # Audit emit FIRST so the invariant lands even if the persistence
        # fire-and-forget never runs (e.g. loop-shutdown teardown).
        _emit_audit(None if success else (stream_error_type or "StreamAborted"))
        # Schedule persistence as fire-and-forget so a slow backend write
        # never blocks the response close. _fire_and_forget no-ops cleanly
        # when no event loop is running (e.g. during teardown).
        if _fire_and_forget is not None:
            _fire_and_forget(_persist_session_metadata(
                agent_graph=agent_graph,
                runnable_config=runnable_config,
                family_id=family_id,
                user_id=user_id,
                session_id=thread_id,
                agent_id=str(agent_id),
                agent_name=agent_name,
                answer="".join(answer_parts),
                model_id=model_id,
                success=success,
                start_ms=t_start,
            ))


# ── Session persistence ─────────────────────────────────────────────────────


async def _build_fallback_title(
    family_id: str, agent_name: str, user_id: str | None
) -> str:
    """Build a `YYYY-MM-DD agent_name user_name` title.

    Mirrors orchestrator._generate_title's non-chat branch (kept as a copy
    rather than imported because the orchestrator helper is private and
    bundles LLM logic we don't want here). Truncated to 50 chars to fit
    ai_chat_sessions.title.
    """
    date_str = time.strftime("%Y-%m-%d", time.localtime())
    user_name = "匿名用户"
    if user_id:
        try:
            client = BackendClient(family_id=family_id)
            user_info = await client.get_user(user_id)
            if user_info:
                user_name = (
                    user_info.get("display_name")
                    or user_info.get("username")
                    or user_name
                )
        except Exception:
            logger.warning(
                "[agent_dispatch] fallback title user fetch failed family=%s",
                family_id,
            )
    return f"{date_str} {agent_name} {user_name}"[:50]


async def _persist_session_metadata(
    *,
    agent_graph: Any,
    runnable_config: dict[str, Any] | None,
    family_id: str,
    user_id: str | None,
    session_id: str,
    agent_id: str | None = None,
    agent_name: str,
    answer: str,
    model_id: str | None,
    success: bool,
    start_ms: float | None = None,
) -> None:
    """Persist title / summary / status to backend after the stream finishes.

    All inputs that came from user content (DeerFlow-generated title and the
    streamed assistant answer) pass through ``pii_redactor.redact_text``
    before being written — required by agent/CLAUDE.md Key Invariant #1.

    Failure modes:
    - ``aget_state`` missing or raising → fall back to date+name template
    - ``_get_shared_checkpointer`` not bound → fall back to date+name template
    - backend write raises → swallowed by AiSessionRepository.update_summary
    """
    raw_title: str | None = None
    if agent_graph is not None and runnable_config is not None:
        aget_state = getattr(agent_graph, "aget_state", None)
        try:
            if aget_state is not None:
                snapshot = await aget_state(runnable_config)
            else:
                # Older langgraph versions only expose sync get_state.
                loop = asyncio.get_running_loop()
                snapshot = await loop.run_in_executor(
                    None, agent_graph.get_state, runnable_config
                )
            values = getattr(snapshot, "values", None) or {}
            raw_title_val = values.get("title") if isinstance(values, dict) else None
            if isinstance(raw_title_val, str) and raw_title_val.strip():
                raw_title = raw_title_val
        except Exception as e:
            # Never log str(e) — state payloads can include the conversation.
            logger.warning(
                "[agent_dispatch] aget_state failed session=%s err_type=%s",
                session_id,
                type(e).__name__,
            )

    title: str | None = None
    if raw_title:
        redacted_title, _ = pii_redactor.redact_text(raw_title)
        # Strip HTML-style tags so a future v-html consumer can't execute
        # markup smuggled in by the LLM. Plan §Risks row 6 — the existing
        # frontend uses mustache (safe) but defence-in-depth keeps the DB clean.
        redacted_title = re.sub(r"<[^>]+>", "", redacted_title)
        if redacted_title.strip():
            title = redacted_title.strip()[:50]
    if not title:
        try:
            title = await _build_fallback_title(family_id, agent_name, user_id)
        except Exception:
            logger.warning(
                "[agent_dispatch] fallback title build failed session=%s",
                session_id,
            )
            title = None

    redacted_answer = ""
    if answer:
        redacted_answer, _ = pii_redactor.redact_text(answer)
    summary: str | None = None
    if redacted_answer.strip():
        summary = redacted_answer.strip()[:200]

    # Journal — assistant_message and session_end. session_journal.append_event
    # already logs and swallows file I/O errors, but resolve_path can raise on
    # invalid id slugs; guard the whole block.
    try:
        if redacted_answer:
            session_journal.write_assistant_message(
                family_id=family_id,
                session_id=session_id,
                content=redacted_answer,
                model_name=model_id,
            )
        duration_ms = (
            int((time.monotonic() - start_ms) * 1000) if start_ms is not None else 0
        )
        session_journal.write_session_end(
            family_id=family_id,
            session_id=session_id,
            success=success,
            duration_ms=duration_ms,
            tokens_used=0,
        )
    except Exception:
        logger.warning(
            "[agent_dispatch] journal end-of-stream write failed session=%s",
            session_id,
        )

    try:
        from apps.agent.services.session_store import AiSessionRepository

        repo = AiSessionRepository(family_id)
        await repo.upsert(
            session_id=session_id,
            family_id=family_id,
            user_id=user_id,
            agent_id=agent_id,
            last_model=model_id,
        )
        await repo.update_summary(
            session_id=session_id,
            family_id=family_id,
            summary=summary,
            model=model_id,
            status="completed" if success else "error",
            title=title,
        )
    except Exception as e:
        logger.warning(
            "[agent_dispatch] persist failed session=%s err_type=%s",
            session_id,
            type(e).__name__,
        )
