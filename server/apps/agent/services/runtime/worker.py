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
from typing import Any

from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.message_classifier import (
    extract_tool_calls,
    resolve_tool_metadata,
)

# Shared provider-selection helper (circuit-state aware). Imported lazily via
# function scope in each runner to avoid a circular import with orchestrator.py
# — but the symbol is referenced here at module level for testability.
from apps.agent.services.orchestrator import _select_stream_run_provider
from apps.agent.services.pii_redactor import pii_redactor
from packages.core import get_path_manager

from .asset_report_middleware import parse_report_json
from .gc import schedule_run_cleanup
from .goal_continuation import (
    _get_shared_checkpointer_for_goal,
    _prepare_goal_continuation_input,
)
from .run_extras import generate_suggestions, sync_title_from_checkpoint
from .run_pipeline import (
    _fire_and_forget_circuit_report,
    _resolve_numina_mcp_servers,
    _track_task,
)
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
      - ``literacy-weekly-report`` → ``_run_literacy_weekly_report_agent`` (启蒙周报).

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
        if app == "literacy-weekly-report":
            await _run_literacy_weekly_report_agent(
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


async def _set_session_title(thread_id: str, family_id: int, title_prefix: str) -> None:
    """Set a fixed-format title on a session.

    Best-effort: any failure is logged and swallowed.
    """
    try:
        from datetime import UTC, datetime

        from apps.agent.services.session_store import AiSessionRepository

        now = datetime.now(UTC)
        title = f"{title_prefix} {now.strftime('%Y%m%d %H%M')}"
        repo = AiSessionRepository(str(family_id))
        await repo.update_summary(
            session_id=thread_id,
            family_id=str(family_id),
            summary=None,
            title=title,
        )
        logger.info("[_set_session_title] Set title '%s' for thread %s", title, thread_id)
    except Exception as e:
        logger.warning("[_set_session_title] Failed for thread %s: %s", thread_id, e)


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
    """Asset-report 3-step pipeline dispatch branch via RunPipeline (U4).

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

    Differences vs chat:
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
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="asset-report",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        enable_thinking=False,  # Qwen3: avoid empty content (see memory qwen3-enable-thinking-empty-content)
        timeout_seconds=240,
    ) as p:
        # App-specific delta: trigger construction + result extraction

        # Synthetic trigger message (plan L117): report runs are backend-
        # initiated with no natural user message. Use the slash-activation form
        # so the LLM loads asset-report/SKILL.md (not chat/SKILL.md). If the
        # backend already supplied a user message in graph_input, prefer it.
        # Localize the trigger based on user's language preference so the first
        # user input the LLM sees matches the target language.
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _SYNTHETIC_TRIGGERS_BY_LANG.get("asset-report", {}).get(
            user_language, _SYNTHETIC_ASSET_REPORT_TRIGGER
        )
        user_message = _extract_backend_user_message(graph_input) or user_message

        # Append language instruction based on user's language preference.
        # SKILL.md is static; the LLM needs an explicit per-run directive to
        # output in the user's chosen language (not always Chinese).
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{user_message}\n\n{lang_instruction}"

        await p.run_skill(user_message)

        # Step 3: worker-synthesized report.step2_json emission + persistence.
        # The middleware path (AssetReportStep2Middleware via get_stream_writer)
        # was attempted but is no-op on numina's sync stream() path (plan step 3
        # fallback condition: "numina 租户隔离动态加载阻断"). Worker synthesis is
        # the plan-sanctioned fallback — emit exactly one report.step2_json
        # before the end frame (timing contract: strictly precedes end), then
        # persist. Best-effort persistence: a failure must not fail the run.
        if p.completion_status == "complete":
            ai_text = p.ai_text
            step2_payload = parse_report_json(ai_text)
            if step2_payload is not None:
                await bridge.publish(
                    p.run_id,
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
                    run_id=p.run_id,
                    user_id=user_id,
                    ai_text=ai_text,
                    write_file_paths=p.captured_write_file_paths,
                )
                try:
                    client = BackendClient(family_id=family_id)
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
                        p.run_id,
                        type(persist_exc).__name__,
                    )
                    p.set_error(
                        "结构化结果保存失败，可参考上方文本",
                        error_type=type(persist_exc).__name__,
                    )

        # Set report session title (fixed format with timestamp).
        if p.completion_status == "complete":
            asyncio.create_task(
                _set_session_title(thread_id, family_id, "家庭资产分析报告")
            )


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


def _extract_backend_user_message(graph_input: dict | None) -> str | None:
    """Pull the backend-injected user message from graph_input.

    Multiple runners receive domain-specific content (PDF text, finance snapshot,
    wishes JSON, narrative context, literacy report) as the last user message in
    ``graph_input["messages"]``. This helper extracts it; callers fall back to a
    synthetic trigger when None is returned.
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
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="import-parse",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        memory_enabled=False,  # stateless — each run parses the document fresh
        enable_thinking=False,  # Qwen3: avoid empty content
    ) as p:
        # App-specific delta: trigger construction + result extraction
        user_message = (
            _extract_backend_user_message(graph_input)
            or _SYNTHETIC_IMPORT_PARSE_TRIGGER
        )
        await p.run_skill(user_message)

        # Worker-synthesized import-parse.result emission (mirrors asset-report
        # step-3 worker synthesis — middleware get_stream_writer() path is no-op
        # on numina's sync stream() path). Emit exactly one import-parse.result
        # before the end frame (timing contract: strictly precedes end).
        if p.completion_status == "complete":
            parsed = parse_report_json(p.ai_text)
            if parsed is not None:
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "import-parse.result",
                        "payload": parsed,
                    },
                )

    # Set import-parse session title (fixed format with timestamp)
    if p.completion_status == "complete":
        asyncio.create_task(_set_session_title(thread_id, family_id, "文件导入解析"))


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
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="finance-coach",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        memory_enabled=False,  # stateless — fresh snapshot each run
        enable_thinking=False,
    ) as p:
        # App-specific delta: trigger construction + result extraction
        user_message = (
            _extract_backend_user_message(graph_input)
            or _SYNTHETIC_FINANCE_COACH_TRIGGER
        )
        await p.run_skill(user_message)

        # Worker-synthesized finance_coach.result emission (mirrors import-parse
        # worker synthesis). Emit exactly one finance_coach.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        if p.completion_status == "complete":
            parsed = parse_report_json(p.ai_text)
            if parsed is not None:
                # Advice baseline (spec §7.1): the worker emits the raw parsed
                # suggestions. Schema-validation gate (suggested_amount >= 0,
                # required fields) runs in Plan B's D2/W4 UI before any enable;
                # a malformed payload is dropped there, not here (the worker is
                # transport, not policy).
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "finance_coach.result",
                        "payload": parsed,
                    },
                )



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
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="wish-advice",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        memory_enabled=False,  # stateless — fresh snapshot each run
        enable_thinking=False,
    ) as p:
        # App-specific delta: trigger construction + result extraction
        user_message = (
            _extract_backend_user_message(graph_input) or _SYNTHETIC_WISH_ADVICE_TRIGGER
        )
        await p.run_skill(user_message)

        # Worker-synthesized wish_advice.result emission (mirrors finance-coach
        # worker synthesis). Emit exactly one wish_advice.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        if p.completion_status == "complete":
            parsed = parse_report_json(p.ai_text)
            if parsed is not None:
                # Advice baseline (spec §7.1): the worker emits the raw parsed
                # advice. Schema-validation gate (suggested_amount >= 0, required
                # fields) runs in Plan B's W4 UI (WishAdviceCard.validateAdvice)
                # + backend validate_advice before any enable; a malformed payload
                # is dropped there, not here (the worker is transport, not policy).
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "wish_advice.result",
                        "payload": parsed,
                    },
                )


# Synthetic trigger for dashboard-narrative runs (mirrors _SYNTHETIC_FINANCE_COACH_TRIGGER).
_SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER = "/dashboard-narrative 生成本月财务叙事"



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
    """dashboard-narrative dispatch branch via RunPipeline.

    Runs a single ``stream_run`` agent run with ``skill_name="dashboard-narrative"``.
    The skill prompt drives the LLM to generate 2-3 sentences of financial narrative
    from the backend-injected context. Emits one ``dashboard_narrative.result`` custom
    event with the plain-text narrative before the ``end`` frame.

    Simpler than finance-coach: no MCP tools (allowed-tools: []), no JSON parsing —
    the LLM output IS the narrative text (after stripping code fences if any).
    """
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="dashboard-narrative",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        enable_thinking=True,
        timeout_seconds=60,
        mcp_servers=[],  # allowed-tools: [] — pure inference
    ) as p:
        user_message = (
            _extract_backend_user_message(graph_input)
            or _SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER
        )
        await p.run_skill(user_message, enable_reasoning_delta=True)

        # Emit dashboard_narrative.result custom event (with thinking)
        if p.completion_status == "complete":
            narrative_text = p.ai_text.strip()
            if narrative_text:
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "dashboard_narrative.result",
                        "payload": {
                            "narrative": narrative_text,
                            "thinking": p.thinking_text,
                        },
                    },
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
    _skill_token = None
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
        selected_provider = _select_stream_run_provider(providers)
        if selected_provider is None:
            raise RuntimeError("无可用 AI 供应商（所有 provider 均已熔断）")

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
        # Circuit-breaker reporting: classify the exception and report to the
        # backend so the provider's circuit_state can transition to open.
        _fire_and_forget_circuit_report(
            family_id, selected_provider, exc
        )
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
        # Clear the active-skill ContextVar so it cannot leak into a later run
        # reusing this thread/coroutine. Guarded: _skill_token is only set if
        # dispatch reached the skill-selection step, and is None
        # for slash-activated messages (U2) where set_active_skill was skipped.
        if _skill_token is not None:
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

        # Thread title: generate for ALL completion states (complete, interrupted,
        # error) so even cancelled/failed threads get a sidebar title (DeerFlow
        # ``_ensure_interrupted_title`` pattern). The sync ``after_model`` hook
        # already produced a fallback title via the values SSE events during the
        # stream; this post-stream step upgrades it to an LLM-generated title
        # when possible, then publishes the final title via a values event so
        # the frontend can update the sidebar without polling.
        generated_title: str | None = None
        if selected_provider is not None and user_message:
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
            try:
                generated_title = await task
            except Exception:
                generated_title = None

        # Publish the generated title via a values event so the frontend updates
        # the sidebar in real-time (DeerFlow pattern: title flows through the
        # values SSE channel, not a separate HTTP poll).
        if generated_title:
            await bridge.publish(run_id, "values", {"title": generated_title})

        await bridge.publish_end(run_id)
        asyncio.create_task(bridge.cleanup(run_id, delay=60))
        asyncio.create_task(schedule_run_cleanup(run_manager, run_id, delay=300))


# Synthetic trigger for literacy-weekly-report runs.
_SYNTHETIC_LITERACY_REPORT_TRIGGER = "/literacy-weekly-report"



async def _run_literacy_weekly_report_agent(
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
    """literacy-weekly-report dispatch branch via RunPipeline.

    Runs a single stream_run agent with skill_name='literacy-weekly-report'.
    The agent calls MCP tools (get_child_literacy_profile, get_literacy_weekly_data)
    to fetch literacy data and generates a weekly report narrative.

    Design rationale:
    - ``skill_name="literacy-weekly-report"`` (fixed skill, no chat routing).
    - ``thinking=True``: SKILL.md declares ``thinking: true`` — the LLM uses
      deep reasoning for data analysis and personalized suggestions.
    - ``plan_mode=False``: simple report generation, no multi-step planning
      or TodoMiddleware needed.
    - ``subagent_enabled=False``: no delegation to sub-agents.
    - Synthetic trigger message ``/literacy-weekly-report ...``: follows the
      DeerFlow canonical skill pattern — agent fetches its own data via MCP
      tools rather than receiving pre-aggregated context.
    - No tool_call/tool_result synthesis (MCP tools are not visualised).
    - Reasoning content extracted from AI messages and forwarded as
      ``reasoning_delta`` custom events (separate from visible content).
    - Result custom event: ``literacy_weekly_report.result`` with
      ``{report, thinking}`` payload for backend persistence.
    """
    from .run_pipeline import RunPipeline

    async with RunPipeline(
        app_name="literacy-weekly-report",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=False,
        subagent_enabled=False,
        enable_thinking=True,
        timeout_seconds=120,
    ) as p:
        user_message = (
            _extract_backend_user_message(graph_input)
            or _SYNTHETIC_LITERACY_REPORT_TRIGGER
        )
        await p.run_skill(user_message, enable_reasoning_delta=True)

        # Emit literacy_weekly_report.result custom event (with thinking)
        if p.completion_status == "complete":
            report_text = p.ai_text.strip()
            if report_text:
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "literacy_weekly_report.result",
                        "payload": {
                            "report": report_text,
                            "thinking": p.thinking_text,
                        },
                    },
                )

            # Set literacy weekly report session title (fixed format).
            asyncio.create_task(
                _set_session_title(thread_id, family_id, "启蒙周报")
            )
