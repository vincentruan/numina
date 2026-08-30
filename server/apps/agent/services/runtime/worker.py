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
from pathlib import Path
from typing import Any

from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.core.backend_client import BackendClient
from packages.core import get_path_manager

from .goal_continuation import (
    _get_shared_checkpointer_for_goal,
    _prepare_goal_continuation_input,
)
from .llm_json_repair import (
    _COACH_REPAIR_PROMPT,
    _IMPORT_PARSE_REPAIR_PROMPT,
    _REPORT_REPAIR_PROMPT,
    _WISH_ADVICE_REPAIR_PROMPT,
    _repair_coach_json_via_llm,
    _repair_import_parse_json_via_llm,
    _repair_report_json_via_llm,
    _repair_wish_advice_json_via_llm,
    extract_coach_snapshot_ids,
    extract_json_via_llm,
    filter_coach_suggestions_by_ids,
    parse_report_json,
    run_json_repair_loop,
    validate_coach_json,
    validate_import_parse_json,
    validate_report_json,
    validate_wish_advice_json,
)
from .run_extras import (
    generate_suggestions,
    strip_language_prefix,
    sync_title_from_checkpoint,
)
from .run_pipeline import _track_task
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


# ---------------------------------------------------------------------------
# U12: Task progress callback helpers
# ---------------------------------------------------------------------------


async def _heartbeat_loop(
    task_id: int,
    family_id: str,
    interval: float = 40.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Background heartbeat loop for dead-worker detection (U12).

    Calls BackendClient.heartbeat() every `interval` seconds until stop_event
    is set or the task is cancelled. Network errors are logged but don't stop
    the loop (heartbeat is best-effort).

    Args:
        task_id: AITask primary key.
        family_id: Family ID for tenant isolation.
        interval: Seconds between heartbeats (default 40s, < lease TTL 120s).
        stop_event: Optional event to signal loop termination.
    """
    if stop_event is None:
        stop_event = asyncio.Event()

    client = BackendClient(family_id)
    while not stop_event.is_set():
        try:
            await client.heartbeat(task_id)
            logger.debug("[heartbeat] task=%s family=%s", task_id, family_id)
        except Exception as e:
            logger.warning(
                "[heartbeat] failed task=%s family=%s err=%s",
                task_id,
                family_id,
                e,
            )
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            break  # stop_event was set
        except TimeoutError:
            continue  # interval elapsed, send another heartbeat


def _extract_task_id(metadata: dict | None) -> int | None:
    """Extract task_id from run metadata (U12).

    Backend passes task_id in metadata when triggering agent runs. Returns None
    if not present (backward compatibility with old triggers).
    """
    if not metadata:
        return None
    task_id = metadata.get("task_id")
    if task_id is None:
        return None
    try:
        return int(task_id)
    except (ValueError, TypeError):
        return None


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

    # U12: Extract task_id from run metadata and start a background heartbeat
    # loop to renew AITask.lease_expires_at (dead-worker detection). Skipped when
    # task_id is absent (backward-compatible with old triggers).
    task_id = _extract_task_id(record.metadata if record else None)
    heartbeat_stop: asyncio.Event | None = None
    heartbeat_task: asyncio.Task | None = None
    if task_id is not None:
        heartbeat_stop = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            _heartbeat_loop(task_id, family_id, stop_event=heartbeat_stop)
        )

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
    except Exception as exc:
        # P0 fix: propagate init/dispatch errors to the SSE consumer instead of
        # silently hanging.  ``run_agent`` is invoked via ``asyncio.create_task``
        # in the SSE gateway — an unhandled exception here is never observed,
        # leaving the frontend waiting on an empty stream until its own timeout.
        # Publish an ``error`` frame (LangGraph SSE wire format) so the frontend
        # ``readSSEStream`` dispatches to ``onError`` and the UI can show a
        # retry button instead of an indefinite spinner.
        logger.error(
            "[run_agent] dispatch failed app=%s run=%s: %s",
            record.metadata.get("app", "numina") if record.metadata else "numina",
            record.run_id,
            exc,
            exc_info=True,
        )
        try:
            await run_manager.set_status(record.run_id, RunStatus.error)
            await bridge.publish(
                record.run_id,
                "error",
                {"error": str(exc) or "Agent dispatch failed"},
            )
            await bridge.publish(record.run_id, "end", {"status": "error"})
        except Exception:
            logger.exception("[run_agent] failed to publish error frame")
    finally:
        # U12: Stop the heartbeat loop and await it (best-effort).
        if heartbeat_stop is not None:
            heartbeat_stop.set()
        if heartbeat_task is not None:
            try:
                await asyncio.wait_for(heartbeat_task, timeout=2.0)
            except Exception:
                heartbeat_task.cancel()
        reset_family_sandbox_context()


async def _set_session_title(thread_id: str, family_id: str, title_prefix: str) -> None:
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
        logger.info(
            "[_set_session_title] Set title '%s' for thread %s", title, thread_id
        )
    except Exception as e:
        logger.warning("[_set_session_title] Failed for thread %s: %s", thread_id, e)


def _persist_session_status(
    *,
    thread_id: str,
    family_id: str,
    status: str,
) -> None:
    """Best-effort write of terminal session status to ai_chat_sessions.

    DeerFlow pattern: the worker's finally block always persists the terminal
    status so the DB row reflects the actual run outcome.  Numina runs this
    synchronously at the end of _run_numina_agent (not fire-and-forget) because
    it is a single HTTP call and we want the status to be durable before the
    SSE end frame reaches the frontend.  All failures are logged and swallowed.
    """
    try:
        from apps.agent.services.session_store import AiSessionRepository

        repo = AiSessionRepository(family_id)
        # update_summary default status="completed" — pass explicit value so
        # error/interrupted outcomes are persisted correctly.
        repo_update = repo.update_summary(
            session_id=thread_id,
            family_id=family_id,
            summary=None,
            status=status,
        )
        # Fire-and-forget: we don't await so a slow backend doesn't block
        # the SSE end frame.  Errors are caught inside update_summary.
        import asyncio

        asyncio.ensure_future(repo_update)
    except Exception as e:
        logger.warning(
            "[_persist_session_status] Failed for thread %s status=%s: %s",
            thread_id,
            status,
            e,
        )


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

    async with (
        RunPipeline(
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
        ) as p
    ):
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

        # Prepend language instruction as the first thing the LLM sees.
        # SKILL.md is language-neutral (all English); the user message carries
        # a forceful, earliest-visible directive so the LLM outputs in the
        # user's chosen language regardless of prompt content.
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"

        logger.info(
            "[_run_asset_report_pipeline] language=%s trigger_preview=%s",
            user_language,
            user_message[:80],
        )

        # Set report session title IMMEDIATELY so the sidebar/history shows
        # a proper label (e.g. "家庭资产分析报告 20260815 1430") from the moment
        # generation starts — even if the user navigates away, the pipeline
        # errors, or the SSE connection drops. Previously the title was only
        # set on completion_status=="complete" AFTER run_skill, leaving the
        # session with title=NULL ("新对话") when the run was interrupted or
        # the user returned later. _set_session_title is best-effort (internal
        # try/except) and idempotent — calling it again on completion overwrites
        # with a fresh timestamp for accurate generation time.
        _title = _SESSION_TITLES_BY_LANG.get("asset-report", {}).get(
            user_language,
            _SESSION_TITLES_BY_LANG.get("asset-report", {}).get(
                "default", "家庭资产分析报告"
            ),
        )
        _track_task(
            asyncio.create_task(_set_session_title(thread_id, family_id, _title))
        )

        await p.run_skill(user_message)
        _report_run_ok = True  # run_skill succeeded; completion_status set in __aexit__

        # Step 3: worker-synthesized report.step2_json emission + persistence.
        # The middleware path (AssetReportStep2Middleware via get_stream_writer)
        # was attempted but is no-op on numina's sync stream() path (plan step 3
        # fallback condition: "numina 租户隔离动态加载阻断"). Worker synthesis is
        # the plan-sanctioned fallback — emit exactly one report.step2_json
        # before the end frame (timing contract: strictly precedes end), then
        # persist. Best-effort persistence: a failure must not fail the run.
        if _report_run_ok:
            ai_text = p.ai_text
            step2_payload = parse_report_json(ai_text)

            # Phase 4B: validate→repair cycle (shared loop in llm_json_repair.py).
            # Validates parsed JSON, retries via LLM repair on failure (≤3 attempts, 240s).
            # Budget is 240s (not 120s) because when parse_report_json returns None
            # (unparseable output), the repair LLM must generate a full report JSON
            # from scratch — this is slower than fixing a minor schema mismatch.
            step2_payload, repair_count = await run_json_repair_loop(
                step2_payload,
                ai_text,
                validator=validate_report_json,
                repair_fn=lambda t, e: _repair_report_json_via_llm(
                    t, e, p.selected_provider
                ),
                publish_retry_event=lambda attempt: bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "report.repair_retry",
                        "attempt": attempt,
                        "max_attempts": 3,
                    },
                ),
                app_name="_run_asset_report_pipeline",
                budget_seconds=240,
            )
            retry_count = repair_count
            validation_errors = (
                validate_report_json(step2_payload)
                if step2_payload is not None
                else ["无法解析报告 JSON"]
            )

            if validation_errors:
                # Phase 4B.5: Final fallback — standalone LLM extraction with
                # response_format=json_object. This is the "send to model for
                # alternative repair" step: the repair loop may have failed
                # because the LLM couldn't fix the JSON in-place, so we ask
                # a fresh LLM call to extract JSON from scratch.
                logger.info(
                    "[_run_asset_report_pipeline] repair loop exhausted, "
                    "attempting final LLM extraction fallback run=%s",
                    p.run_id,
                )
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {"type": "report.repair_final_fallback", "attempt": 1},
                )
                fallback_payload = await extract_json_via_llm(
                    ai_text,
                    _REPORT_REPAIR_PROMPT,
                    p.selected_provider,
                )
                if fallback_payload is not None:
                    fallback_errors = validate_report_json(fallback_payload)
                    if not fallback_errors:
                        logger.info(
                            "[_run_asset_report_pipeline] final LLM extraction "
                            "succeeded run=%s",
                            p.run_id,
                        )
                        step2_payload = fallback_payload
                        validation_errors = []
                    else:
                        logger.warning(
                            "[_run_asset_report_pipeline] final LLM extraction "
                            "also invalid run=%s errors=%s",
                            p.run_id,
                            fallback_errors[:3],
                        )

            if validation_errors:
                # Still invalid after all fallbacks — fail the run.
                logger.error(
                    "[_run_asset_report_pipeline] report JSON validation failed "
                    "after %d retries + final fallback run=%s errors=%s",
                    retry_count,
                    p.run_id,
                    validation_errors[:3],
                )
                p.set_error(
                    "报告结构化输出校验失败",
                    error_type="ReportValidationError",
                )
                # Publish error event to bridge so frontend SSE receives it
                # before the end frame (lifecycle consumer will fail the task).
                await bridge.publish(
                    p.run_id,
                    "error",
                    {
                        "error": "报告结构化输出校验失败，请重试",
                        "error_type": "ReportValidationError",
                    },
                )
                # Best-effort: still persist markdown_file_path so the user
                # can view the fallback markdown even when structured parse
                # failed. The sandbox file may be gone by the time the user
                # clicks "view", so copy it now.
                markdown_file_path = _copy_asset_report_markdown(
                    family_id=family_id,
                    thread_id=thread_id,
                    run_id=p.run_id,
                    user_id=user_id,
                    ai_text=ai_text,
                    write_file_paths=p.captured_write_file_paths,
                )
                if markdown_file_path:
                    try:
                        client = BackendClient(family_id=family_id)
                        await client.persist_report_result(
                            report_json={"indicators": [], "overall_score": 0},
                            markdown_file_path=markdown_file_path,
                        )
                    except Exception:
                        logger.warning(
                            "[_run_asset_report_pipeline] fallback persist "
                            "failed run=%s",
                            p.run_id,
                        )
            elif step2_payload is not None:
                logger.info(
                    "[_run_asset_report_pipeline] Extracted report JSON: "
                    "overall_score=%s indicators_count=%d ai_text_length=%d",
                    step2_payload.get("overall_score"),
                    len(step2_payload.get("indicators", [])),
                    len(ai_text),
                )
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
                    # Publish error event to bridge so frontend SSE receives it
                    # before the end frame (lifecycle consumer will fail the task).
                    await bridge.publish(
                        p.run_id,
                        "error",
                        {
                            "error": "报告保存失败，请重试",
                            "error_type": type(persist_exc).__name__,
                        },
                    )

    # Set report session title (localized by user language).
    if _report_run_ok:
        _title = _SESSION_TITLES_BY_LANG.get("asset-report", {}).get(
            user_language,
            _SESSION_TITLES_BY_LANG.get("asset-report", {}).get(
                "default", "家庭资产分析报告"
            ),
        )
        _track_task(
            asyncio.create_task(_set_session_title(thread_id, family_id, _title))
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
    "en-US": (
        "[LANGUAGE REQUIREMENT] Output language: English.\n\n"
        "IMPORTANT: The ENTIRE JSON output must use English for ALL user-visible text.\n"
        '- label fields: English (e.g. "Net Worth Health", NOT "净资产健康度")\n'
        "- narrative fields: English analysis text with **bold** + bullet lists\n"
        "- suggestions arrays: English, 1-2 sentences each\n"
        "- summary field: English, 100-250 words\n"
        "- Only 'key' fields use snake_case English (e.g. \"net_worth_health\").\n\n"
        "DO NOT output Chinese text anywhere except in the 'zh' field of data.items bilingual labels."
    ),
    "zh-CN": (
        "[语言要求] 输出语言：中文。\n\n"
        "所有用户可见文本字段必须使用中文：label、narrative、suggestions、summary。\n"
        "仅 key 字段使用英文 snake_case。"
    ),
    "default": (
        "[语言要求] 输出语言：中文。\n\n"
        "所有用户可见文本字段必须使用中文。仅 key 字段使用英文 snake_case。"
    ),
}


# Localized synthetic triggers — the slash prefix loads the skill, the rest
# sets the language tone for the LLM.
_SYNTHETIC_TRIGGERS_BY_LANG = {
    "asset-report": {
        "en-US": "/asset-report Generate family asset report",
        "zh-CN": "/asset-report 生成家庭资产报告",
        "default": "/asset-report 生成家庭资产报告",
    },
    "import-parse": {
        "en-US": "/import-parse Parse financial document holdings",
        "zh-CN": "/import-parse 解析金融文档持仓",
        "default": "/import-parse 解析金融文档持仓",
    },
    "finance-coach": {
        "en-US": "/finance-coach Generate family financial advice",
        "zh-CN": "/finance-coach 生成家庭财务建议",
        "default": "/finance-coach 生成家庭财务建议",
    },
    "wish-advice": {
        "en-US": "/wish-advice Generate wish savings advice",
        "zh-CN": "/wish-advice 生成心愿储蓄建议",
        "default": "/wish-advice 生成心愿储蓄建议",
    },
    "dashboard-narrative": {
        "en-US": "/dashboard-narrative Generate monthly financial narrative",
        "zh-CN": "/dashboard-narrative 生成本月财务叙事",
        "default": "/dashboard-narrative 生成本月财务叙事",
    },
    "literacy-weekly-report": {
        "en-US": "/literacy-weekly-report Generate weekly literacy report",
        "zh-CN": "/literacy-weekly-report 生成启蒙周报",
        "default": "/literacy-weekly-report 生成启蒙周报",
    },
}

# Localized session titles for skill runs (shown in chat history sidebar).
_SESSION_TITLES_BY_LANG = {
    "asset-report": {
        "en-US": "Family Asset Report",
        "zh-CN": "家庭资产分析报告",
        "default": "家庭资产分析报告",
    },
    "import-parse": {
        "en-US": "Document Import",
        "zh-CN": "文件导入解析",
        "default": "文件导入解析",
    },
    "literacy-weekly-report": {
        "en-US": "Literacy Weekly Report",
        "zh-CN": "启蒙周报",
        "default": "启蒙周报",
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
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(
            graph_input
        ) or _SYNTHETIC_TRIGGERS_BY_LANG.get("import-parse", {}).get(
            user_language, _SYNTHETIC_IMPORT_PARSE_TRIGGER
        )
        # Prepend language instruction for user-facing output
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"
        # Set import-parse session title IMMEDIATELY so sidebar/history shows
        # a proper label even if the user navigates away or the run errors.
        # _set_session_title is best-effort and idempotent.
        _ip_title = _SESSION_TITLES_BY_LANG.get("import-parse", {}).get(
            user_language,
            _SESSION_TITLES_BY_LANG.get("import-parse", {}).get(
                "default", "文件导入解析"
            ),
        )
        _track_task(
            asyncio.create_task(_set_session_title(thread_id, family_id, _ip_title))
        )
        await p.run_skill(user_message)
        _import_ok = True  # run_skill succeeded; completion_status set in __aexit__

        # Worker-synthesized import-parse.result emission (mirrors asset-report
        # step-3 worker synthesis — middleware get_stream_writer() path is no-op
        # on numina's sync stream() path). Emit exactly one import-parse.result
        # before the end frame (timing contract: strictly precedes end).
        if _import_ok:
            parsed = parse_report_json(p.ai_text)

            # Validate→repair cycle (shared loop)
            parsed, repair_count = await run_json_repair_loop(
                parsed,
                p.ai_text,
                validator=validate_import_parse_json,
                repair_fn=lambda t, e: _repair_import_parse_json_via_llm(
                    t, e, p.selected_provider
                ),
                publish_retry_event=lambda attempt: bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "import-parse.repair_retry",
                        "attempt": attempt,
                        "max_attempts": 3,
                    },
                ),
                app_name="_run_import_parse_agent",
            )

            # Final fallback: standalone LLM extraction
            if parsed is not None and validate_import_parse_json(parsed):
                fallback = await extract_json_via_llm(
                    p.ai_text, _IMPORT_PARSE_REPAIR_PROMPT, p.selected_provider,
                )
                if fallback is not None and not validate_import_parse_json(fallback):
                    parsed = fallback

            if parsed is not None and not validate_import_parse_json(parsed):
                logger.error(
                    "[_run_import_parse_agent] import-parse JSON validation failed "
                    "after %d retries + fallback run=%s errors=%s",
                    repair_count,
                    p.run_id,
                    validate_import_parse_json(parsed)[:3],
                )
                await bridge.publish(
                    p.run_id,
                    "error",
                    {"error": "文档解析结果格式异常，请重试"},
                )
            elif parsed is not None:
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "import-parse.result",
                        "payload": parsed,
                    },
                )
            else:
                logger.warning(
                    "[_run_import_parse_agent] JSON parse failed run=%s ai_text_len=%d",
                    p.run_id,
                    len(p.ai_text) if p.ai_text else 0,
                )
                await bridge.publish(
                    p.run_id,
                    "error",
                    {"error": "文档解析失败，请重试"},
                )

    # Set import-parse session title (localized by user language)
    if _import_ok:
        _title = _SESSION_TITLES_BY_LANG.get("import-parse", {}).get(
            user_language,
            _SESSION_TITLES_BY_LANG.get("import-parse", {}).get(
                "default", "文件导入解析"
            ),
        )
        _track_task(
            asyncio.create_task(_set_session_title(thread_id, family_id, _title))
        )


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
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(
            graph_input
        ) or _SYNTHETIC_TRIGGERS_BY_LANG.get("finance-coach", {}).get(
            user_language, _SYNTHETIC_FINANCE_COACH_TRIGGER
        )
        # Prepend language instruction for user-facing output
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"
        await p.run_skill(user_message)
        _coach_ok = True  # run_skill succeeded; completion_status set in __aexit__

        # Extract valid entity IDs from the snapshot for anti-hallucination
        # filtering. The user_message contains the snapshot JSON (possibly
        # prefixed with a [LANGUAGE REQUIREMENT] directive). extract_coach_snapshot_ids
        # tolerates the non-JSON prefix via json.loads fallback.
        _raw_snapshot = _extract_backend_user_message(graph_input) or ""
        _valid_coach_ids = extract_coach_snapshot_ids(_raw_snapshot)

        # Worker-synthesized finance_coach.result emission (mirrors import-parse
        # worker synthesis). Emit exactly one finance_coach.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        #
        # Validate → repair cycle (shared loop in llm_json_repair.py): the LLM may
        # output a valid JSON with wrong field names (e.g. priority/category/
        # action_steps instead of severity/target_type/cta_label). Without
        # validation the frontend silently drops all suggestions.
        if _coach_ok:
            parsed = parse_report_json(p.ai_text)

            # Validate→repair via shared loop
            parsed, repair_count = await run_json_repair_loop(
                parsed,
                p.ai_text,
                validator=validate_coach_json,
                repair_fn=lambda t, e: _repair_coach_json_via_llm(
                    t, e, p.selected_provider
                ),
                publish_retry_event=lambda attempt: bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "coach.repair_retry",
                        "attempt": attempt,
                        "max_attempts": 3,
                    },
                ),
                app_name="_run_finance_coach_agent",
            )

            if parsed is not None:
                validation_errors = validate_coach_json(parsed)
                if validation_errors:
                    # Final fallback: standalone LLM extraction
                    logger.info(
                        "[_run_finance_coach_agent] repair loop exhausted, "
                        "attempting final LLM extraction fallback run=%s",
                        p.run_id,
                    )
                    fallback = await extract_json_via_llm(
                        p.ai_text, _COACH_REPAIR_PROMPT, p.selected_provider,
                    )
                    if fallback is not None and not validate_coach_json(fallback):
                        parsed = fallback
                        validation_errors = []
                    else:
                        logger.error(
                        "[_run_finance_coach_agent] coach JSON validation failed after %d retries run=%s errors=%s",
                        repair_count,
                        p.run_id,
                        validation_errors[:5],
                    )
                    await bridge.publish(
                        p.run_id,
                        "error",
                        {"error": "财务建议格式异常，请重试"},
                    )
                else:
                    # Anti-hallucination: sanitise suggestions referencing entity
                    # IDs not present in the snapshot (LLM fabricated IDs → 404
                    # on click).  target_id/target_type are cleared so the text
                    # is still shown but the CTA button is inert.
                    if _valid_coach_ids:
                        parsed, _filtered = filter_coach_suggestions_by_ids(
                            parsed, _valid_coach_ids
                        )
                        if _filtered:
                            logger.warning(
                                "[_run_finance_coach_agent] sanitised %d suggestions "
                                "with hallucinated target_id run=%s",
                                _filtered,
                                p.run_id,
                            )
                    logger.info(
                        "[_run_finance_coach_agent] result emitted run=%s suggestions_count=%d repairs=%d",
                        p.run_id,
                        len(parsed.get("suggestions", [])),
                        repair_count,
                    )
                    await bridge.publish(
                        p.run_id,
                        "custom",
                        {
                            "type": "finance_coach.result",
                            "payload": parsed,
                        },
                    )
            else:
                # LLM output couldn't be parsed as JSON. Emit an error frame so the
                # frontend can surface a retry instead of silently showing
                # "No suggestions". Do NOT emit an empty finance_coach.result —
                # the backend lifecycle consumer would persist it and overwrite
                # a valid cached result with an empty one.
                logger.warning(
                    "[_run_finance_coach_agent] JSON parse failed run=%s ai_text_len=%d ai_text_preview=%s",
                    p.run_id,
                    len(p.ai_text) if p.ai_text else 0,
                    (p.ai_text[:200] if p.ai_text else "")[:200],
                )
                await bridge.publish(
                    p.run_id,
                    "error",
                    {"error": "财务建议生成失败，请重试"},
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
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(
            graph_input
        ) or _SYNTHETIC_TRIGGERS_BY_LANG.get("wish-advice", {}).get(
            user_language, _SYNTHETIC_WISH_ADVICE_TRIGGER
        )
        # Prepend language instruction for user-facing output
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"
        await p.run_skill(user_message)
        _wish_ok = True  # run_skill succeeded; completion_status set in __aexit__

        # Worker-synthesized wish_advice.result emission (mirrors finance-coach
        # worker synthesis). Emit exactly one wish_advice.result before the end
        # frame. parse_report_json extracts the ```json block the LLM produced.
        #
        # Validate → repair cycle (shared loop in llm_json_repair.py): validates
        # the wish-advice schema before emitting. On failure, retries via LLM
        # repair. On persistent failure, emits an error frame instead of silently
        # dropping the malformed payload.
        if _wish_ok:
            parsed = parse_report_json(p.ai_text)

            # Validate→repair via shared loop
            parsed, repair_count = await run_json_repair_loop(
                parsed,
                p.ai_text,
                validator=validate_wish_advice_json,
                repair_fn=lambda t, e: _repair_wish_advice_json_via_llm(
                    t, e, p.selected_provider
                ),
                publish_retry_event=lambda attempt: bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "wish.repair_retry",
                        "attempt": attempt,
                        "max_attempts": 3,
                    },
                ),
                app_name="_run_wish_advice_agent",
            )

            if parsed is not None:
                validation_errors = validate_wish_advice_json(parsed)
                if validation_errors:
                    # Final fallback: standalone LLM extraction
                    logger.info(
                        "[_run_wish_advice_agent] repair loop exhausted, "
                        "attempting final LLM extraction fallback run=%s",
                        p.run_id,
                    )
                    fallback = await extract_json_via_llm(
                        p.ai_text, _WISH_ADVICE_REPAIR_PROMPT, p.selected_provider,
                    )
                    if fallback is not None and not validate_wish_advice_json(fallback):
                        parsed = fallback
                        validation_errors = []
                    else:
                        logger.error(
                        "[_run_wish_advice_agent] wish-advice JSON validation failed after %d retries run=%s errors=%s",
                        repair_count,
                        p.run_id,
                        validation_errors[:5],
                    )
                    await bridge.publish(
                        p.run_id,
                        "error",
                        {"error": "心愿储蓄建议格式异常，请重试"},
                    )
                else:
                    logger.info(
                        "[_run_wish_advice_agent] result emitted run=%s redistribution_count=%d repairs=%d",
                        p.run_id,
                        len(parsed.get("redistribution", [])),
                        repair_count,
                    )
                    await bridge.publish(
                        p.run_id,
                        "custom",
                        {
                            "type": "wish_advice.result",
                            "payload": parsed,
                        },
                    )
            else:
                # LLM output couldn't be parsed as JSON.
                logger.warning(
                    "[_run_wish_advice_agent] JSON parse failed run=%s ai_text_len=%d",
                    p.run_id,
                    len(p.ai_text) if p.ai_text else 0,
                )
                await bridge.publish(
                    p.run_id,
                    "error",
                    {"error": "心愿储蓄建议生成失败，请重试"},
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
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(
            graph_input
        ) or _SYNTHETIC_TRIGGERS_BY_LANG.get("dashboard-narrative", {}).get(
            user_language, _SYNTHETIC_DASHBOARD_NARRATIVE_TRIGGER
        )
        # Prepend language instruction for user-facing output
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"
        await p.run_skill(user_message, enable_reasoning_delta=True)
        _narrative_ok = True  # run_skill succeeded

        # Emit BEFORE __aexit__ publishes the "end" frame (run_pipeline.py:474),
        # so the lifecycle consumer sees result before the end sentinel.
        if _narrative_ok:
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
                logger.info(
                    "[dashboard-narrative] result emitted run=%s narrative_len=%d",
                    p.run_id,
                    len(narrative_text),
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

    Uses ``RunPipeline`` for the standard scaffolding (setup + streaming +
    teardown).  The chat runner is the only runner with extra complexity:
    per-call config overrides from the frontend, dynamic skill selection
    (chat vs chat-search), slash-message bypass, goal continuation loop,
    follow-up suggestions, and LLM-generated thread titles.

    The goal continuation loop (D1 — DeerFlow worker.py parity) calls
    ``p.run_skill()`` for each hidden continuation turn after the initial
    user-visible turn.  ``run_skill`` accumulates ``ai_response_parts`` and
    ``cumulative_usage`` across turns, so the post-stream hooks (suggestions,
    title) see the full conversation.
    """
    from .run_pipeline import RunPipeline

    # Pre-pipeline setup: resolve dynamic parameters that depend on the
    # family AI config (web-search capability, custom skills) or on the
    # frontend's per-call overrides (config.configurable).
    client = BackendClient(family_id=family_id)
    ai_config = await client.get_family_ai_config()

    # Extract per-call execution-mode overrides from the RunnableConfig.
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
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    call_subagent_enabled = bool(configurable.get("subagent_enabled", False))
    call_plan_mode = bool(configurable.get("is_plan_mode", False))
    call_thinking_enabled = bool(configurable.get("thinking_enabled", True))
    call_websearch_enabled = bool(configurable.get("websearch_enabled", False))
    # Retry checkpoint forking: when the frontend passes checkpoint_id
    # (from retryPrepare), fork from that checkpoint instead of the head.
    call_checkpoint_id = (
        configurable.get("checkpoint_id")
        if isinstance(configurable.get("checkpoint_id"), str)
        else None
    )

    # Web-search behavioral guidance lives in the skill files:
    # chat-search/SKILL.md ("联网搜索使用原则") and chat/SKILL.md ("不要尝试联网搜索").
    # The skill is selected below (chat-search vs chat) based on call_websearch_enabled,
    # so no runtime injection is needed — and injecting here would leak
    # internal guidance into user-visible prompts.
    # Only use chat-search when actual search capability is configured.
    # Otherwise the model is told it can search but has no tools → hallucinated searches.
    has_search_capability = bool(
        ai_config.get("web_search_providers") or ai_config.get("web_search_mcp_servers")
    )

    def _resolve_skill_name(cfg: dict) -> str:
        """Callable passed to RunPipeline.skill_name — resolved after ai_config
        is fetched inside __aenter__."""
        return (
            "chat-search"
            if (call_websearch_enabled and has_search_capability)
            else "chat"
        )

    # U3: Fetch enabled custom skills for slash activation whitelist.
    # The worker fetches the family's enabled custom skills and passes them
    # to create_family_adapter so DeerFlow's SkillActivationMiddleware enforces
    # the whitelist. Q1 resolution: custom-skills-only (builtin excluded).
    enabled_skills = await client.get_enabled_skills()
    available_skills = {
        s["skill_id"] for s in enabled_skills if s.get("skill_type") == "custom"
    }

    # Extract user message for suggestions and title generation.
    user_message = _extract_backend_user_message(graph_input) or ""
    # Strip the language-instruction prefix ([LANGUAGE REQUIREMENT] / [语言要求])
    # for user-facing outputs (title, suggestions). The LLM prompt in DeerFlow
    # still receives the prefixed version via the checkpoint messages.
    title_user_message = strip_language_prefix(user_message)

    # Determine whether this is a slash-activated skill message. For slash
    # messages, skip set_active_skill so DeerFlow's SkillActivationMiddleware
    # owns tool filtering instead of numina's _apply_active_skill_tool_filter.
    from deerflow.skills.slash import parse_slash_skill_reference

    is_slash_message = parse_slash_skill_reference(user_message) is not None

    # Build the pipeline with all numina-specific parameters.
    async with RunPipeline(
        app_name="numina",
        family_id=family_id,
        user_id=user_id,
        thread_id=thread_id,
        record=record,
        bridge=bridge,
        run_manager=run_manager,
        plan_mode=call_plan_mode,
        subagent_enabled=call_subagent_enabled,
        enable_thinking=call_thinking_enabled,
        timeout_seconds=240,
        skill_name=_resolve_skill_name,
        available_skills=available_skills,
        skip_active_skill=is_slash_message,
        middlewares=None,
        preloaded_ai_config=ai_config,
        checkpoint_id=call_checkpoint_id,
    ) as p:
        # For slash-activated skills (U2), set the skill context manually
        # after the pipeline's __aenter__ (which skipped set_active_skill).
        if is_slash_message:
            p.set_skill_token()

        # 1. First (user-visible) stream turn.
        await p.run_skill(user_message, enable_thinking=call_thinking_enabled)

        # 2. U4 goal continuation loop (D1 — DeerFlow worker.py parity).
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
                run_id=p.run_id,
                family_ai_config=p.selected_provider or {},
                family_id=family_id,
                user_id=user_id,
                abort_event=record.abort_event,
            )
            if continuation is None:
                break
            logger.info(
                "[_run_numina_agent] goal continuation run=%s thread=%s count=%s",
                p.run_id,
                thread_id,
                continuation.get("continuation_count"),
            )
            # Hidden continuation turn — same frame-forwarding as the first
            # turn (tool_call/tool_result synthesis, ai_response accumulation).
            # run_skill handles PII redaction internally (defense-in-depth).
            await p.run_skill(
                continuation["context"].free_text,
                enable_thinking=call_thinking_enabled,
            )

        # 3. Post-stream: follow-up suggestions (R8).
        # Generated BEFORE publishing `end`, because the frontend attaches
        # suggestions to the last AI message in the `end` handler. If
        # suggestions arrive after `end`, they are silently dropped.
        if p.selected_provider is not None:
            suggestions = await generate_suggestions(
                p.ai_text, title_user_message, p.selected_provider
            )
            if suggestions:
                await bridge.publish(
                    p.run_id,
                    "custom",
                    {
                        "type": "suggestions",
                        "suggestions": suggestions,
                    },
                )

        # 4. Post-stream: LLM-generated thread title.
        # Generated for ALL completion states (complete, interrupted, error)
        # so even cancelled/failed threads get a sidebar title (DeerFlow
        # ``_ensure_interrupted_title`` pattern).  Interrupted first turns pass
        # ``allow_partial_exchange=True`` so a lone user message still yields a
        # fallback title, matching DeerFlow's behaviour.
        if p.selected_provider is not None and title_user_message:
            was_interrupted = record.status == RunStatus.interrupted
            # Detect target language from the original (unstripped) user message.
            # If it starts with the English prefix, generate an English title;
            # otherwise default to Chinese.
            title_target_language = "Chinese"
            for _prefix in (
                "[LANGUAGE REQUIREMENT]",
                "[语言要求]",
            ):
                if user_message.startswith(_prefix):
                    title_target_language = (
                        "English" if _prefix == "[LANGUAGE REQUIREMENT]" else "Chinese"
                    )
                    break
            task = asyncio.create_task(
                sync_title_from_checkpoint(
                    thread_id,
                    family_id,
                    ai_config=p.selected_provider,
                    user_message=title_user_message,
                    ai_response=p.ai_text,
                    allow_partial_exchange=was_interrupted,
                    target_language=title_target_language,
                )
            )
            _track_task(task)
            try:
                generated_title = await task
            except Exception:
                generated_title = None
            if generated_title:
                await bridge.publish(p.run_id, "values", {"title": generated_title})

        # 5. Post-stream: persist terminal session status to DB.
        #    DeerFlow pattern (worker.py finally block): guarantee the session
        #    row reflects the actual run outcome.  sync_title_from_checkpoint
        #    writes status="completed" as a side-effect, but if it was skipped
        #    (no selected_provider, no user_message, or fire-and-forget task
        #    failed), the DB row stays at its initial value.  This call is
        #    best-effort — all failures are logged and swallowed.
        _persist_session_status(
            thread_id=thread_id,
            family_id=family_id,
            status=record.status.value
            if hasattr(record.status, "value")
            else str(record.status),
        )

        # 6. Emit chat.completed custom event for backend lifecycle tracking.
        # When the frontend SSE proxy breaks (user navigates away), the backend
        # spawns a _spawn_lifecycle_consumer that subscribes to the bridge
        # independently. This custom event signals successful completion so the
        # lifecycle consumer can call the on_result callback (if any). The
        # END_SENTINEL (published by RunPipeline.__aexit__) signals the stream
        # end, which triggers complete_task() in the lifecycle consumer.
        await bridge.publish(
            p.run_id,
            "custom",
            {"type": "chat.completed", "thread_id": thread_id},
        )


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
        user_language = (record.metadata or {}).get("language") or "zh"
        user_message = _extract_backend_user_message(
            graph_input
        ) or _SYNTHETIC_TRIGGERS_BY_LANG.get("literacy-weekly-report", {}).get(
            user_language, _SYNTHETIC_LITERACY_REPORT_TRIGGER
        )
        # Prepend language instruction for user-facing output
        if user_language:
            lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
                user_language, _LANGUAGE_INSTRUCTIONS["default"]
            )
            user_message = f"{lang_instruction}\n\n{user_message}"
        await p.run_skill(user_message, enable_reasoning_delta=True)
        _lit_ok = True

        # Emit literacy_weekly_report.result custom event (with thinking).
        # p.completion_status is only set to "complete" in __aexit__ (line 453),
        # so we use _lit_ok set after run_skill succeeds inside the block.
        if _lit_ok:
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

            # Set literacy weekly report session title (localized by user language).
            _lit_title = _SESSION_TITLES_BY_LANG.get("literacy-weekly-report", {}).get(
                user_language,
                _SESSION_TITLES_BY_LANG.get("literacy-weekly-report", {}).get(
                    "default", "启蒙周报"
                ),
            )
            _track_task(
                asyncio.create_task(
                    _set_session_title(thread_id, family_id, _lit_title)
                )
            )
