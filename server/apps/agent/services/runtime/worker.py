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
import time
from typing import Any

from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.schemas.context import FamilyContext
from apps.agent.services.audit_logger import AuditEntry, audit_logger
from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.services.pii_redactor import pii_redactor

from .gc import schedule_run_cleanup
from .run_extras import generate_suggestions, sync_title_from_checkpoint

logger = logging.getLogger(__name__)

# Track fire-and-forget background tasks so they don't get garbage collected prematurely
_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    """Track a background task and auto-remove it when done."""
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _background_tasks.discard(t))


async def run_family_agent(
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
    """Background agent execution for a family-scoped run.

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
                "[run_family_agent] get_enabled_mcp_servers failed family=%s err=%s",
                family_id, type(exc).__name__,
            )
            mcp_servers = []

        # 4. Build adapter (uses per-family LRU cache from family_adapter_cache.py)
        #
        # subagent_enabled/plan_mode init-time defaults are False; per-call
        # overrides (driven by the frontend's flash/thinking/pro/ultra mode
        # selector) are extracted from ``config["configurable"]`` below and
        # passed to typed_stream_dispatch as kwargs, which route them into
        # DeerFlowClient.stream() -> _get_runnable_config() to override the
        # init-time setting for this specific call. This mirrors the reference
        # Gateway path (agent_dispatch.stream_agent_dispatch).
        adapter = create_family_adapter(
            family_id,
            selected_provider,
            timeout_seconds=240,
            subagent_enabled=False,
            plan_mode=False,
            mcp_servers=mcp_servers,
        )

        # 4a. Extract per-call execution-mode overrides from the RunnableConfig.
        # The frontend sends these in config.configurable (see reference
        # backend/app/gateway/services.py:merge_run_context_overrides). They
        # control DeerFlow's tool loading (subagent_enabled -> task tool) and
        # planning middleware (plan_mode -> TodoList) on a per-call basis.
        configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
        call_subagent_enabled = bool(configurable.get("subagent_enabled", False))
        call_plan_mode = bool(configurable.get("is_plan_mode", False))
        call_thinking_enabled = bool(configurable.get("thinking_enabled", True))
        call_websearch_enabled = bool(configurable.get("websearch_enabled", False))

        # 5. Extract user message for context
        if graph_input and "messages" in graph_input:
            msgs = graph_input["messages"]
            if isinstance(msgs, list) and msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") in ("user", "human"):
                    user_message = last.get("content", "")

        # 5a. Inject web_search behavioural guidance so the LLM knows whether it
        # may search. The web_search tool is always loaded when the family has a
        # configured provider (family_adapter_cache.py:485), but without this
        # prompt the LLM won't proactively call it. Mirrors chat_adapter.py:96-100
        # and agent_dispatch.py:630-651 (legacy Gateway path).
        if call_websearch_enabled:
            web_search_providers = ai_config.get("web_search_providers", [])
            web_search_mcp_servers = ai_config.get("web_search_mcp_servers", [])
            if web_search_providers:
                web_search_guidance = "用户已启用联网搜索。如果需要最新信息，你可以调用搜索工具获取。"
            elif web_search_mcp_servers:
                web_search_guidance = (
                    "用户已启用联网搜索（MCP 模式）。如果需要最新信息，你可以调用 MCP 搜索工具获取。"
                )
            else:
                web_search_guidance = "用户未启用联网搜索。请仅基于已有工具和知识回答，不要尝试联网。"
            user_message = f"## 联网搜索\n\n{web_search_guidance}\n\n{user_message}"

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
        capability = "chat-search" if call_websearch_enabled else "chat"
        async for sse_type, data in adapter.typed_stream_dispatch(
            skill_name=capability,
            context=redacted,
            thread_id=thread_id,
            enable_thinking=call_thinking_enabled,
            subagent_enabled=call_subagent_enabled,
            plan_mode=call_plan_mode,
        ):
            # Cooperative cancellation check (DeerFlow pattern)
            if record.abort_event.is_set():
                break

            if sse_type == "end":
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
                if data.get("type") == "ai" and data.get("content"):
                    ai_response_parts.append(data["content"])
                tool_calls_raw = data.get("tool_calls")
                if tool_calls_raw:
                    for tc in tool_calls_raw:
                        await bridge.publish(run_id, "custom", {
                            "type": "tool_call",
                            "tool_call_id": tc.get("id", ""),
                            "tool_name": tc.get("name", ""),
                            "args": tc.get("args", {}),
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
        logger.warning("[run_family_agent] failed run=%s err=%s", run_id, error_type)
        await run_manager.set_status(run_id, RunStatus.error, error=str(exc))
        await bridge.publish(
            run_id,
            "error",
            {"message": str(exc), "name": error_type},
        )

    finally:
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
        # 10. Terminal frames: `end` with completion status (Q2), follow-up
        # suggestions (R8), and fire-and-forget title generation — then the
        # end sentinel + deferred cleanup (DeerFlow pattern).
        #
        # Q2: publish a real `end` data frame carrying the completion status
        # so the frontend can distinguish a clean completion from a truncated
        # stream (#19) without guessing from content. publish_end() below only
        # signals the sentinel (data=None), so the data frame must precede it.
        await bridge.publish(run_id, "end", {"status": completion_status})

        # R8: generate follow-up suggestions from the selected provider config
        # — NOT the whole ``ai_config`` envelope, which nests provider keys
        # (api_key/ai_model_id/ai_base_url) under ``providers``. Passing the
        # envelope leaves every key unset, so the suggestions LLM falls back
        # to a dummy key and silently 401s. Skipped when the run aborted
        # before a provider was selected OR when the run was cancelled/interrupted.
        # Mirrors the legacy runs.py:251-254 finally-block behavior.
        if completion_status == 'complete' and selected_provider is not None:
            ai_response = "".join(ai_response_parts)
            suggestions = await generate_suggestions(ai_response, user_message, selected_provider)
            if suggestions:
                await bridge.publish(run_id, "custom", {
                    "type": "suggestions",
                    "suggestions": suggestions,
                })

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
