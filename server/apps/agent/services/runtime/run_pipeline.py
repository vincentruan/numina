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

    ``__aexit__`` does: reset active skill, audit log, circuit report on error,
    publish end frame + deferred cleanup.

    ``run_skill(user_message)`` does: PII redact, typed_stream_dispatch loop,
    collect ai_response_parts + cumulative_usage, forward frames to bridge.
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
        # (defaults to app_name)
        skill_name: str | None = None,
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
        self.skill_name = skill_name or app_name

        # Populated by __aenter__
        self.run_id: str = record.run_id
        self.selected_provider: dict | None = None
        self.adapter: Any = None
        self._skill_token: Any = None
        self._t_start: float = 0.0

        # Populated by run_skill
        self.ai_response_parts: list[str] = []
        self.cumulative_usage: dict[str, int] | None = None
        self._completion_status: str = "error"
        self._success: bool = False
        self._error_type: str | None = None

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

        # 3. Fetch enabled MCP servers
        mcp_servers = await _resolve_numina_mcp_servers(
            client, self.family_id, self.user_id, f"[{self.app_name}]"
        )

        # 4. Resolve memory_enabled from AgentRegistry (when caller didn't override)
        from apps.agent.services.agent_registry import get_agent_registry

        agent_meta = await get_agent_registry().get(self.app_name, self.family_id)
        if agent_meta and "memory_enabled" in agent_meta:
            self.memory_enabled = bool(agent_meta["memory_enabled"])

        # 5. Build adapter
        self.adapter = create_family_adapter(
            self.family_id,
            self.selected_provider,
            timeout_seconds=self.timeout_seconds,
            subagent_enabled=self.subagent_enabled,
            plan_mode=self.plan_mode,
            mcp_servers=mcp_servers,
            agent_name=self.app_name,
            memory_enabled=self.memory_enabled,
        )

        # 6. Set active skill (so sync_tool_patch filters tools correctly)
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

        # 2. Handle exception
        if exc_type is not None:
            if exc_type is asyncio.CancelledError:
                self._error_type = "Cancelled"
                await self.run_manager.set_status(self.run_id, RunStatus.interrupted)
                self._completion_status = "interrupted"
                # Re-raise CancelledError (don't swallow)
                return
            self._error_type = exc_type.__name__
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
            self._completion_status = "error"
            # Don't re-raise — we've published the error frame
            return

        # 3. Success path: set terminal status
        await self.run_manager.set_status(self.run_id, RunStatus.success)
        self._completion_status = "complete"
        self._success = self.record.status == RunStatus.success

        # 4. Audit log (Key Invariant #3)
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

    async def run_skill(self, user_message: str) -> None:
        """Run the skill via typed_stream_dispatch and forward frames to bridge.

        Collects ``ai_response_parts`` and ``cumulative_usage`` for the caller
        to read after this method returns. Synthesizes tool_call/tool_result
        custom events so the frontend can reuse the chat renderer.
        """
        # PII redaction (Key Invariant #1) — defense-in-depth
        context = FamilyContext(family_id=self.family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        # Stream via typed_stream_dispatch → publish to bridge
        async for sse_type, data in self.adapter.typed_stream_dispatch(
            skill_name=self.skill_name,
            context=redacted,
            thread_id=self.thread_id,
            enable_thinking=self.enable_thinking,
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

            # Forward the canonical frame (messages / values / custom)
            await self.bridge.publish(self.run_id, sse_type, data)

            # Collect AI text + synthesize tool_call/tool_result custom events
            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    content = data.get("content")
                    if content:
                        self.ai_response_parts.append(content)
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
                            await self.bridge.publish(self.run_id, "custom", payload)
                elif msg_type == "tool":
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

    @property
    def completion_status(self) -> str:
        """Return the terminal status: 'error', 'interrupted', or 'complete'."""
        return self._completion_status

    @property
    def ai_text(self) -> str:
        """Concatenate all collected AI response parts."""
        return "".join(self.ai_response_parts)


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
