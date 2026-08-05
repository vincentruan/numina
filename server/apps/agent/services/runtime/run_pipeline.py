"""Shared scaffolding for stream_run agent runners.

Extracts the duplicated lifecycle logic that every runner in ``worker.py``
repeats: config fetch, provider selection, MCP resolution, adapter construction,
active-skill management, streaming with tool_call/tool_result synthesis, audit
logging, circuit-breaker reporting, and terminal frame emission.

Each runner becomes an ``async with RunPipeline(...)`` block that supplies only
the app-specific delta (trigger construction, result extraction, post-stream
hooks). See the grilling design doc for the full rationale (A1 + C1 + D3).

Deletion test: removing this module would force every runner to re-implement
~200 lines of scaffolding. The module earns its keep.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
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
from apps.agent.services.orchestrator import _select_stream_run_provider
from apps.agent.services.pii_redactor import pii_redactor

from .gc import schedule_run_cleanup

logger = logging.getLogger(__name__)


class RunPipeline:
    """Async context manager that wraps the scaffolding of a stream_run runner.

    Usage::

        async with RunPipeline(
            app_name="finance-coach",
            family_id=family_id,
            user_id=user_id,
            thread_id=thread_id,
            record=record,
            bridge=bridge,
            run_manager=run_manager,
        ) as p:
            trigger = _extract_finance_coach_snapshot(graph_input) or _SYNTHETIC_TRIGGER
            await p.run_skill(trigger)
            # optional: extract result from p.ai_response_parts

    ``__aenter__`` does: set_status(running) + publish metadata, fetch AI config,
    select provider, resolve MCP servers, create adapter, set active skill.

    ``__aexit__`` does: reset active skill, set terminal status, audit log,
    publish end frame + deferred cleanup.  ALL terminal paths (success, error,
    cancellation) go through the same cleanup sequence — matching DeerFlow's
    unified finally pattern in ``run_agent()``.  If ``set_error()`` was called
    inside the ``async with`` body, the error frame is published before the
    end frame.

    ``run_skill(user_message)`` does: PII redact, typed_stream_dispatch loop,
    collect ai_response_parts + cumulative_usage, forward frames to bridge.

    Design notes (vs DeerFlow reference):
    - **No lease admission**: DeerFlow's ``run_agent`` uses try_start/ownership
      tokens for multi-worker lease management.  RunPipeline runs inside a
      single worker process with RunManager already gating concurrency, so the
      lease layer is unnecessary here.
    - **No checkpoint rollback**: DeerFlow persists rollbacks on failure for
      resume support.  Numina's runs are idempotent single-pass pipelines; the
      checkpointer retains the last state but resume is not implemented.
    - **skill_name vs app_name**: ``app_name`` drives config/audit/end-frame
      metadata; ``skill_name`` is what ``typed_stream_dispatch`` uses for tool
      filtering via the active-skill ContextVar.  They default to the same
      value but can differ when the dispatch skill doesn't match the app label.
    - **BackendClient + mcp_servers override**: Each pipeline creates its own
      ``BackendClient(family_id=...)`` for tenant-isolated config fetch.  The
      ``mcp_servers`` parameter overrides MCP resolution — pass ``[]`` to skip
      MCP entirely (e.g. dashboard-narrative has no tools), or ``None`` (default)
      to resolve via the standard ``_resolve_numina_mcp_servers`` path.
    """

    def __init__(
        self,
        *,
        app_name: str,
        family_id: str,
        user_id: str | None,
        thread_id: str,
        record: RunRecord,
        bridge: StreamBridge,
        run_manager: RunManager,
        # Adapter knobs (per-app delta)
        plan_mode: bool = False,
        subagent_enabled: bool = False,
        memory_enabled: bool = True,
        enable_thinking: bool = False,
        timeout_seconds: int = 120,
        # Optional: override the skill_name passed to typed_stream_dispatch
        # (defaults to app_name).  Accepts a callable that receives the fetched
        # ai_config dict and returns the resolved skill name — used by the chat
        # runner to pick chat vs chat-search based on web-search capability.
        skill_name: str | Callable[[dict], str] | None = None,
        # Optional: override MCP server resolution. Pass [] to skip MCP entirely
        # (dashboard-narrative has allowed-tools: []). Default None = resolve.
        mcp_servers: list[dict[str, Any]] | None = None,
        # Optional: custom skills whitelist passed to create_family_adapter.
        # When None, no available_skills parameter is forwarded (adapter default).
        available_skills: set[str] | None = None,
        # Optional: skip auto-setting the active skill in __aenter__.  Used by
        # the chat runner for slash-activated messages where DeerFlow's
        # SkillActivationMiddleware handles skill selection instead.
        skip_active_skill: bool = False,
    ) -> None:
        self.app_name = app_name
        self.family_id = family_id
        self.user_id = user_id
        self.thread_id = thread_id
        self.record = record
        self.bridge = bridge
        self.run_manager = run_manager
        self.plan_mode = plan_mode
        self.subagent_enabled = subagent_enabled
        self.memory_enabled = memory_enabled
        self.enable_thinking = enable_thinking
        self.timeout_seconds = timeout_seconds
        self._skill_name_spec: str | Callable[[dict], str] | None = skill_name
        self.skill_name: str = (
            skill_name if isinstance(skill_name, str) else app_name
        )
        self._mcp_servers_override = mcp_servers
        self._available_skills = available_skills
        self._skip_active_skill = skip_active_skill

        # Populated by __aenter__
        self.run_id: str = record.run_id
        self.selected_provider: dict | None = None
        self.adapter: Any = None
        self._skill_token: Any = None
        self._t_start: float = 0.0

        # Populated by run_skill / set_error
        self.ai_response_parts: list[str] = []
        self.thinking_parts: list[str] = []
        self.cumulative_usage: dict[str, int] | None = None
        self.captured_tool_calls: list[dict[str, Any]] = []
        self._completion_status: str = "error"
        self._success: bool = False
        self._error_type: str | None = None
        self._post_stream_error_message: str | None = None

    async def __aenter__(self) -> RunPipeline:
        self._t_start = time.monotonic()

        # 1. Mark running + publish metadata (DeerFlow pattern)
        await self.run_manager.set_status(self.run_id, RunStatus.running)
        await self.bridge.publish(
            self.run_id,
            "metadata",
            {"run_id": self.run_id, "thread_id": self.thread_id},
        )

        # 2. Fetch per-family AI config (tenant-isolated)
        client = BackendClient(family_id=self.family_id)
        ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        self.selected_provider = _select_stream_run_provider(providers)
        if self.selected_provider is None:
            raise RuntimeError("无可用 AI 供应商（所有 provider 均已熔断）")

        # 2b. Resolve callable skill_name (e.g. chat runner picks chat vs
        #     chat-search based on web-search capability in ai_config).
        if callable(self._skill_name_spec):
            self.skill_name = self._skill_name_spec(ai_config)

        # 3. Fetch enabled MCP servers (or use override)
        if self._mcp_servers_override is not None:
            mcp_servers = self._mcp_servers_override
        else:
            mcp_servers = await _resolve_numina_mcp_servers(
                client, self.family_id, self.user_id, f"[{self.app_name}]"
            )

        # 3b. Fail-fast: verify all tenant ContextVars are set before the
        # adapter is created. Without this, a missing ContextVar (e.g.
        # numina_extensions_config_path) would only surface later in the
        # executor thread where the error message is hard to diagnose.
        from apps.agent.services.runtime.sandbox_provider import (
            assert_mcp_context_complete,
        )

        assert_mcp_context_complete(f"RunPipeline[{self.app_name}].__aenter__")

        # 4. Resolve memory_enabled from AgentRegistry (when caller didn't override)
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get(self.app_name, self.family_id)
        if agent_meta and "memory_enabled" in agent_meta:
            self.memory_enabled = bool(agent_meta["memory_enabled"])

        # 5. Build adapter
        adapter_kwargs: dict[str, Any] = dict(
            timeout_seconds=self.timeout_seconds,
            subagent_enabled=self.subagent_enabled,
            plan_mode=self.plan_mode,
            mcp_servers=mcp_servers,
            agent_name=self.app_name,
            memory_enabled=self.memory_enabled,
        )
        if self._available_skills is not None:
            adapter_kwargs["available_skills"] = self._available_skills
        self.adapter = create_family_adapter(
            self.family_id,
            self.selected_provider,
            **adapter_kwargs,
        )

        # 6. Set active skill (so sync_tool_patch filters tools correctly).
        #    Skip when the caller manages skill activation externally — e.g.
        #    the chat runner for slash-activated messages where DeerFlow's
        #    SkillActivationMiddleware handles selection.
        if not self._skip_active_skill:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                set_active_skill,
            )

            self._skill_token = set_active_skill(self.skill_name)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        _exc_tb: Any,
    ) -> None:
        # 1. Reset active skill (prevent ContextVar leak)
        if self._skill_token is not None:
            from apps.agent.services.deerflow_adapter.active_skill_context import (
                reset_active_skill,
            )

            reset_active_skill(self._skill_token)

        # 2. Handle exception — set terminal state but do NOT return early.
        #    All paths (success/error/cancellation) share the cleanup below.
        if exc_type is not None:
            if exc_type is asyncio.CancelledError:
                self._error_type = "Cancelled"
                self._completion_status = "interrupted"
                await self.run_manager.set_status(self.run_id, RunStatus.interrupted)
            else:
                self._error_type = exc_type.__name__
                self._completion_status = "error"
                logger.warning(
                    "[%s] failed run=%s err=%s",
                    self.app_name,
                    self.run_id,
                    self._error_type,
                )
                await self.run_manager.set_status(
                    self.run_id, RunStatus.error, error=str(exc_val)
                )
                # Circuit-breaker reporting (fire-and-forget)
                if exc_val is not None:
                    _fire_and_forget_circuit_report(
                        self.family_id, self.selected_provider, exc_val
                    )
                await self.bridge.publish(
                    self.run_id,
                    "error",
                    {"message": str(exc_val), "name": self._error_type},
                )
                # Don't re-raise — we've published the error frame

        # 3. Success path: set terminal status (only if no exception and no set_error)
        elif self._post_stream_error_message is not None:
            # set_error() was called — publish the error frame now.
            await self.run_manager.set_status(
                self.run_id,
                RunStatus.error,
                error=self._post_stream_error_message,
            )
            await self.bridge.publish(
                self.run_id,
                "error",
                {
                    "message": self._post_stream_error_message,
                    "name": self._error_type,
                },
            )
        else:
            await self.run_manager.set_status(self.run_id, RunStatus.success)
            self._completion_status = "complete"
            self._success = self.record.status == RunStatus.success

        # 4. Audit log (Key Invariant #3) — runs for ALL terminal paths
        audit_logger.log_call(
            AuditEntry(
                family_id=self.family_id,
                audit_id=self.run_id,
                user_id=self.user_id or "",
                skill_id=self.app_name,
                success=self._success,
                error_type=self._error_type,
                deerflow_attempted=True,
                duration_ms=int((time.monotonic() - self._t_start) * 1000),
            )
        )

        # 5. Terminal end frame + sentinel + deferred cleanup (DeerFlow pattern)
        end_payload: dict[str, Any] = {"status": self._completion_status}
        if self.cumulative_usage:
            end_payload["usage"] = self.cumulative_usage
        await self.bridge.publish(self.run_id, "end", end_payload)
        await self.bridge.publish_end(self.run_id)
        asyncio.create_task(self.bridge.cleanup(self.run_id, delay=60))
        asyncio.create_task(
            schedule_run_cleanup(self.run_manager, self.run_id, delay=300)
        )

    async def run_skill(
        self,
        user_message: str,
        *,
        enable_reasoning_delta: bool = False,
        enable_thinking: bool | None = None,
    ) -> None:
        """Run the skill via typed_stream_dispatch and forward frames to bridge.

        Collects ``ai_response_parts``, ``thinking_parts`` (when reasoning_delta
        is enabled), ``cumulative_usage``, and ``captured_tool_calls`` for the
        caller to read after this method returns. Synthesizes tool_call/tool_result
        custom events so the frontend can reuse the chat renderer (unless
        reasoning_delta mode is active, which uses a different message path).

        ``enable_thinking`` overrides the pipeline-level setting for this turn
        only (used by the chat runner where the frontend controls thinking
        per-call via ``config.configurable.thinking_enabled``).
        """
        effective_thinking = (
            enable_thinking if enable_thinking is not None else self.enable_thinking
        )
        # PII redaction (Key Invariant #1) — defense-in-depth
        context = FamilyContext(family_id=self.family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # Stream via typed_stream_dispatch → publish to bridge
        async for sse_type, data in self.adapter.typed_stream_dispatch(
            skill_name=self.skill_name,
            context=redacted,
            thread_id=self.thread_id,
            enable_thinking=effective_thinking,
        ):
            if self.record.abort_event.is_set():
                break

            if sse_type == "end":
                if isinstance(data, dict) and data.get("usage"):
                    raw_usage = data["usage"]
                    self.cumulative_usage = {
                        "input_tokens": raw_usage.get("input_tokens", 0),
                        "output_tokens": raw_usage.get("output_tokens", 0),
                        "total_tokens": raw_usage.get("total_tokens", 0),
                    }
                break
            if sse_type == "error":
                await self.bridge.publish(self.run_id, "error", data)
                break

            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    # Reasoning-delta path (dashboard-narrative, literacy-report):
                    # extract reasoning_content, publish as reasoning_delta custom
                    # event, forward content-only message (strip reasoning to
                    # avoid duplication).
                    if enable_reasoning_delta:
                        additional_kwargs = data.get("additional_kwargs") or {}
                        reasoning = additional_kwargs.get("reasoning_content")
                        if isinstance(reasoning, str) and reasoning:
                            self.thinking_parts.append(reasoning)
                            await self.bridge.publish(
                                self.run_id,
                                "custom",
                                {"type": "reasoning_delta", "content": reasoning},
                            )
                        content = data.get("content")
                        if content:
                            self.ai_response_parts.append(content)
                            await self.bridge.publish(
                                self.run_id,
                                "messages",
                                {"type": "ai", "content": content},
                            )
                        # Defensive: capture tool_calls even in reasoning_delta
                        # mode (current callers don't use tools, but if they
                        # ever do the standard path would handle them).
                        tool_calls = data.get("tool_calls")
                        if tool_calls:
                            for tc in extract_tool_calls(data):
                                raw_name = tc.get("name", "")
                                tc_args = tc.get("args") or {}
                                self.captured_tool_calls.append(
                                    {"name": raw_name, "args": tc_args}
                                )
                        continue

                    # Standard path (asset-report, finance-coach, etc.):
                    # forward the full message + synthesize tool_call/tool_result.
                    await self.bridge.publish(self.run_id, sse_type, data)
                    content = data.get("content")
                    if content:
                        self.ai_response_parts.append(content)
                    tool_calls = data.get("tool_calls")
                    if tool_calls:
                        for tc in extract_tool_calls(data):
                            raw_name = tc.get("name", "")
                            tc_args = tc.get("args") or {}
                            self.captured_tool_calls.append(
                                {"name": raw_name, "args": tc_args}
                            )
                            tool_type, display_name, icon, display_key = (
                                resolve_tool_metadata(raw_name)
                            )
                            payload: dict[str, Any] = {
                                "type": "tool_call",
                                "tool_call_id": tc.get("id", ""),
                                "tool_name": raw_name,
                                "args": tc_args,
                                "display_name": display_name,
                                "icon": icon,
                                "tool_type": tool_type,
                            }
                            if display_key:
                                payload["display_key"] = display_key
                            await self.bridge.publish(self.run_id, "custom", payload)
                elif msg_type == "tool":
                    await self.bridge.publish(self.run_id, sse_type, data)
                    tool_call_id = str(data.get("tool_call_id") or "")
                    tool_name = data.get("name") or ""
                    content = data.get("content")
                    if tool_call_id:
                        await self.bridge.publish(
                            self.run_id,
                            "custom",
                            {
                                "type": "tool_result",
                                "tool_call_id": tool_call_id,
                                "tool_name": tool_name,
                                "content": content,
                            },
                        )
                else:
                    await self.bridge.publish(self.run_id, sse_type, data)
            else:
                # Forward non-messages frames (values, custom, etc.)
                await self.bridge.publish(self.run_id, sse_type, data)

    def set_error(self, message: str, *, error_type: str | None = None) -> None:
        """Downgrade the run to error *after* the stream completed normally.

        Used by asset-report when post-stream persistence fails: the step2_json
        custom event already shipped (frontend shows step 2 finish), but the
        run must not look complete when the backend has no row.

        This is a **state-only** method: it records the error flags and the
        message.  ``__aexit__`` reads the flags and publishes the error frame
        + run status before the end frame, so there is no race between
        fire-and-forget tasks and the cleanup sequence.
        """
        self._error_type = error_type or "PostStreamError"
        self._completion_status = "error"
        self._success = False
        self._post_stream_error_message = message

    @property
    def completion_status(self) -> str:
        """Return the terminal status: 'error', 'interrupted', or 'complete'."""
        return self._completion_status

    @property
    def ai_text(self) -> str:
        """Concatenate all collected AI response parts."""
        return "".join(self.ai_response_parts)

    @property
    def thinking_text(self) -> str:
        """Concatenate all collected reasoning/thinking parts."""
        return "".join(self.thinking_parts).strip()

    @property
    def captured_write_file_paths(self) -> list[str]:
        """Extract write_file paths from captured tool calls (asset-report)."""
        paths: list[str] = []
        for tc in self.captured_tool_calls:
            if tc.get("name") == "write_file":
                wf_path = (tc.get("args") or {}).get("path")
                if isinstance(wf_path, str) and wf_path:
                    paths.append(wf_path)
        return paths


# ---------------------------------------------------------------------------
# Helpers (moved from worker.py)
# ---------------------------------------------------------------------------


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
    ``label`` is the calling pipeline's log tag (e.g. ``[finance-coach]``).
    """
    from apps.agent.app.config import settings

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
                from packages.security.service_auth.agent_jwt import create_agent_token

                mcp_headers: dict[str, str] = {
                    "X-Agent-Token": create_agent_token(family_id),
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


# Track fire-and-forget background tasks so they don't get garbage collected
_background_tasks: set[asyncio.Task] = set()


def _track_task(task: asyncio.Task) -> None:
    """Track a background task and auto-remove it when done."""
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _background_tasks.discard(t))


async def _report_circuit_on_failure(
    family_id: str,
    selected_provider: dict | None,
    exc: BaseException,
) -> None:
    """Classify the exception and report a circuit event to the backend."""
    if selected_provider is None:
        return
    config_id = selected_provider.get("config_id")
    if not config_id:
        return
    try:
        from apps.agent.core.backend_client import (
            BackendClient,
            _extract_llm_error_info,
            classify_error_type,
        )

        error_code, error_message = _extract_llm_error_info(exc)
        error_type = classify_error_type(error_code, error_message)
        client = BackendClient(family_id=family_id)
        await client.report_circuit_event(
            config_id=config_id,
            error_code=error_code,
            error_type=error_type,
            error_message=error_message[:500],
        )
    except Exception as report_exc:
        logger.warning(
            "[run_pipeline] report_circuit_event failed family=%s config_id=%s err=%s",
            family_id,
            config_id,
            type(report_exc).__name__,
        )


def _fire_and_forget_circuit_report(
    family_id: str,
    selected_provider: dict | None,
    exc: BaseException,
) -> None:
    """Schedule a circuit report in the background (fire-and-forget)."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(
        _report_circuit_on_failure(family_id, selected_provider, exc)
    )
    _track_task(task)
