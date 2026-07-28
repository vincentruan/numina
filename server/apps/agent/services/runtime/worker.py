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
import shutil
import time
from pathlib import Path
from typing import Any, cast

from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.goal_evaluator import (
    GoalEvaluationError,
    evaluate_goal_completion,
)
from apps.agent.services.goal_store import (
    GoalWriteConflict,
    attach_goal_evaluation,
    compute_no_progress_count,
    goal_thread_lock,
    latest_visible_assistant_signature,
    make_goal_continuation_message,
    read_thread_goal,
    should_continue_goal,
    visible_conversation_signature,
    write_thread_goal,
)
from apps.agent.services.message_classifier import (
    extract_tool_calls,
    resolve_tool_metadata,
)
from apps.agent.services.pii_redactor import pii_redactor
from packages.core import get_path_manager

from .asset_report_middleware import parse_report_json
from .gc import schedule_run_cleanup
from .run_extras import generate_suggestions, sync_title_from_checkpoint
from .sandbox_provider import reset_family_sandbox_context, set_family_sandbox_context

logger = logging.getLogger(__name__)

# LLM-declared filename in the asset-report AI text (SKILL.md §文件命名规则):
# ``WRITE_FILE: report_{YYYYMMDD_HHMMSS}.md``. The native write_file tool only
# returns ``"OK"`` (not a path), so the skill prompt instructs the LLM to
# declare the filename it wrote — worker parses this to locate the sandbox file.
_WRITE_FILE_DECL_RE = re.compile(
    r"WRITE_FILE:\s*(report_[a-zA-Z0-9_-]+\.md)", re.IGNORECASE
)
# Canonical report filename pattern (mirrors PathManager._REPORT_FILENAME_PATTERN)
# — used to validate filenames recovered from write_file tool_call args.path.
_REPORT_FILENAME_RE = re.compile(r"^report_[a-zA-Z0-9_-]+\.md$")

# Track fire-and-forget background tasks so they don't get garbage collected prematurely
_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    """Track a background task and auto-remove it when done."""
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _background_tasks.discard(t))


def _deerflow_default_workspace_md(
    thread_id: str, user_id: str | None, filename: str
) -> Path | None:
    """Resolve the DeerFlow host sandbox workspace path for a filename.

    With the unified DeerFlow layout (2026-07-19), ``set_family_sandbox_context``
    sets ``_current_user`` so ``get_effective_user_id()`` returns ``family_id``.
    write_file therefore lands at
    ``{DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/user-data/workspace/<file>``,
    and this function resolves exactly that path.

    Returns the resolved Path, or None if DeerFlow's paths API is unavailable.

    ``effective_user`` is DeerFlow's own resolution (``get_effective_user_id``,
    now family_id after set_current_user). The ``user_id`` arg is accepted for
    symmetry but the effective DeerFlow user is always queried fresh so it
    matches whatever ``write_file`` actually used at runtime.
    """
    try:
        from deerflow.config.paths import get_paths
        from deerflow.runtime.user_context import get_effective_user_id
    except Exception:
        return None
    try:
        # user_id arg is intentionally not used for path resolution — see above.
        _ = user_id
        effective_user = get_effective_user_id()
        host_workspace = get_paths().host_sandbox_work_dir(
            thread_id, user_id=effective_user
        )
        return Path(host_workspace) / filename
    except Exception:
        return None


def _copy_asset_report_markdown(
    *,
    family_id: str,
    thread_id: str,
    run_id: str,
    user_id: str | None,
    ai_text: str,
    write_file_paths: list[str],
) -> str | None:
    """U4 step 3 / R5 path 契约: copy the step-1 markdown audit from the
    per-thread sandbox into the tenant reports directory, returning the
    persisted filename for ``AIReport.markdown_file_path``.

    The source filename is resolved in priority order:
    1. ``write_file`` tool_call ``args.path`` (most reliable — e2e showed the
       LLM often omits the ``WRITE_FILE:`` text declaration from AI message
       content even when it calls ``write_file`` with a real path).
    2. ``WRITE_FILE: <filename>`` declaration in the AI text (SKILL.md
       §文件命名规则 instructs the LLM to declare it; the native ``write_file``
       tool only returns ``"OK"`` so the filename must be recovered elsewhere).

    The source sandbox file lives at
    ``AGENT_DATA_DIR/{family_id}/sandboxes/{thread_id}/workspace/<filename>``.

    The persisted filename is server-generated (plan R5 文件名碰撞防御):
    ``report_{YYYYMMDD_HHMMSS}_{run_id[:8]}.md`` — the LLM's timestamp plus a
    ``run_id`` suffix to eliminate same-second collision across retried/queued
    runs. Matches ``^report_[a-zA-Z0-9_-]+\\.md$`` (``_`` already allowed).

    Returns ``None`` (and logs) when no filename is recoverable or the sandbox
    file is missing — persistence is best-effort, a failure must not fail the run.
    """
    declared_filename: str | None = None

    # 1. Prefer write_file tool_call args.path — extract the basename.
    for wf_path in write_file_paths:
        candidate = Path(wf_path).name
        if _REPORT_FILENAME_RE.match(candidate):
            declared_filename = candidate
            break

    # 2. Fallback: WRITE_FILE: <filename> declaration in AI text.
    if declared_filename is None:
        decl = _WRITE_FILE_DECL_RE.search(ai_text)
        if decl is not None:
            declared_filename = decl.group(1)

    if declared_filename is None:
        logger.warning(
            "[_run_asset_report_pipeline] no write_file path or WRITE_FILE "
            "declaration recovered, markdown_file_path not persisted run=%s "
            "(write_file_paths=%s)",
            run_id,
            write_file_paths,
        )
        return None

    # Source: locate the sandbox markdown the LLM wrote via write_file. With the
    # unified DeerFlow layout (2026-07-19), write_file always lands at:
    #   {DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/user-data/workspace/<file>
    # (family_id is set as DeerFlow's effective user via set_current_user in
    # set_family_sandbox_context, so LocalSandbox._resolve_path + thread_data both
    # resolve to the same path). write_file tool_call args.path is often empty in
    # the SSE messages event (LangGraph fills positional args at execution time),
    # so we cannot rely on write_file_paths alone — resolve the host workspace
    # dir via DeerFlow's paths API + the declared filename.
    declared_filename_str = declared_filename
    source_path = _deerflow_default_workspace_md(
        thread_id, user_id, declared_filename_str
    )
    if source_path is None or not source_path.is_file():
        logger.warning(
            "[_run_asset_report_pipeline] sandbox markdown not found at %s "
            "(DeerFlow layout), markdown_file_path not persisted run=%s "
            "(declared_filename=%s)",
            source_path,
            run_id,
            declared_filename_str,
        )
        return None

    # Target: tenant reports dir, server-generated filename with run_id suffix.
    # Reuse the LLM's timestamp (already validated to match report_*.md) and
    # append run_id[:8] for same-second collision defense.
    stem = declared_filename[:-3]  # strip ".md"
    persisted_filename = f"{stem}_{run_id[:8]}.md"
    try:
        pm = get_path_manager()
        # tenant_report_file validates the filename pattern + family_id scope.
        target_path = pm.tenant_report_file(int(family_id), persisted_filename)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target_path)
        logger.info(
            "[_run_asset_report_pipeline] persisted markdown %s -> %s run=%s",
            source_path,
            target_path,
            run_id,
        )
        return persisted_filename
    except Exception as exc:
        logger.warning(
            "[_run_asset_report_pipeline] copy markdown failed run=%s err=%s",
            run_id,
            type(exc).__name__,
        )
        return None


async def _resolve_numina_mcp_servers(
    client: BackendClient,
    family_id: str,
    user_id: str | None,
    label: str,
) -> list[dict[str, Any]]:
    """Fetch enabled MCP servers and rewrite the Numina Backend MCP entry.

    Shared MCP-setup for every pipeline: locate the "Numina Backend MCP" server,
    point its URL at the family-scoped SSE endpoint (when not already prefixed),
    and attach the auth headers the backend MCP SSE handshake requires
    (``X-Caller-User-Id`` is mandatory; without it the SSE endpoint 403s). Only
    the Numina Backend MCP entry gets headers, not all servers. Returns ``[]``
    when the fetch fails so the caller degrades to zero MCP tools.
    ``label`` is the calling pipeline's log tag (e.g. ``[_run_numina_agent]``).
    """
    try:
        mcp_servers = await client.get_enabled_mcp_servers()
        for srv in mcp_servers:
            if srv.get("name") == "Numina Backend MCP":
                expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
                actual_url = (srv.get("url") or "").rstrip("/")
                if not actual_url.startswith(expected_prefix):
                    srv["url"] = (
                        expected_prefix + "/api/v1/internal/mcp/" + family_id + "/sse"
                    )
                mcp_headers: dict[str, str] = {
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                    "X-Family-Id": family_id,
                }
                if user_id:
                    mcp_headers["X-Caller-User-Id"] = user_id
                srv["headers"] = mcp_headers
                break
        return mcp_servers
    except Exception as exc:
        logger.warning(
            "%s get_enabled_mcp_servers failed family=%s err=%s",
            label,
            family_id,
            type(exc).__name__,
        )
        return []


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
      - ``asset-report``  → ``_run_asset_report_pipeline`` (U4 3-step pipeline).
      - ``import-parse``  → ``_run_import_parse_agent`` (U8 single-run parse).
      - ``finance-coach`` → ``_run_finance_coach_agent`` (Plan A single-run advice).
      - ``wish-advice``   → ``_run_wish_advice_agent`` (Plan B T7 single-run advice).
      - ``dashboard-narrative`` → ``_run_dashboard_narrative_agent`` (仪表盘叙事).

    The allowlist preventing unknown / asset-report / import-parse / finance-coach
    / wish-advice values from reaching here is enforced upstream in
    ``sse_gateway.start_run`` (R1 gate).
    """
    # Resolved-3 blocker A: set the family_id ContextVar before any sandbox
    # tool (write_file/read_file) can be invoked. Must run in all branches —
    # numina and import-parse also depend on it once native tools are enabled.
    set_family_sandbox_context(family_id, caller_user_id=user_id)

    # Resolved-3 blocker A reset (P0, ce-code-review 2026-07-19): the family_id
    # + extensions_config_path ContextVars are coroutine-scoped and would leak
    # into a subsequent run if this coroutine is reused (shared worker task /
    # executor thread). Mirror the active-skill reset pattern: set above, reset
    # in a finally that wraps all three dispatch branches + any exception path.
    try:
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
        if app == "finance-coach":
            await _run_finance_coach_agent(
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
        if app == "wish-advice":
            await _run_wish_advice_agent(
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
        if app == "dashboard-narrative":
            await _run_dashboard_narrative_agent(
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
        )
    finally:
        reset_family_sandbox_context()


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
    write_file_paths: list[str] = []
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
        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_asset_report_pipeline]"
        )

        # 4. Build adapter. plan_mode=False (fixed 3-step flow, no TodoList).
        # Read the agent's memory_enabled flag from the AgentRegistry (single
        # source of truth: ai_agents.memory_enabled). asset-report declares
        # memory_enabled=False on its system-agent row → DeerMem injection +
        # write are disabled, so each run is stateless and fetches fresh MCP
        # data (plan U4 Open Question: DeerMem pollution). agent_name is also
        # passed for DeerMem bucket isolation (per (agent_name, user_id)).
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get("asset-report", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="asset-report",
            memory_enabled=memory_enabled,
            # U4 step 3: middleware path (AssetReportStep2Middleware) was
            # attempted but get_stream_writer() is no-op on numina's sync
            # stream() path (plan fallback condition). report.step2_json is
            # worker-synthesized instead (see step 9 below).
        )

        # 5. Synthetic trigger message (plan L117): report runs are backend-
        # initiated with no natural user message. Use the slash-activation form
        # so the LLM loads asset-report/SKILL.md (not chat/SKILL.md). If the
        # backend already supplied a user message in graph_input, prefer it.
        # Localize the trigger based on user's language preference so the first
        # user input the LLM sees matches the target language.
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _SYNTHETIC_TRIGGERS_BY_LANG.get("asset-report", {}).get(
            user_language, _SYNTHETIC_ASSET_REPORT_TRIGGER
        )
        if graph_input and "messages" in graph_input:
            msgs = graph_input["messages"]
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") in ("user", "human"):
                    content = last.get("content", "")
                    if content:
                        user_message = content

        # 5b. Append language instruction based on user's language preference.
        # SKILL.md is static; the LLM needs an explicit per-run directive to
        # output in the user's chosen language (not always Chinese).
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{user_message}\n\n{lang_instruction}"

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
                            # U4 step 3 / R5: capture write_file's args.path so
                            # step 9 can locate the sandbox markdown for
                            # persistence (more reliable than the LLM's
                            # WRITE_FILE: text declaration, which e2e showed is
                            # often omitted from AI message content).
                            if raw_name == "write_file":
                                tc_args = tc.get("args") or {}
                                wf_path = tc_args.get("path")
                                if isinstance(wf_path, str) and wf_path:
                                    write_file_paths.append(wf_path)
                            tool_type, display_name, icon, display_key = (
                                resolve_tool_metadata(raw_name)
                            )
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
                        await bridge.publish(
                            run_id,
                            "custom",
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "content": content,
                            },
                        )

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Step 3 worker-synthesized report.step2_json emission + persistence.
        # The middleware path (AssetReportStep2Middleware via get_stream_writer)
        # was attempted but is no-op on numina's sync stream() path (plan step 3
        # fallback condition: "numina 租户隔离动态加载阻断"). Worker synthesis is
        # the plan-sanctioned fallback — emit exactly one report.step2_json
        # before the end frame (timing contract: strictly precedes end), then
        # persist. Best-effort persistence: a failure must not fail the run.
        if completion_status == "complete":
            ai_text = "".join(ai_response_parts)
            step2_payload = parse_report_json(ai_text)
            if step2_payload is not None:
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "report.step2_json",
                        "payload": step2_payload,
                    },
                )
                # R5 path 契约 + Finding 4: persist markdown_file_path by
                # copying the step-1 sandbox markdown into the tenant reports
                # dir (server-generated filename with run_id suffix — collision
                # defense). Best-effort: None when the LLM declared no filename
                # or the sandbox file is missing.
                markdown_file_path = _copy_asset_report_markdown(
                    family_id=family_id,
                    thread_id=thread_id,
                    run_id=run_id,
                    user_id=user_id,
                    ai_text=ai_text,
                    write_file_paths=write_file_paths,
                )
                try:
                    await client.persist_report_result(
                        report_json=step2_payload,
                        markdown_file_path=markdown_file_path,
                    )
                except Exception as persist_exc:
                    # P1 green-while-red fix (ce-code-review 2026-07-19): a
                    # persist failure must NOT leave the run looking complete —
                    # the step2_json custom event already shipped (step2=finish
                    # on the frontend), so downgrade the terminal status to
                    # "error" before the end frame so the UI reflects that
                    # ai_reports has no row. Run status is set too so retries /
                    # /runs polling see failure.
                    logger.warning(
                        "[_run_asset_report_pipeline] persist_report_result failed run=%s err=%s",
                        run_id,
                        type(persist_exc).__name__,
                    )
                    completion_status = "error"
                    error_type = type(persist_exc).__name__
                    success = False
                    await run_manager.set_status(
                        run_id, RunStatus.error, error=str(persist_exc)
                    )
                    await bridge.publish(
                        run_id,
                        "error",
                        {
                            "message": "结构化结果保存失败，可参考上方文本",
                            "name": error_type,
                        },
                    )

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning(
            "[_run_asset_report_pipeline] failed run=%s err=%s", run_id, error_type
        )
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
                skill_id="asset-report",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow
        # pattern). No suggestions/title (report is not a chat).
        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


# Synthetic trigger for asset-report runs (plan L117: backend-initiated runs
# have no natural user message; slash form steers skill loading to asset-report).
_SYNTHETIC_ASSET_REPORT_TRIGGER = "/asset-report 生成家庭资产报告"

# Synthetic trigger for import-parse runs (U8, same rationale as asset-report):
# backend /import/parse-pdf initiates the run with the extracted document text
# as the user message; the slash prefix steers skill loading to import-parse
# (not chat). If graph_input carries no user message, this triggers skill load.
_SYNTHETIC_IMPORT_PARSE_TRIGGER = "/import-parse 解析金融文档持仓"

# Synthetic trigger for finance-coach runs (Plan A T6, same rationale as
# asset-report / import-parse): the backend posts the family finance snapshot
# JSON as the run's user message (see Task 8 backend trigger); the slash prefix
# steers skill loading to finance-coach (not chat). If graph_input carries no
# user message, this triggers skill load.
_SYNTHETIC_FINANCE_COACH_TRIGGER = "/finance-coach 生成家庭财务建议"


# Synthetic trigger for wish-advice runs (Plan B T7, same rationale as
# finance-coach): the backend posts the wishes snapshot JSON as the run's user
# message; the slash prefix steers skill loading to wish-advice (not chat). If
# graph_input carries no user message, this triggers skill load.
_SYNTHETIC_WISH_ADVICE_TRIGGER = "/wish-advice 生成心愿储蓄建议"


# Per-user-language instructions for the synthetic trigger message.
# SKILL.md is static; the LLM needs an explicit per-run directive to output
# in the user's chosen language. The trigger message itself is also localized
# so the first user input the LLM sees matches the target language.
_LANGUAGE_INSTRUCTIONS = {
    "en-US": "[LANGUAGE REQUIREMENT] Output language: English. All user-visible text fields (label, narrative, suggestions, summary) MUST be in English. Only 'key' fields use snake_case.",
    "zh-CN": "[语言要求] 输出语言：中文。所有用户可见文本字段（label、narrative、suggestions、summary）必须使用中文。仅 key 字段使用 snake_case。",
    "default": "[语言要求] 输出语言：中文。所有用户可见文本字段（label、narrative、suggestions、summary）必须使用中文。仅 key 字段使用 snake_case。",
}

# Localized synthetic triggers — the slash prefix loads the skill, the rest
# sets the language tone for the LLM.
_SYNTHETIC_TRIGGERS_BY_LANG = {
    "asset-report": {
        "en-US": "/asset-report Generate family asset report",
        "zh-CN": "/asset-report 生成家庭资产报告",
        "default": "/asset-report 生成家庭资产报告",
    },
}


def _extract_import_parse_document(graph_input: dict | None) -> str | None:
    """Pull the document text the backend injected as the run's user message.

    backend ``/import/parse-pdf`` extracts PDF text and posts it as the
    ``messages[-1]`` content of the stream_run input. Returns None when no
    user message is present (caller falls back to the synthetic trigger).
    """
    if not graph_input or not isinstance(graph_input, dict):
        return None
    msgs = graph_input.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, dict) and last.get("role") in ("user", "human"):
        content = last.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
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
    """Import-parse (3rd stream_run agent) dispatch branch (U8).

    Runs a single ``stream_run`` agent run via ``adapter.typed_stream_dispatch``
    with ``skill_name="import-parse"``. The skill prompt (see
    ``skills/builtin/public/import-parse/SKILL.md``) drives the LLM to parse the
    injected document text and emit a single ```json block with
    ``{source, report_date, items}``. The worker forwards frames, synthesizes
    tool_call/tool_result custom events (chat renderer reuse), and emits exactly
    one ``import-parse.result`` custom event with the parsed payload before the
    ``end`` frame (mirrors asset-report's worker-synthesized step-3 emission).

    Differences vs asset-report:
    - ``skill_name="import-parse"`` (fixed system flow, KTD-8).
    - No markdown audit step (import-parse outputs JSON directly; no write_file
      persistence). MCP batch-write tools (``import_*_batch``) + multimodal vision
      are U8 follow-ups (plan 前提链 dependent #2: slip does not block dispatch
      deletion) — this branch parses only.
    - Document text is injected by backend as the run's user message (not a
      synthetic trigger); the slash trigger is only the skill-load fallback.
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
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

        # 2. Fetch per-family AI config (tenant-isolated) — mirrors asset-report.
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers (same MCP-setup as asset-report).
        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_import_parse_agent]"
        )

        # 4. Build adapter. plan_mode=False (fixed parse flow, no TodoList).
        # import-parse is stateless (memory_enabled=False) — each run parses the
        # injected document fresh, no DeerMem pollution.
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get("import-parse", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=120,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="import-parse",
            memory_enabled=memory_enabled,
        )

        # 5. User message = backend-injected document text (preferred) or the
        # synthetic slash trigger (skill-load fallback).
        user_message = (
            _extract_import_parse_document(graph_input)
            or _SYNTHETIC_IMPORT_PARSE_TRIGGER
        )

        # 6. PII redaction (Key Invariant #1)
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge. Set the
        # active skill so sync_tool_patch filters tools to import-parse's
        # declared allowed-tools whitelist.
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        _skill_token = set_active_skill("import-parse")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="import-parse",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=False,  # Qwen3: avoid empty content
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

            # Mirror asset-report: collect AI text + synthesize tool_call/
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
                            tool_type, display_name, icon, display_key = (
                                resolve_tool_metadata(raw_name)
                            )
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
                        await bridge.publish(
                            run_id,
                            "custom",
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "content": content,
                            },
                        )

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Worker-synthesized import-parse.result emission (mirrors asset-report
        # step-3 worker synthesis — middleware get_stream_writer() path is no-op
        # on numina's sync stream() path). Emit exactly one import-parse.result
        # before the end frame (timing contract: strictly precedes end).
        if completion_status == "complete":
            ai_text = "".join(ai_response_parts)
            parsed = parse_report_json(ai_text)
            if parsed is not None:
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "import-parse.result",
                        "payload": parsed,
                    },
                )

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning(
            "[_run_import_parse_agent] failed run=%s err=%s", run_id, error_type
        )
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
                skill_id="import-parse",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow
        # pattern). No suggestions/title (parse is not a chat).
        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


async def _run_finance_coach_agent(
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
    """finance-coach (4th stream_run agent) dispatch branch (Plan A).

    Runs a single ``stream_run`` agent run via ``adapter.typed_stream_dispatch``
    with ``skill_name="finance-coach"``. The skill prompt (see
    ``skills/builtin/public/finance-coach/SKILL.md``) drives the LLM to read the
    family finance snapshot (injected by the backend as the run's user message)
    and emit a single ```json block with ``{suggestions: [...]}``. The worker
    forwards frames, synthesizes tool_call/tool_result custom events (chat
    renderer reuse), and emits exactly one ``finance_coach.result`` custom event
    with the parsed payload before the ``end`` frame (mirrors import-parse's
    worker-synthesized emission).

    Differences vs import-parse:
    - ``skill_name="finance-coach"`` (fixed system flow, KTD-8).
    - The user message is the backend-injected family finance snapshot JSON
      (preferred) or the synthetic slash trigger (skill-load fallback).
    - PII minimization (spec §7.1): the backend builds the snapshot with
      ``id + category`` (not ``name``); pii_redactor still runs on the message
      as defense-in-depth.
    - finance-coach is stateless (``memory_enabled=False``) — each run builds a
      fresh snapshot, no DeerMem pollution.
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
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

        # 2. Fetch per-family AI config (tenant-isolated) — mirrors import-parse.
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers (same MCP-setup as import-parse).
        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_finance_coach_agent]"
        )

        # 4. Build adapter. plan_mode=False (fixed advice flow, no TodoList).
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get("finance-coach", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=120,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="finance-coach",
            memory_enabled=memory_enabled,
        )

        # 5. User message = backend-injected snapshot (preferred) or synthetic
        # slash trigger (skill-load fallback). The snapshot is JSON the backend
        # posts as the run's user message content (see Task 8 backend trigger).
        user_message = (
            _extract_finance_coach_snapshot(graph_input)
            or _SYNTHETIC_FINANCE_COACH_TRIGGER
        )

        # 6. PII redaction (Key Invariant #1) — defense-in-depth; backend already
        # minimized PII (id+category, no name) per spec §7.1.
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge. Set the active
        # skill so sync_tool_patch filters tools to finance-coach's allowed-tools.
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        _skill_token = set_active_skill("finance-coach")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="finance-coach",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=False,  # single-run advice, keep latency bounded
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

            # Mirror import-parse: collect AI text + synthesize tool_call/
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
                            tool_type, display_name, icon, display_key = (
                                resolve_tool_metadata(raw_name)
                            )
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
                        await bridge.publish(
                            run_id,
                            "custom",
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "content": content,
                            },
                        )

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Worker-synthesized finance_coach.result emission (mirrors import-parse
        # worker synthesis). Emit exactly one finance_coach.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        if completion_status == "complete":
            ai_text = "".join(ai_response_parts)
            parsed = parse_report_json(ai_text)
            if parsed is not None:
                # Advice baseline (spec §7.1): the worker emits the raw parsed
                # suggestions. Schema-validation gate (suggested_amount >= 0,
                # required fields) runs in Plan B's D2/W4 UI before any enable;
                # a malformed payload is dropped there, not here (the worker is
                # transport, not policy).
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "finance_coach.result",
                        "payload": parsed,
                    },
                )

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning(
            "[_run_finance_coach_agent] failed run=%s err=%s", run_id, error_type
        )
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
                skill_id="finance-coach",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow pattern).
        # Annotated ``dict[str, Any]`` so assigning the ``usage`` dict (typed
        # ``dict[str, int]``) is type-compatible — the import-parse / asset-report
        # / numina siblings leave this unannotated and incur the same mypy error;
        # annotating only here keeps this task's additions mypy-clean without
        # touching the pre-existing sibling sites (surgical scope).
        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


def _extract_finance_coach_snapshot(graph_input: dict | None) -> str | None:
    """Pull the family finance snapshot JSON the backend injected as the run's
    user message (mirrors ``_extract_import_parse_document``).

    The backend (Task 8) posts the snapshot as ``messages[-1]`` content of the
    stream_run input. Returns None when no user message is present (caller falls
    back to the synthetic trigger).
    """
    if not graph_input or not isinstance(graph_input, dict):
        return None
    msgs = graph_input.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, dict) and last.get("role") in ("user", "human"):
        content = last.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
    return None


def _extract_wish_advice_input(graph_input: dict | None) -> str | None:
    """Pull the wishes snapshot JSON the backend injected as the run's user
    message (mirrors ``_extract_finance_coach_snapshot``).

    The backend (Plan B T7) posts the wishes snapshot as ``messages[-1]``
    content of the stream_run input. Returns None when no user message is
    present (caller falls back to the synthetic trigger).
    """
    if not graph_input or not isinstance(graph_input, dict):
        return None
    msgs = graph_input.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, dict) and last.get("role") in ("user", "human"):
        content = last.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
    return None


async def _run_wish_advice_agent(
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
    """wish-advice (5th stream_run agent) dispatch branch (Plan B T7).

    Mirrors ``_run_finance_coach_agent`` but with ``skill_name="wish-advice"``
    and a ``wish_advice.result`` emission whose payload is ``{redistribution[]}``
    (NOT finance_coach's ``{suggestions[]}`` — spec §7.1 schema-mutually-exclusive).
    The skill prompt (see ``skills/builtin/public/wish-advice/SKILL.md``) drives
    the LLM to read the wishes snapshot (injected by the backend as the run's
    user message) and emit a single ```json block with the redistribution.

    Differences vs finance-coach:
    - ``skill_name="wish-advice"`` (fixed system flow, Plan B T7).
    - Output schema = ``{primary_wish_id, reason, suggested_monthly,
      redistribution[]}`` (W4 advice contract).
    - wish name IS prompt-required here (the user names wishes and the AI reasons
      about them by name — unlike finance_coach's id+category PII minimization).
    - stateless (``memory_enabled=False``) — fresh snapshot each run.
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
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

        # 2. Fetch per-family AI config (tenant-isolated) — mirrors finance-coach.
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. Fetch enabled MCP servers (same MCP-setup as finance-coach).
        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_wish_advice_agent]"
        )

        # 4. Build adapter. plan_mode=False (fixed advice flow, no TodoList).
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get("wish-advice", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=120,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="wish-advice",
            memory_enabled=memory_enabled,
        )

        # 5. User message = backend-injected wishes snapshot (preferred) or
        # synthetic slash trigger (skill-load fallback).
        user_message = (
            _extract_wish_advice_input(graph_input) or _SYNTHETIC_WISH_ADVICE_TRIGGER
        )

        # 6. PII redaction (Key Invariant #1) — defense-in-depth; the backend
        # already minimized PII per spec §7.1 (wish name is prompt-required for
        # the AI to reason about which wish to prioritize, but amounts/ids only).
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch → publish to bridge. Set the active
        # skill so sync_tool_patch filters tools to wish-advice's allowed-tools.
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        _skill_token = set_active_skill("wish-advice")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="wish-advice",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=False,  # single-run advice, keep latency bounded
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

            # Mirror finance-coach: collect AI text + synthesize tool_call/
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
                            tool_type, display_name, icon, display_key = (
                                resolve_tool_metadata(raw_name)
                            )
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
                        await bridge.publish(
                            run_id,
                            "custom",
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "content": content,
                            },
                        )

        # 8. Terminal status.
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Worker-synthesized wish_advice.result emission (mirrors finance-coach
        # worker synthesis). Emit exactly one wish_advice.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        if completion_status == "complete":
            ai_text = "".join(ai_response_parts)
            parsed = parse_report_json(ai_text)
            if parsed is not None:
                # Advice baseline (spec §7.1): the worker emits the raw parsed
                # advice. Schema-validation gate (suggested_amount >= 0, required
                # fields) runs in Plan B's W4 UI (WishAdviceCard.validateAdvice)
                # + backend validate_advice before any enable; a malformed payload
                # is dropped there, not here (the worker is transport, not policy).
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "wish_advice.result",
                        "payload": parsed,
                    },
                )

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning(
            "[_run_wish_advice_agent] failed run=%s err=%s", run_id, error_type
        )
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
                skill_id="wish-advice",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        # 11. Terminal end frame + sentinel + deferred cleanup (DeerFlow pattern).
        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


# ---------------------------------------------------------------------------
# U4 goal continuation helpers (D1 — DeerFlow runtime/runs/worker.py:715-1047 parity)
#
# These mirror DeerFlow's worker goal-continuation helpers but live here because
# DeerFlow's versions are private to its ``runtime/runs/worker.py`` module and
# reference DeerFlow-only objects (``StreamBridge.publish`` of serialized
# ``values``, DeerFlow ``AppConfig``). Numina's worker drives the same logic
# against its own ``StreamBridge`` and the family AI config dict.
#
# R1 isolation: the entire continuation loop is cleanly separable — removing
# ``_prepare_goal_continuation_input`` + the ``while`` block in
# ``_run_numina_agent`` leaves goal set/clear/status (U2) + GoalStatusBar (U5)
# fully functional, just without auto-continuation.
# ---------------------------------------------------------------------------


def _get_shared_checkpointer_for_goal() -> Any:
    """Return the shared LangGraph checkpointer used for goal channel reads/writes.

    Thin indirection so tests can patch ``worker._get_shared_checkpointer_for_goal``
    without touching the family-adapter cache module.
    """
    from apps.agent.services.deerflow_adapter.family_adapter_cache import (
        _get_shared_checkpointer,
    )

    return _get_shared_checkpointer(None)


def _goal_checkpoint_id(checkpoint_tuple: Any) -> str | None:
    config = getattr(checkpoint_tuple, "config", {}) or {}
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    checkpoint_id = (
        configurable.get("checkpoint_id") if isinstance(configurable, dict) else None
    )
    if isinstance(checkpoint_id, str):
        return checkpoint_id
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    if isinstance(checkpoint, dict):
        checkpoint_id_value = checkpoint.get("id")
        if isinstance(checkpoint_id_value, str):
            return checkpoint_id_value
    return None


def _read_checkpoint_messages(checkpoint_tuple: Any) -> list[Any]:
    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = (
        checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}
    )
    messages = (
        channel_values.get("messages", []) if isinstance(channel_values, dict) else []
    )
    return messages if isinstance(messages, list) else []


def _read_checkpoint_goal(checkpoint_tuple: Any) -> dict[str, Any] | None:
    import copy

    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = (
        checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}
    )
    raw_goal = channel_values.get("goal") if isinstance(channel_values, dict) else None
    return copy.deepcopy(raw_goal) if isinstance(raw_goal, dict) else None


def _goal_instance_matches(
    left: dict[str, Any] | None, right: dict[str, Any] | None
) -> bool:
    if not left or not right:
        return False
    same_status = left.get("status") == right.get("status") == "active"
    same_objective = left.get("objective") == right.get("objective")
    same_created_at = left.get("created_at") == right.get("created_at")
    return bool(same_status and same_objective and same_created_at)


def _has_durable_goal_turn_receipt(checkpoint_tuple: Any, messages: list[Any]) -> bool:
    """Return true when a completed visible assistant turn is safely checkpointed."""
    if _goal_checkpoint_id(checkpoint_tuple) is None:
        return False
    if getattr(checkpoint_tuple, "pending_writes", None):
        return False
    from deerflow.runtime.goal import has_visible_assistant_evidence

    if not has_visible_assistant_evidence(messages):
        return False
    # Last visible message must be an AI reply (turn completed).
    last_type: str | None = None
    for message in messages:
        mt = _goal_message_type(message)
        if mt in {"human", "ai"} and _goal_message_text(message).strip():
            last_type = mt
    return last_type == "ai"


def _goal_message_type(message: Any) -> str | None:
    value = getattr(message, "type", None)
    if value is None and isinstance(message, dict):
        value = message.get("type") or message.get("role")
    if value == "assistant":
        return "ai"
    if value == "user":
        return "human"
    return str(value) if value else None


def _goal_message_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if content is None and isinstance(message, dict):
        content = message.get("content")
    if isinstance(content, list):
        parts = [
            item["text"]
            if isinstance(item, dict) and isinstance(item.get("text"), str)
            else item
            for item in content
        ]
        content = "".join(str(p) for p in parts)
    if not isinstance(content, str):
        content = str(content) if content is not None else ""
    return content.strip()


def _stand_down_reason(
    goal: dict[str, Any], evaluation: dict[str, Any], no_progress_count: int
) -> str | None:
    """Mirror DeerFlow goal.py:774-785 stand-down reasons."""
    if evaluation["satisfied"]:
        return None
    if evaluation["blocker"] != "goal_not_met_yet":
        return f"blocked:{evaluation['blocker']}"
    if int(goal.get("continuation_count", 0)) >= int(goal.get("max_continuations", 8)):
        return "max_continuations_reached"
    if no_progress_count >= int(goal.get("max_no_progress_continuations", 2)):
        return "no_progress_detected"
    return None


async def _reread_goal_and_checkpoint(
    checkpointer: Any, thread_id: str
) -> tuple[dict[str, Any] | None, Any]:
    goal = await read_thread_goal(checkpointer, thread_id)
    aget_tuple = getattr(checkpointer, "aget_tuple", None) or getattr(
        checkpointer, "get_tuple", None
    )
    if aget_tuple is None:
        return goal, None
    result = aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    import inspect

    if inspect.isawaitable(result):
        result = await result
    return goal, result


async def _prepare_goal_continuation_input(
    *,
    checkpointer: Any,
    thread_id: str,
    run_id: str,
    family_ai_config: dict[str, Any],
    family_id: str,
    user_id: str | None,
    abort_event: asyncio.Event,
) -> dict[str, Any] | None:
    """Evaluate the active goal and return a hidden continuation input if needed.

    Aligned with DeerFlow ``runtime/runs/worker.py:858-1047``. Returns a dict
    with the continuation ``context`` (a ``RedactedContext`` whose ``free_text``
    carries the hidden goal-continuation message) plus the bumped
    ``continuation_count``, or ``None`` when the loop should stop (satisfied,
    blocked, capped, raced, aborted, or evaluator error).

    P0 fix: ``missing_evidence`` and any non-``goal_not_met_yet`` blocker stand
    down (``should_continue_goal`` returns False) — DeerFlow stops on these, it
    does NOT continue on them.

    Lock scope (P3): the lock is held only across the read-modify-write
    segment (``goal_thread_lock``), never across the evaluator LLM call — so a
    racing ``DELETE /goal`` (which acquires the same lock) cannot deadlock
    against a long continuation evaluation.
    """
    if checkpointer is None:
        return None
    if abort_event.is_set():
        return None

    try:
        goal = await read_thread_goal(checkpointer, thread_id)
    except Exception:
        logger.warning(
            "Could not read goal for thread %s after run %s",
            thread_id,
            run_id,
            exc_info=True,
        )
        return None
    if not goal or goal.get("status") != "active":
        return None

    # Read the checkpoint for messages + a pre-evaluation signature.
    aget_tuple = getattr(checkpointer, "aget_tuple", None) or getattr(
        checkpointer, "get_tuple", None
    )
    if aget_tuple is None:
        return None
    try:
        import inspect

        checkpoint_tuple = aget_tuple(
            {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        )
        if inspect.isawaitable(checkpoint_tuple):
            checkpoint_tuple = await checkpoint_tuple
    except Exception:
        logger.warning(
            "Could not read checkpoint for goal eval thread %s",
            thread_id,
            exc_info=True,
        )
        return None
    if checkpoint_tuple is None:
        return None

    checkpoint_id_before = _goal_checkpoint_id(checkpoint_tuple)
    messages = _read_checkpoint_messages(checkpoint_tuple)
    conversation_signature_before = visible_conversation_signature(messages)
    evidence_signature = latest_visible_assistant_signature(messages)

    if not _has_durable_goal_turn_receipt(checkpoint_tuple, messages):
        evaluation = {
            "satisfied": False,
            "blocker": "run_failed",
            "reason": "No durable assistant end-of-turn receipt was available.",
            "evidence_summary": "",
        }
        no_progress_count = compute_no_progress_count(
            goal, evaluation, evidence_signature=evidence_signature
        )
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="no_durable_end_of_turn",
            evidence_signature=evidence_signature,
            family_ai_config=family_ai_config,
        )
        return None

    if abort_event.is_set():
        return None

    # Evaluate via the non-thinking LLM. On failure stand down (no infinite loop).
    try:
        evaluation = await evaluate_goal_completion(
            goal,
            messages,
            family_ai_config=family_ai_config,
            thread_id=thread_id,
            user_id=user_id,
        )
    except GoalEvaluationError as exc:
        logger.warning(
            "Goal evaluator failed for thread %s after run %s: %s",
            thread_id,
            run_id,
            exc,
        )
        evaluation = {
            "satisfied": False,
            "blocker": "evaluator_error",
            "reason": str(exc),
            "evidence_summary": "",
        }
        no_progress_count = compute_no_progress_count(
            goal, evaluation, evidence_signature=evidence_signature
        )
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="blocked:evaluator_error",
            evidence_signature=evidence_signature,
            family_ai_config=family_ai_config,
        )
        return None

    if abort_event.is_set():
        return None

    no_progress_count = compute_no_progress_count(
        goal, evaluation, evidence_signature=evidence_signature
    )

    # Re-check that neither the goal nor the visible conversation changed while
    # the evaluator ran — a user message or /goal clear racing the evaluation wins.
    try:
        current_goal, current_checkpoint_tuple = await _reread_goal_and_checkpoint(
            checkpointer, thread_id
        )
    except Exception:
        logger.warning(
            "Could not re-check goal state for thread %s after evaluation",
            thread_id,
            exc_info=True,
        )
        return None
    if (
        not _goal_instance_matches(goal, current_goal)
        or current_checkpoint_tuple is None
    ):
        return None
    checkpoint_changed = (
        _goal_checkpoint_id(current_checkpoint_tuple) != checkpoint_id_before
    )
    messages_changed = (
        visible_conversation_signature(
            _read_checkpoint_messages(current_checkpoint_tuple)
        )
        != conversation_signature_before
    )
    if checkpoint_changed or messages_changed:
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="thread_changed_after_evaluation",
            evidence_signature=evidence_signature,
            family_ai_config=family_ai_config,
        )
        return None

    # Satisfied → clear the goal (inside the lock, with conflict detection).
    if evaluation["satisfied"]:
        try:
            async with goal_thread_lock(thread_id):
                latest_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
                if latest_tuple is None:
                    return None
                latest_goal = _read_checkpoint_goal(latest_tuple)
                if latest_goal is None or not _goal_instance_matches(goal, latest_goal):
                    return None
                await write_thread_goal(
                    checkpointer,
                    thread_id,
                    None,
                    as_node="goal_evaluator",
                    expected_checkpoint_id=_goal_checkpoint_id(latest_tuple),
                )
        except GoalWriteConflict:
            return None
        except Exception:
            logger.warning(
                "Could not clear satisfied goal for thread %s", thread_id, exc_info=True
            )
        return None

    stand_down_reason = _stand_down_reason(goal, evaluation, no_progress_count)
    if stand_down_reason is not None or not should_continue_goal(
        goal, evaluation, no_progress_count=no_progress_count
    ):
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason=stand_down_reason,
            evidence_signature=evidence_signature,
            family_ai_config=family_ai_config,
        )
        return None

    # Bump continuation_count (inside the lock, defensive max against a racing bump).
    next_count = int(goal.get("continuation_count", 0)) + 1
    updated_goal = await _persist_goal_evaluation(
        checkpointer=checkpointer,
        thread_id=thread_id,
        run_id=run_id,
        goal=goal,
        evaluation=evaluation,
        no_progress_count=no_progress_count,
        continuation_count=next_count,
        evidence_signature=evidence_signature,
        family_ai_config=family_ai_config,
    )
    if updated_goal is None:
        return None

    # Final guard: verify the visible conversation did not change before queuing.
    try:
        latest_goal, latest_checkpoint_tuple = await _reread_goal_and_checkpoint(
            checkpointer, thread_id
        )
    except Exception:
        logger.warning(
            "Could not verify queued goal continuation for thread %s",
            thread_id,
            exc_info=True,
        )
        return None
    if (
        not _goal_instance_matches(updated_goal, latest_goal)
        or latest_checkpoint_tuple is None
    ):
        return None
    if (
        visible_conversation_signature(
            _read_checkpoint_messages(latest_checkpoint_tuple)
        )
        != conversation_signature_before
    ):
        assert latest_goal is not None  # _goal_instance_matches guarantees non-None
        await _persist_goal_evaluation(
            checkpointer=checkpointer,
            thread_id=thread_id,
            run_id=run_id,
            goal=latest_goal,
            evaluation=evaluation,
            no_progress_count=no_progress_count,
            stand_down_reason="thread_changed_before_continuation",
            evidence_signature=evidence_signature,
            family_ai_config=family_ai_config,
        )
        return None

    logger.info(
        "Run %s continuing thread %s for active goal (%d/%d)",
        run_id,
        thread_id,
        updated_goal.get("continuation_count", next_count),
        updated_goal.get("max_continuations", 0),
    )
    # Build the hidden continuation message and wrap it in a RedactedContext so
    # the adapter streams it as the next turn's user input. The frontend hides
    # human messages during active streaming (useThreadChat `!isInitialLoad`
    # filter), so this continuation is not shown as a duplicate user bubble.
    continuation_message = make_goal_continuation_message(updated_goal, evaluation)
    continuation_context = pii_redactor.redact(
        FamilyContext(family_id=family_id, free_text=continuation_message.content)
    )
    return {
        "context": continuation_context,
        "continuation_count": updated_goal.get("continuation_count", next_count),
    }


async def _reread_checkpoint_tuple(checkpointer: Any, thread_id: str) -> Any:
    aget_tuple = getattr(checkpointer, "aget_tuple", None) or getattr(
        checkpointer, "get_tuple", None
    )
    if aget_tuple is None:
        return None
    import inspect

    result = aget_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    if inspect.isawaitable(result):
        result = await result
    return result


async def _persist_goal_evaluation(
    *,
    checkpointer: Any,
    thread_id: str,
    run_id: str,
    goal: dict[str, Any],
    evaluation: dict[str, Any],
    no_progress_count: int,
    continuation_count: int | None = None,
    stand_down_reason: str | None = None,
    evidence_signature: str = "",
    family_ai_config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Persist the evaluation against the still-current goal instance.

    Lock scope (P3): the ``goal_thread_lock`` is held only across the
    read-modify-write (read fresh checkpoint → attach evaluation → write), never
    across LLM calls — so a racing ``DELETE /goal`` cannot deadlock.
    """
    try:
        async with goal_thread_lock(thread_id):
            checkpoint_tuple = await _reread_checkpoint_tuple(checkpointer, thread_id)
            if checkpoint_tuple is None:
                return None
            current_goal = _read_checkpoint_goal(checkpoint_tuple)
            if current_goal is None or not _goal_instance_matches(goal, current_goal):
                return None
            # Defensive: compute continuation_count from the fresh current_goal
            # inside the lock — a racing continuation may have already bumped it.
            effective_count = continuation_count
            if effective_count is not None:
                current_count = int(current_goal.get("continuation_count", 0))
                effective_count = max(effective_count, current_count + 1)
            expected_checkpoint_id = _goal_checkpoint_id(checkpoint_tuple)
            updated_goal = cast(
                dict[str, Any],
                attach_goal_evaluation(
                    current_goal,
                    evaluation,
                    run_id=run_id,
                    continuation_count=effective_count,
                    no_progress_count=no_progress_count,
                    stand_down_reason=stand_down_reason,
                    evidence_signature=evidence_signature,
                ),
            )
            await write_thread_goal(
                checkpointer,
                thread_id,
                updated_goal,
                as_node="goal_evaluator",
                expected_checkpoint_id=expected_checkpoint_id,
            )
        return updated_goal
    except GoalWriteConflict:
        return None
    except Exception:
        logger.warning(
            "Could not persist goal evaluation for thread %s", thread_id, exc_info=True
        )
        return None


# Synthetic trigger for dashboard-narrative runs (mirrors _SYNTHETIC_FINANCE_COACH_TRIGGER).
_SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER = "/dashboard-narrative 生成本月财务叙事"


def _extract_dashboard_narrative_context(graph_input: dict | None) -> str | None:
    """Pull the financial context JSON the backend injected as the run's user
    message (mirrors ``_extract_finance_coach_snapshot``).
    """
    if not graph_input or not isinstance(graph_input, dict):
        return None
    msgs = graph_input.get("messages")
    if not isinstance(msgs, list) or not msgs:
        return None
    last = msgs[-1]
    if isinstance(last, dict) and last.get("role") in ("user", "human"):
        content = last.get("content", "")
        if isinstance(content, str) and content.strip():
            return content
    return None


async def _run_dashboard_narrative_agent(
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
    """dashboard-narrative (6th stream_run agent) dispatch branch.

    Runs a single ``stream_run`` agent run with ``skill_name="dashboard-narrative"``.
    The skill prompt drives the LLM to generate 2-3 sentences of financial narrative
    from the backend-injected context. Emits one ``dashboard_narrative.result`` custom
    event with the plain-text narrative before the ``end`` frame.

    Simpler than finance-coach: no MCP tools (allowed-tools: []), no JSON parsing —
    the LLM output IS the narrative text (after stripping code fences if any).
    """
    run_id = record.run_id
    t_start = time.monotonic()
    success = False
    error_type: str | None = None
    completion_status = "error"
    ai_response_parts: list[str] = []
    thinking_parts: list[str] = []
    cumulative_usage: dict[str, int] | None = None

    try:
        # 1. Mark running + publish metadata
        await run_manager.set_status(run_id, RunStatus.running)
        await bridge.publish(
            run_id, "metadata", {"run_id": run_id, "thread_id": thread_id}
        )

        # 2. Fetch per-family AI config
        client = BackendClient(family_id=family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        selected_provider = next(
            (p for p in providers if p.get("is_active")), providers[0]
        )

        # 3. No MCP servers needed (allowed-tools: [] — pure inference)
        mcp_servers: list[dict] = []

        # 4. Build adapter
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get("dashboard-narrative", family_id)
        memory_enabled = (
            bool(agent_meta.get("memory_enabled", True)) if agent_meta else True
        )

        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=60,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
            agent_name="dashboard-narrative",
            memory_enabled=memory_enabled,
        )

        # 5. User message = backend-injected context or synthetic trigger fallback
        user_message = (
            _extract_dashboard_narrative_context(graph_input)
            or _SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER
        )

        # 6. PII redaction (defense-in-depth)
        context = FamilyContext(family_id=family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # 7. Stream via typed_stream_dispatch (enable_thinking=True for real reasoning)
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        _skill_token = set_active_skill("dashboard-narrative")
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name="dashboard-narrative",
            context=redacted,
            thread_id=thread_id,
            enable_thinking=True,
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

            # Extract reasoning from AI messages and emit as reasoning_delta
            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    additional_kwargs = data.get("additional_kwargs") or {}
                    reasoning = additional_kwargs.get("reasoning_content")
                    if isinstance(reasoning, str) and reasoning:
                        thinking_parts.append(reasoning)
                        await bridge.publish(
                            run_id,
                            "custom",
                            {"type": "reasoning_delta", "content": reasoning},
                        )
                    # Forward message without reasoning_content to avoid duplication
                    content = data.get("content")
                    if content:
                        await bridge.publish(
                            run_id,
                            "messages",
                            {"type": "ai", "content": content},
                        )
                    continue

            # Forward other canonical frames (values, etc.)
            await bridge.publish(run_id, sse_type, data)

        # 8. Terminal status
        if record.abort_event.is_set():
            await run_manager.set_status(run_id, RunStatus.interrupted)
            completion_status = "interrupted"
        else:
            await run_manager.set_status(run_id, RunStatus.success)
            completion_status = "complete"
            success = record.status == RunStatus.success

        # 9. Emit dashboard_narrative.result custom event (with thinking)
        if completion_status == "complete":
            narrative_text = "".join(ai_response_parts).strip()
            thinking_text = "".join(thinking_parts).strip()

            if narrative_text:
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "dashboard_narrative.result",
                        "payload": {
                            "narrative": narrative_text,
                            "thinking": thinking_text,
                        },
                    },
                )

    except asyncio.CancelledError:
        error_type = "Cancelled"
        await run_manager.set_status(run_id, RunStatus.interrupted)
        raise
    except Exception as exc:
        error_type = type(exc).__name__
        logger.warning(
            "[_run_dashboard_narrative_agent] failed run=%s err=%s",
            run_id,
            error_type,
        )
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id, "error", {"message": str(exc), "name": error_type}
        )

    finally:
        if "_skill_token" in locals():
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )

            reset_active_skill(_skill_token)

        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                skill_id="dashboard-narrative",
                success=success,
                error_type=error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - t_start) * 1000),
            )
        )

        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


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
        mcp_servers = await _resolve_numina_mcp_servers(
            client, family_id, user_id, "[_run_numina_agent]"
        )

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
        configurable = (
            config.get("configurable", {}) if isinstance(config, dict) else {}
        )
        call_subagent_enabled = bool(configurable.get("subagent_enabled", False))
        call_plan_mode = bool(configurable.get("is_plan_mode", False))
        call_thinking_enabled = bool(configurable.get("thinking_enabled", True))
        call_websearch_enabled = bool(configurable.get("websearch_enabled", False))

        # U3: Fetch enabled custom skills for slash activation whitelist.
        # The worker fetches the family's enabled custom skills and passes them
        # to create_family_adapter so DeerFlow's SkillActivationMiddleware enforces
        # the whitelist. Q1 resolution: custom-skills-only (builtin excluded).
        enabled_skills = await client.get_enabled_skills()
        available_skills = {
            s["skill_id"] for s in enabled_skills if s.get("skill_type") == "custom"
        }

        # 4. Build adapter (uses per-family LRU cache from family_adapter_cache.py)
        # U7 (D5 TodoList): plan_mode=True makes DeerFlow's build_middlewares
        # inject its own TodoMiddleware (write_todos tool + context-loss /
        # premature-exit hooks) — see deerflow/agents/lead_agent/agent.py. No
        # custom middleware is injected here: a second TodoMiddleware (the former
        # numina copy) collided with DeerFlow's on LangChain's name-based dedup
        # (``Please remove duplicate middleware instances``) and double-fired the
        # after_model reminder. plan_mode is part of the LRU cache key
        # (family_adapter_cache.py cache_key), so plan_mode=True / False get
        # distinct DeerFlowClient instances.
        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=call_subagent_enabled,
            plan_mode=call_plan_mode,
            mcp_servers=mcp_servers,
            middlewares=None,
            available_skills=available_skills,  # U3: slash activation whitelist
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
            ai_config.get("web_search_providers")
            or ai_config.get("web_search_mcp_servers")
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
        skill_id = (
            "chat-search"
            if (call_websearch_enabled and has_search_capability)
            else "chat"
        )
        # Set the active skill so sync_tool_patch can filter tools to this skill's
        # declared allowed-tools whitelist (see active_skill_context module docstring).
        #
        # U2: For slash-activated skills (e.g. `/my-budget task`), skip set_active_skill
        # so DeerFlow's SkillToolPolicyMiddleware owns tool filtering instead of numina's
        # _apply_active_skill_tool_filter. The adapter sets ORIGINAL_USER_CONTENT_KEY
        # (U1), so DeerFlow's SkillActivationMiddleware can parse the slash.
        from deerflow.skills.slash import parse_slash_skill_reference

        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        _is_slash_message = parse_slash_skill_reference(user_message) is not None
        # Slash-activated skill: skip set_active_skill, let DeerFlow handle it
        # Non-slash message: use existing chat/chat-search pre-selection
        _skill_token = None if _is_slash_message else set_active_skill(skill_id)

        async def _stream_once(
            stream_context: Any, *, is_continuation: bool = False
        ) -> None:
            """Run one DeerFlow stream turn and forward events to the bridge.

            Extracted from the inline loop so the U4 goal continuation loop can
            re-invoke it with a hidden continuation ``RedactedContext``. When
            ``is_continuation`` is True the turn is a hidden goal-continuation
            turn (logged, not user-visible as a new prompt).
            """
            # ``cumulative_usage`` is reassigned
            # here but declared in the enclosing ``_run_numina_agent`` scope —
            # declare them nonlocal so the assignments propagate (and so the
            # continuation loop sees an interrupt flagged during a turn).
            nonlocal cumulative_usage
            async for sse_type, data in adapter.typed_stream_dispatch(
                skill_name=skill_id,
                context=stream_context,
                thread_id=thread_id,
                enable_thinking=call_thinking_enabled,
                subagent_enabled=call_subagent_enabled,
                plan_mode=call_plan_mode,
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
                            run_id,
                            msg_id,
                            len(content) if content else 0,
                            bool(tool_calls),
                        )
                        if content:
                            ai_response_parts.append(content)
                        else:
                            logger.warning(
                                "[_run_numina_agent] AI message with empty content: run=%s data_keys=%s",
                                run_id,
                                list(data.keys()),
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
                                tool_type, display_name, icon, display_key = (
                                    resolve_tool_metadata(raw_name)
                                )
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
                            await bridge.publish(
                                run_id,
                                "custom",
                                {
                                    "type": "tool_result",
                                    "tool_call_id": tool_call_id,
                                    "tool_name": tool_name,
                                    "content": content,
                                },
                            )

        # 7a. First (user-visible) stream turn.
        await _stream_once(redacted)

        # 7b. U4 goal continuation loop (D1 — DeerFlow worker.py:519-542 parity).
        # After the user-visible turn, evaluate whether the active goal is
        # satisfied; if not (and the blocker is the only continuable one,
        # ``goal_not_met_yet``), inject a hidden continuation turn and stream
        # again. Repeat until satisfied or the double-breaker trips
        # (continuation_count/max 0/8 + no_progress_count/max 0/2). The loop is
        # cleanly separable: if it proves unstable it can be removed entirely
        # and goal set/clear/status (U2) + GoalStatusBar (U5) still work (R1).
        #
        # CRITICAL (P0): ``missing_evidence`` and any non-``goal_not_met_yet``
        # blocker MUST stand down — DeerFlow stops on these
        # (``CONTINUABLE_GOAL_BLOCKERS = {"goal_not_met_yet"}`` only), it does
        # NOT continue on them. Continuing on ``missing_evidence`` is the
        # unbounded-loop vector.
        while not record.abort_event.is_set():
            continuation = await _prepare_goal_continuation_input(
                checkpointer=_get_shared_checkpointer_for_goal(),
                thread_id=thread_id,
                run_id=run_id,
                family_ai_config=selected_provider or {},
                family_id=family_id,
                user_id=user_id,
                abort_event=record.abort_event,
            )
            if continuation is None:
                break
            logger.info(
                "[_run_numina_agent] goal continuation run=%s thread=%s count=%s",
                run_id,
                thread_id,
                continuation.get("continuation_count"),
            )
            await _stream_once(continuation["context"], is_continuation=True)

        # 8. Terminal status - drives the `end` completion signal (Q2).
        # ``interrupted`` is set only by user-initiated cancel via abort_event.
        if record.abort_event.is_set():
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
        # dispatch reached the skill-selection step (line ~234), and is None
        # for slash-activated messages (U2) where set_active_skill was skipped.
        if "_skill_token" in locals() and _skill_token is not None:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )

            reset_active_skill(_skill_token)

        # 9. Audit log (Key Invariant #3)
        audit_logger.log_call(
            AuditEntry(
                family_id=family_id,
                audit_id=run_id,
                user_id=user_id or "",
                skill_id="chat",
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
        if completion_status == "complete" and selected_provider is not None:
            ai_response = "".join(ai_response_parts)
            suggestions = await generate_suggestions(
                ai_response, user_message, selected_provider
            )
            if suggestions:
                await bridge.publish(
                    run_id,
                    "custom",
                    {
                        "type": "suggestions",
                        "suggestions": suggestions,
                    },
                )

        # Q2: publish a real `end` data frame carrying the completion status
        # so the frontend can distinguish a clean completion from a truncated
        # stream (#19) without guessing from content. publish_end() below only
        # signals the sentinel (data=None), so the data frame must precede it.
        # Include cumulative token usage from DeerFlow when available.
        end_payload: dict[str, Any] = {"status": completion_status}
        if cumulative_usage:
            end_payload["usage"] = cumulative_usage
        await bridge.publish(run_id, "end", end_payload)

        if completion_status == "complete" and selected_provider is not None:
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
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))
