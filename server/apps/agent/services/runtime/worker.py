"""Background agent execution for family-scoped runs.

This is the Numina equivalent of DeerFlow's ``run_agent()`` worker.  Unlike
DeerFlow (which calls ``agent.astream()`` directly on a LangGraph graph built
by ``make_lead_agent``), the Numina version delegates to the existing
``DeerFlowAdapter.typed_stream_dispatch()`` — this preserves Numina's per-family
adapter caching, PII redaction, and audit logging while gaining the
``StreamBridge`` + ``RunManager`` lifecycle.

# [Integrated with Numina Multi-Tenant] — family-scoped agent execution
# Preserves Numina's PII redaction (K.I. #1) and audit logging (K.I. #3)
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any

import json_repair
from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.message_classifier import (
    extract_tool_calls,
    resolve_tool_metadata,
)
from apps.agent.services.pii_redactor import pii_redactor

from .gc import schedule_run_cleanup
from .run_extras import generate_suggestions, sync_title_from_checkpoint
from .sandbox_provider import set_family_sandbox_context

logger = logging.getLogger(__name__)

# Track fire-and-forget background tasks so they don't get garbage collected prematurely
_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    """Track a background task and auto-remove it when done."""
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _background_tasks.discard(t))


async def run_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
    stream_modes: list[str] | None = None,
    resume_answer: str | None = None,
    interrupt_id: str | None = None,
) -> None:
    """Multi-app dispatch entry point.

    Reads ``record.metadata["app"]`` (default ``"numina"``) and delegates to
    the matching per-app runner. The NuminaLocalSandboxProvider relies on a
    coroutine-scoped family_id ContextVar (set here, in every branch) so that
    write_file/read_file/str_replace resolve to the family-scoped sandbox —
    without this the provider falls back to family_id="unknown" and tenant
    isolation silently fails (Resolved-3 blocker A).

    Apps:
      - ``numina``        → ``_run_numina_agent`` (the /ai/chat path, live).
      - ``asset-report``  → ``_run_asset_report_pipeline`` (U4 will land the
                            3-step pipeline; until then a 503-style error is
                            published so any premature dispatch is a handled
                            error, not a runtime crash — Finding 15).
      - ``import-parse``  → ``_run_import_parse_agent`` (U8; 503 placeholder).

    The allowlist preventing unknown / asset-report / import-parse values from
    reaching here is enforced upstream in ``sse_gateway.start_run`` (R1 gate).
    """
    # Resolved-3 blocker A: set the family_id ContextVar before any sandbox
    # tool (write_file/read_file) can be invoked. Must run in all branches —
    # numina and import-parse also depend on it once native tools are enabled.
    set_family_sandbox_context(family_id)

    app = record.metadata.get("app", "numina") if record.metadata else "numina"
    if app == "asset-report":
        await _run_asset_report_pipeline(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            graph_input=graph_input,
            config=config,
        )
        return
    if app == "import-parse":
        await _run_import_parse_agent(
            bridge=bridge,
            run_manager=run_manager,
            record=record,
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            graph_input=graph_input,
            config=config,
        )
        return
    # Default / "numina"
    await _run_numina_agent(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        graph_input=graph_input,
        config=config,
        stream_modes=stream_modes,
        resume_answer=resume_answer,
        interrupt_id=interrupt_id,
    )


async def _publish_not_ready(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    app: str,
    landing_unit: str,
) -> None:
    """Publish a 503-style error for a dispatch branch whose pipeline is not
    yet implemented.

    Finding 15: placeholders must surface a *handled* error (frontend can show
    a graceful message) rather than ``raise NotImplementedError`` (a runtime
    crash). Marks the run ``error`` and publishes ``error`` + ``end`` frames
    so the SSE stream closes cleanly.

    Args:
        app: The app value that was dispatched (e.g. ``"asset-report"``).
        landing_unit: The plan unit that will implement this branch
            (e.g. ``"U4"`` / ``"U8"``).
    """
    run_id = record.run_id
    message = f"{app} 流水线未就绪，待 {landing_unit} 落地"
    logger.warning("[run_agent] %s (app=%s run=%s)", message, app, run_id)
    await run_manager.set_status(run_id, RunStatus.error, error=message)
    await bridge.publish(run_id, "error", {"message": message, "name": "NotImplemented"})
    await bridge.publish(run_id, "end", {"status": "error"})
    await bridge.publish_end(run_id)
    asyncio.create_task(bridge.cleanup(run_id, delay=60))


async def _run_asset_report_pipeline(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
) -> None:
    """Asset-report 3-step pipeline dispatch branch (U4).

    Runs a single ``stream_run`` agent run via ``adapter.typed_stream_dispatch``
    with ``skill_name="asset-report"``. The skill prompt (see
    ``skills/builtin/public/asset-report/SKILL.md``) drives the LLM through the
    three steps in one run: step 1 family-data MCP + ``write_file`` (markdown
    audit) → step 2 ``read_file`` + indicators JSON output → step 3 worker
    json-repair + persist (persistence lands in a follow-up step; this worker
    only forwards frames and emits ``report.step2_json``).

    KTD-7 (P0 pilot verified 2026-07-18): single agent run single-pass success
    rate = 18/20 (90%) ≥ 80% gate, so the single-run pipeline is viable — no
    fallback to two-skill NDJSON orchestration.

    Mirrors ``_run_numina_agent`` for config/MCP setup + stream forwarding +
    tool_call/tool_result custom-event synthesis so the frontend reuses the
    chat renderer. Differences vs chat:
    - ``skill_name="asset-report"`` (fixed system flow, KTD-8).
    - Synthetic trigger message ``/asset-report 生成家庭资产报告`` (plan L117:
      report runs have no natural user message; backend-initiated).
    - ``plan_mode=False``: fixed 3-step flow, no TodoMiddleware (plan_mode=True
      in the pilot script was a leftover assumption that aggravated the
      run 17-18 Recursion-100 drift; production uses False for stability).
    - No suggestions / title / interrupt handling (report is not a chat).
    - Step 3 (worker-synthesized): on stream end, parse the accumulated AI
      text JSON via ``json_repair`` and emit exactly one ``report.step2_json``
      custom event before the ``end`` frame (plan step 3 fallback path —
      middleware ``get_stream_writer()`` emission is preferred but requires
      an adapter middleware-injection point not yet present).
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
    selected_provider: dict[str, Any] | None = None
    ai_response_parts: list[str] = []
    cumulative_usage: dict[str, int] | None = None

    try:
        # 1. Mark running + publish metadata (DeerFlow pattern)
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(
            run_id,
            "metadata",
            {"run_id": run_id, "thread_id": thread_id},
        )

        # 2. Fetch per-family AI config (tenant-isolated) — mirrors _run_numina_agent.
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        # NOTE: ai_config providers carry ai_provider/ai_model_id, not is_active
        # (DB is_active is not mapped into the config dict). next() falls back
        # to providers[0]; Demo Family's [0] happens to be active. This is a
        # pre-existing worker assumption, not introduced here.
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers (same MCP-setup as _run_numina_agent).
        try:
            mcp_servers = await client.get_enabled_mcp_servers()
            for srv in mcp_servers:
                if srv.get("name") == "Numina Backend MCP":
                    expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
                    actual_url = (srv.get("url") or "").rstrip("/")
                    if not actual_url.startswith(expected_prefix):
                        srv["url"] = (
                            expected_prefix
                            + "/api/v1/internal/mcp/"
                            + family_id
                            + "/sse"
                        )
                    mcp_headers: dict[str, str] = {
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Family-Id": family_id,
                    }
                    if user_id:
                        mcp_headers["X-Caller-User-Id"] = user_id
                    srv["headers"] = mcp_headers
                    break
        except Exception as exc:
            logger.warning(
                "[_run_asset_report_pipeline] get_enabled_mcp_servers failed family=%s err=%s",
                family_id, type(exc).__name__,
            )
            mcp_servers = []

        # 4. Build adapter. plan_mode=False (fixed 3-step flow, no TodoList).
        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
        )

        # 5. Synthetic trigger message (plan L117): report runs are backend-
        # initiated with no natural user message. Use the slash-activation form
        # so the LLM loads asset-report/SKILL.md (not chat/SKILL.md). If the
        # backend already supplied a user message in graph_input, prefer it.
        user_message = _SYNTHETIC_ASSET_REPORT_TRIGGER
        if graph_input and "messages" in graph_input:
            msgs = graph_input["messages"]
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") in ("user", "human"):
                    content = last.get("content", "")
                    if content:
                        user_message = content

        # 6. PII redaction (Key Invariant #1)
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge. Set the
        # active skill so sync_tool_patch filters tools to asset-report's
        # declared allowed-tools whitelist.
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )
        _skill_token = set_active_skill("asset-report")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="asset-report",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=False,  # Qwen3: avoid empty content (see memory qwen3-enable-thinking-empty-content)
        ):
            if record.abort_event.is_set():
                break

            if sse_type == "end":
                if isinstance(data, dict) and data.get("usage"):
                    raw_usage = data["usage"]
                    cumulative_usage = {
                        "input_tokens": raw_usage.get("input_tokens", 0),
                        "output_tokens": raw_usage.get("output_tokens", 0),
                        "total_tokens": raw_usage.get("total_tokens", 0),
                    }
                break
            if sse_type == "error":
                await bridge.publish(run_id, "error", data)
                break

            # Forward the canonical frame (messages / values / custom).
            await bridge.publish(run_id, sse_type, data)

            # Mirror _run_numina_agent: collect AI text + synthesize tool_call/
            # tool_result custom events so the frontend reuses the chat renderer.
            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    content = data.get("content")
                    if content:
                        ai_response_parts.append(content)
                    tool_calls = data.get("tool_calls")
                    if tool_calls:
                        for tc in extract_tool_calls(data):
                            raw_name = tc.get("name", "")
                            tool_type, display_name, icon, display_key = resolve_tool_metadata(raw_name)
                            payload: dict[str, Any] = {
                                "type": "tool_call",
                                "tool_call_id": tc.get("id", ""),
                                "tool_name": raw_name,
                                "args": tc.get("args", {}),
                                "display_name": display_name,
                                "icon": icon,
                                "tool_type": tool_type,
                            }
                            if display_key:
                                payload["display_key"] = display_key
                            await bridge.publish(run_id, "custom", payload)
                elif msg_type == "tool":
                    tool_call_id = str(data.get("tool_call_id") or "")
                    tool_name = data.get("name") or ""
                    content = data.get("content")
                    if tool_call_id:
                        await bridge.publish(run_id, "custom", {
                            "type": "tool_result",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "content": content,
                        })

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Step 3 worker-synthesized report.step2_json: parse the accumulated
        # AI text (the final ```json block) via json_repair and emit exactly one
        # custom event BEFORE the end frame (plan step 3 fallback path; timing
        # contract per plan — report.step2_json strictly precedes end).
        if completion_status == "complete":
            step2_payload = _parse_report_json("".join(ai_response_parts))
            if step2_payload is not None:
                await bridge.publish(run_id, "custom", {
                    "type": "report.step2_json",
                    "payload": step2_payload,
                })

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning("[_run_asset_report_pipeline] failed run=%s err=%s", run_id, error_type)
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
        # Clear the active-skill ContextVar so it cannot leak into a later run.
        if "_skill_token" in locals():
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )
            reset_active_skill(_skill_token)

        # 10. Audit log (Key Invariant #3)
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                capability="asset-report",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow
        # pattern). No suggestions/title (report is not a chat).
        end_payload = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


# Synthetic trigger for asset-report runs (plan L117: backend-initiated runs
# have no natural user message; slash form steers skill loading to asset-report).
_SYNTHETIC_ASSET_REPORT_TRIGGER = "/asset-report 生成家庭资产报告"


def _parse_report_json(ai_text: str) -> dict | None:
    """Parse the indicators JSON from the asset-report AI output.

    Tries fenced ```json blocks first, then the bare text, via json_repair
    (tolerant of trailing commas / minor syntax drift). Returns None on failure
    so the caller can skip emitting ``report.step2_json`` (plan F8: step2
    incomplete => 0 events).
    """
    if not ai_text:
        return None

    fence_re = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
    candidates: list[str] = [m.group(1) for m in fence_re.finditer(ai_text)]
    candidates.append(ai_text)
    for cand in candidates:
        try:
            parsed = json_repair.repair_json(cand, return_objects=True)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None


async def _run_import_parse_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
) -> None:
    """Import-parse (3rd stream_run agent) dispatch branch.

    U2 placeholder: the import-parse agent is implemented in U8. Until then
    backend ``/import/parse-pdf`` should keep using the legacy
    ``dispatch(capability="import_parse")`` path (U2 Finding 15).
    """
    await _publish_not_ready(
        bridge=bridge,
        run_manager=run_manager,
        record=record,
        app="import-parse",
        landing_unit="U8",
    )


async def _run_numina_agent(
    *,
    bridge: StreamBridge,
    run_manager: RunManager,
    record: RunRecord,
    family_id: str,
    user_id: str | None,
    thread_id: str,
    graph_input: dict | None,
    config: dict[str, Any],
    stream_modes: list[str] | None = None,
    resume_answer: str | None = None,
    interrupt_id: str | None = None,
) -> None:
    """Background agent execution for the Numina (/ai/chat) application.

    Publishes events to the ``StreamBridge`` and uses the ``RunManager`` for
    lifecycle tracking.  Runs inside ``asyncio.create_task()`` so it does not
    block the SSE response.

    Key patterns preserved from DeerFlow ``run_agent``:
    - ``await run_manager.set_status(run_id, RunStatus.running)`` at start
    - ``await bridge.publish(run_id, "metadata", ...)`` as first event
    - ``record.abort_event.is_set()`` checks for cooperative cancellation
    - Terminal status ``success`` / ``error`` / ``interrupted``
    - ``await bridge.publish_end(run_id)`` in ``finally``
    - Deferred ``bridge.cleanup(run_id, delay=60)`` in ``finally``

    # [Copied from DeerFlow Reference] — patterns from runtime/runs/worker.py
    # [Integrated with Numina Multi-Tenant] — family_id scoping
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    # Completion status surfaced to the client in the `end` frame (Q2). Default
    # to "error" so an unexpected path never reports "complete" falsely.
    completion_status = "error"
    # Set True when the adapter stream yields a custom event with
    # type="interrupt" (LangGraph interrupt() call from ask_clarification).
    # Distinct from abort_event (user-initiated cancel) — interrupted runs
    # skip the 300s cleanup GC so the checkpoint state is preserved for resume.
    interrupted_by_event = False
    # Stream-extras inputs — initialised here so the ``finally`` block is safe
    # when the run aborts before streaming starts. Title/suggestion generation
    # are skipped when ``selected_provider`` stays None.
    selected_provider: dict[str, Any] | None = None
    user_message = ""
    ai_response_parts: list[str] = []
    # Cumulative token usage from the adapter's `end` event (DeerFlow pattern).
    # Captured here so the worker's own `end` frame can include it.
    cumulative_usage: dict[str, int] | None = None

    try:
        # 1. Mark running + publish metadata (DeerFlow pattern)
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(
            run_id,
            "metadata",
            {
                "run_id": run_id,
                "thread_id": thread_id,
            },
        )

        # 2. Fetch per-family AI config (tenant-isolated)
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers so the chat skill can query family data
        # via MCP tools (get_family_overview, get_assets, ...). Without this,
        # _generate_temp_config writes no extensions_config.json and DeerFlow
        # loads zero MCP tools - the agent then falls back to the empty context
        # fields injected by _build_prompt and reports "all records empty".
        # Mirrors the same logic in agent_dispatch.stream_agent_dispatch.
        try:
            mcp_servers = await client.get_enabled_mcp_servers()
            for srv in mcp_servers:
                if srv.get("name") == "Numina Backend MCP":
                    expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
                    actual_url = (srv.get("url") or "").rstrip("/")
                    if not actual_url.startswith(expected_prefix):
                        srv["url"] = (
                            expected_prefix
                            + "/api/v1/internal/mcp/"
                            + family_id
                            + "/sse"
                        )
                    # Auth headers required by the backend MCP SSE handshake
                    # (X-Caller-User-Id is mandatory; without it the SSE endpoint 403s).
                    # Only attach headers to the Numina Backend MCP entry, not to all servers.
                    mcp_headers: dict[str, str] = {
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Family-Id": family_id,
                    }
                    if user_id:
                        mcp_headers["X-Caller-User-Id"] = user_id
                    srv["headers"] = mcp_headers
                    break
        except Exception as exc:
            logger.warning(
                "[_run_numina_agent] get_enabled_mcp_servers failed family=%s err=%s",
                family_id, type(exc).__name__,
            )
            mcp_servers = []

        # 4a. Extract per-call execution-mode overrides from the RunnableConfig.
        # The frontend sends these in config.configurable (see reference
        # backend/app/gateway/services.py:merge_run_context_overrides). They
        # control DeerFlow's tool loading (subagent_enabled -> task tool) and
        # planning middleware (plan_mode -> TodoList/write_todos) on a per-call
        # basis.
        #
        # IMPORTANT: These values MUST be passed to create_family_adapter as
        # init-time parameters (not just per-call overrides). The cache key in
        # family_adapter_cache.py includes (subagent_enabled, plan_mode), so
        # different mode combinations get distinct DeerFlowClient instances.
        # If we pass hardcoded False here, the DeerFlowClient is created with
        # plan_mode=False, and while _ensure_agent() can rebuild the agent when
        # per-call plan_mode=True arrives via stream(), this causes unnecessary
        # agent rebuilds on every call and may miss the TodoMiddleware's
        # write_todos tool if the rebuild doesn't fire correctly.
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        call_subagent_enabled = bool(configurable.get("subagent_enabled", False))
        call_plan_mode = bool(configurable.get("is_plan_mode", False))
        call_thinking_enabled = bool(configurable.get("thinking_enabled", True))
        call_websearch_enabled = bool(configurable.get("websearch_enabled", False))

        # 4. Build adapter (uses per-family LRU cache from family_adapter_cache.py)
        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=call_subagent_enabled,
            plan_mode=call_plan_mode,
            mcp_servers=mcp_servers,
        )

        # 5. Extract user message for context
        if graph_input and "messages" in graph_input:
            msgs = graph_input["messages"]
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") in ("user", "human"):
                    user_message = last.get("content", "")

        # 5a. Web-search behavioral guidance lives in the skill files:
        # chat-search/SKILL.md ("联网搜索使用原则") and chat/SKILL.md ("不要尝试联网搜索").
        # The skill is selected below (chat-search vs chat) based on call_websearch_enabled,
        # so no runtime injection is needed — and injecting here would leak
        # internal guidance into user-visible prompts.
        # Only use chat-search when actual search capability is configured.
        # Otherwise the model is told it can search but has no tools → hallucinated searches.
        has_search_capability = bool(
            ai_config.get("web_search_providers") or ai_config.get("web_search_mcp_servers")
        )

        # 5b. Skill discovery is handled natively by DeerFlow: apply_prompt_template
        # renders <skill_system> (with <available_skills> listing the active skill's
        # metadata) into the system prompt, filtered by available_skills passed to
        # DeerFlowClient. The LLM then calls read_file to load the full SKILL.md.
        # The former self-built <skill_index> user-message injection duplicated this
        # and leaked internal guidance into the user-visible message, so it was removed.

        # 6. PII redaction (Key Invariant #1)
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge.
        # Collect AI text for suggestions, and synthesize `tool_call` custom
        # events from `messages` frames so R6 (规划步骤) renders under v2 —
        # the legacy runs.py router did this inline; the v2 worker must too,
        # because typed_stream_dispatch yields raw LangGraph `messages` events
        # (with tool_calls on the AI message) rather than pre-split tool_call
        # chunks. See services/deerflow_adapter/adapter.py:typed_stream_dispatch.
        capability = "chat-search" if (call_websearch_enabled and has_search_capability) else "chat"
        # Set the active skill so sync_tool_patch can filter tools to this skill's
        # declared allowed-tools whitelist (see active_skill_context module docstring).
        from apps.agent.services.deerflow_adapter.active_skill_context import set_active_skill
        _skill_token = set_active_skill(capability)
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name=capability,
            context=redacted,
            thread_id=thread_id,
            enable_thinking=call_thinking_enabled,
            subagent_enabled=call_subagent_enabled,
            plan_mode=call_plan_mode,
            resume_answer=resume_answer,
        ):
            # Cooperative cancellation check (DeerFlow pattern)
            if record.abort_event.is_set():
                break

            if sse_type == "end":
                # Capture cumulative usage from DeerFlow before breaking.
                # The adapter yields ("end", {"usage": {...}}) from
                # DeerFlowClient.stream() end event.
                if isinstance(data, dict) and data.get("usage"):
                    raw_usage = data["usage"]
                    cumulative_usage = {
                        "input_tokens": raw_usage.get("input_tokens", 0),
                        "output_tokens": raw_usage.get("output_tokens", 0),
                        "total_tokens": raw_usage.get("total_tokens", 0),
                    }
                break
            if sse_type == "error":
                await bridge.publish(run_id, "error", data)
                break

            # Forward the canonical frame (messages / values / custom).
            await bridge.publish(run_id, sse_type, data)

            # Mirror runs.py:223-236 — collect AI text and synthesize
            # `tool_call` custom events from the AI message's tool_calls so
            # the frontend planning-steps UI (R6) updates in real time.
            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")

                if msg_type == "ai":
                    content = data.get("content")
                    tool_calls = data.get("tool_calls")
                    msg_id = data.get("id")
                    logger.info(
                        "[_run_numina_agent] AI message received: run=%s id=%s content_len=%d has_tool_calls=%s",
                        run_id, msg_id, len(content) if content else 0, bool(tool_calls),
                    )
                    if content:
                        ai_response_parts.append(content)
                    else:
                        logger.warning(
                            "[_run_numina_agent] AI message with empty content: run=%s data_keys=%s",
                            run_id, list(data.keys()),
                        )
                    tool_calls_raw = tool_calls
                    if tool_calls_raw:
                        # Use extract_tool_calls to properly handle LangChain ToolCall objects
                        for tc in extract_tool_calls(data):
                            raw_name = tc.get("name", "")
                            # Resolve display metadata (display_name/icon/tool_type/
                            # display_key) the same way agent_dispatch.py does, so the
                            # /ai/chat planning-steps UI shows readable Chinese action
                            # labels (e.g. "查询资产数据") instead of raw tool names
                            # (e.g. "Numina Backend MCP_get_assets").
                            tool_type, display_name, icon, display_key = resolve_tool_metadata(raw_name)
                            payload: dict[str, Any] = {
                                "type": "tool_call",
                                "tool_call_id": tc.get("id", ""),
                                "tool_name": raw_name,
                                "args": tc.get("args", {}),
                                "display_name": display_name,
                                "icon": icon,
                                "tool_type": tool_type,
                            }
                            if display_key:
                                payload["display_key"] = display_key
                            await bridge.publish(run_id, "custom", payload)

                elif msg_type == "tool":
                    # Tool result message — forward to frontend so ChainOfThought
                    # can update step status from 'running' to 'done' and display
                    # artifact links (which require status === 'done').
                    tool_call_id = str(data.get("tool_call_id") or "")
                    tool_name = data.get("name") or ""
                    content = data.get("content")
                    if tool_call_id:
                        await bridge.publish(run_id, "custom", {
                            "type": "tool_result",
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "content": content,
                        })

            # Detect LangGraph interrupt() events forwarded by the adapter as
            # custom events with type="interrupt".  Set the flag so the
            # terminal-status block below marks the run as ``interrupted``
            # (distinct from ``cancelled`` via abort_event) and the finally
            # block skips the 300s cleanup GC — the checkpoint must survive
            # so the user can resume after providing human input.
            if sse_type == "custom" and isinstance(data, dict) and data.get("type") == "interrupt":
                interrupted_by_event = True

        # 8. Terminal status — drives the `end` completion signal (Q2).
        # Two paths to ``interrupted``: (a) user-initiated cancel via
        # abort_event, (b) LangGraph interrupt() detected as a custom event
        # in the stream (ask_clarification tool). Both preserve the checkpoint
        # so the run can be resumed, but only (a) sets abort_event.
        if record.abort_event.is_set() or interrupted_by_event:
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
        success = record.status == RunStatus.success

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning("[_run_numina_agent] failed run=%s err=%s", run_id, error_type)
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
        # Clear the active-skill ContextVar so it cannot leak into a later run
        # reusing this thread/coroutine. Guarded: _skill_token is only set if
        # dispatch reached the skill-selection step (line ~234).
        if "_skill_token" in locals():
            from apps.agent.services.deerflow_adapter.active_skill_context import reset_active_skill
            reset_active_skill(_skill_token)

        # 9. Audit log (Key Invariant #3)
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                capability="chat",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )
        # 10. Terminal frames: follow-up suggestions (R8), `end` with completion
        # status (Q2), and fire-and-forget title generation — then the end
        # sentinel + deferred cleanup (DeerFlow pattern).
        #
        # R8: generate follow-up suggestions BEFORE publishing `end`, because
        # the frontend attaches suggestions to the last AI message in the `end`
        # handler. If suggestions arrive after `end`, they are silently dropped.
        # — NOT the whole ``ai_config`` envelope, which nests provider keys
        # (api_key/ai_model_id/ai_base_url) under ``providers``. Passing the
        # envelope leaves every key unset, so the suggestions LLM falls back
        # to a dummy key and silently 401s. Skipped when the run aborted
        # before a provider was selected OR when the run was cancelled/interrupted.
        if completion_status == 'complete' and selected_provider is not None:
            ai_response = "".join(ai_response_parts)
            suggestions = await generate_suggestions(ai_response, user_message, selected_provider)
            if suggestions:
                await bridge.publish(run_id, "custom", {
                    "type": "suggestions",
                    "suggestions": suggestions,
                })

        # Q2: publish a real `end` data frame carrying the completion status
        # so the frontend can distinguish a clean completion from a truncated
        # stream (#19) without guessing from content. publish_end() below only
        # signals the sentinel (data=None), so the data frame must precede it.
        # Include cumulative token usage from DeerFlow when available.
        end_payload = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        if completion_status == 'complete' and selected_provider is not None:
            # Sync / generate the thread title. DeerFlow's TitleMiddleware
            # writes to the checkpoint, but Numina's adapter runs the sync
            # ``stream()`` path so only the sync ``after_model`` hook fires -
            # that returns a local fallback (the raw ``[SKILL:chat]`` wrapper),
            # never an LLM summary. sync_title_from_checkpoint generates a
            # proper title via the family provider when the checkpoint title is
            # a fallback. Best-effort, fire-and-forget.
            task = asyncio.create_task(
                sync_title_from_checkpoint(
                    thread_id,
                    family_id,
                    ai_config=selected_provider,
                    user_message=user_message,
                    ai_response="".join(ai_response_parts),
                )
            )
            _track_task(task)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        # Skip the 300s cleanup GC for interrupted runs — the checkpoint must
        # be preserved so the user can resume after providing human input.
        # Cancelled runs (abort_event) still get cleaned up after 300s.
        if not interrupted_by_event:
            asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))
