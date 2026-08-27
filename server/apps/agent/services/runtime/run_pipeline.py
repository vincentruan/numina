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

from apps.agent.core.backend_client import (
    BackendClient,
    _extract_llm_error_info,
    classify_error_type,
)
from apps.agent.schemas.context import FamilyContext, RedactedContext
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


# ── Agent soul sync (DeerFlow SOUL.md bridge) ────────────────────────────────
#
# DeerFlow natively loads SOUL.md from {base_dir}/users/{user_id}/agents/{name}/
# and injects it as <soul>...</soul> in the system prompt.  Numina stores
# soul_md in the DB (ai_agents table) but historically never wrote it to the
# filesystem path DeerFlow expects — the value was dead code end-to-end.
#
# _sync_agent_soul() bridges this gap: it writes the DB value to DeerFlow's
# expected path so load_agent_soul() picks it up on the next run.
# Following DeerFlow reference: agents_config.py:load_agent_soul() +
# lead_agent/prompt.py:get_agent_soul() (HTML-escape + <soul> wrapping).


def _sync_agent_soul(agent_name: str, soul_md: str) -> None:
    """Write agent soul to the filesystem path DeerFlow expects.

    DeerFlow's ``load_agent_soul(agent_name, user_id=family_id)`` reads from
    ``{base_dir}/users/{family_id}/agents/{agent_name}/SOUL.md``.  The
    ``family_id`` comes from ``get_effective_user_id()`` which reads the
    ``set_current_user()`` ContextVar — already set by ``worker.run_agent``
    before ``typed_stream_dispatch()`` is called.

    This function is idempotent: skips the write when the file already contains
    the same content (avoids unnecessary disk I/O on every chat turn).
    """
    try:
        from deerflow.config.paths import get_paths

        from apps.agent.services.runtime.sandbox_provider import (
            get_family_sandbox_context,
        )

        family_id = get_family_sandbox_context()
        if not family_id:
            logger.debug("[run_pipeline] agent soul sync skipped: no sandbox family_id")
            return
        agent_dir = get_paths().user_agent_dir(str(family_id), agent_name)
        soul_path = agent_dir / "SOUL.md"
        # Skip if already present with same content (avoid per-turn disk I/O).
        if soul_path.exists():
            try:
                if soul_path.read_text(encoding="utf-8") == soul_md:
                    return
            except OSError:
                pass  # Read failed — rewrite below.
        soul_path.parent.mkdir(parents=True, exist_ok=True)
        soul_path.write_text(soul_md, encoding="utf-8")
        logger.info(
            "[run_pipeline] agent soul synced: agent=%s path=%s (%d chars)",
            agent_name,
            soul_path,
            len(soul_md),
        )
    except Exception:
        # Non-fatal: if DeerFlow's paths API is unavailable or the write fails,
        # the run continues without a soul (DeerFlow's load_agent_soul returns
        # None, and the system prompt simply lacks the <soul> block).
        logger.debug(
            "[run_pipeline] agent soul sync skipped (non-fatal): agent=%s",
            agent_name,
            exc_info=True,
        )


# ── Security middlewares ─────────────────────────────────────────────────────
#
# DeerFlow natively provides both security middlewares we need:
# - InputSanitizationMiddleware (via _build_runtime_middlewares)
# - TokenBudgetMiddleware (via build_middlewares when token_budget.enabled=True)
#
# We inject token_budget config via _inject_token_budget() in
# family_adapter_cache.py. No custom middlewares needed.


def _is_fallback_eligible(error_type: str) -> bool:
    """Decide whether an error warrants switching to a different provider.

    Includes both transient errors (server down, rate limit, timeout) and
    provider-specific permanent errors (quota, auth) — because a different
    provider may not share the same issue.  Pure client errors (bad request,
    validation failure) are excluded since switching providers won't help.
    """
    # Transient: rate-limit, server error, timeout, network
    if error_type.startswith("transient_"):
        return True
    # Provider-specific permanent: quota/billing, auth (invalid key), account
    # These may be provider-specific — another provider likely has a different
    # key/subscription, so switching is worthwhile.
    if error_type in ("permanent_account", "permanent_auth"):
        return True
    # DeerFlow-specific exceptions that propagate as generic error names
    return error_type in (
        "DeerFlowTimeoutError",
        "ConnectionError",
        "TimeoutError",
    )


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
        # Optional: DeerFlow AgentMiddleware list to mount on the adapter.
        # Created once by the caller and reused across fallback attempts so
        # the family_adapter_cache key (which includes ``tuple(id(m) for m
        # in middlewares)``) stays stable.  Pass ``None`` (default) for no
        # middleware — used by fixed-flow runners (asset-report, etc.).
        middlewares: list[Any] | None = None,
        # Optional: pre-fetched AI config dict.  When provided, __aenter__
        # skips the ``get_family_ai_config()`` HTTP call (the chat runner
        # already fetches config before constructing the pipeline to resolve
        # web-search capability and custom skills — accepting it here avoids
        # a redundant round-trip).
        preloaded_ai_config: dict[str, Any] | None = None,
        # Optional: checkpoint ID to fork from (retry checkpoint forking).
        # When set, the adapter passes it to DeerFlowClient.stream so the
        # checkpointer loads state from that checkpoint instead of the head.
        # This skips the failed user message that the head retains after a
        # failed first turn.  Pass None (default) for normal head-based runs.
        checkpoint_id: str | None = None,
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
        self.skill_name: str = skill_name if isinstance(skill_name, str) else app_name
        self._mcp_servers_override = mcp_servers
        self._available_skills = available_skills
        self._middlewares = middlewares
        self._preloaded_ai_config = preloaded_ai_config
        self.checkpoint_id = checkpoint_id

        # Populated by __aenter__
        self._providers: list[dict[str, Any]] = []
        self._adapter_kwargs: dict[str, Any] = {}
        self._circuit_reported_during_fallback = False
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
        #    Skip the HTTP call when the caller already fetched it.
        client = BackendClient(family_id=self.family_id)
        if self._preloaded_ai_config is not None:
            ai_config = self._preloaded_ai_config
        else:
            ai_config = await client.get_family_ai_config()
        providers = ai_config.get("providers", [])
        if not providers:
            raise RuntimeError("未配置 AI 供应商")
        self.selected_provider = _select_stream_run_provider(providers)
        if self.selected_provider is None:
            raise RuntimeError("无可用 AI 供应商（所有 provider 均已熔断）")
        # Store full provider list for transparent fallback in run_skill().
        self._providers = providers

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

        # 4b. Sync agent soul to DeerFlow's expected filesystem path.
        # DeerFlow's load_agent_soul() reads SOUL.md from
        # {DEER_FLOW_HOME}/users/{family_id}/agents/{agent_name}/SOUL.md
        # and injects it as <soul>...</soul> in the system prompt.
        # Numina stores soul_md in the DB (ai_agents table) but never wrote
        # it to disk — so DeerFlow's native soul mechanism was dead code.
        # Fix: write the DB value to the path DeerFlow expects before the
        # adapter's first stream call (which triggers apply_prompt_template).
        if agent_meta and agent_meta.get("soul_md"):
            _sync_agent_soul(self.app_name, agent_meta["soul_md"])

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
        if self._middlewares:
            adapter_kwargs["middlewares"] = self._middlewares
        # Store for fallback (run_skill re-creates adapter with new provider)
        self._adapter_kwargs = adapter_kwargs
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
                # Circuit-breaker reporting (fire-and-forget).
                # Skip if run_skill() fallback already reported for this
                # exception (avoids double-reporting on final exhausted retry).
                if exc_val is not None and not self._circuit_reported_during_fallback:
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
        # Buffer lifecycle is the backend's responsibility (Phase 1 refactor).
        # The agent no longer calls bridge.cleanup() — the backend-owned buffer
        # manages TTL based on AITask lifecycle, not a fixed 60s delay.
        # Previously: _track_task(asyncio.create_task(self.bridge.cleanup(self.run_id, delay=60)))
        _track_task(
            asyncio.create_task(
                schedule_run_cleanup(self.run_manager, self.run_id, delay=300)
            )
        )

    def set_skill_token(self, skill_name: str | None = None) -> None:
        """Set the active skill token for this pipeline.

        Public alternative to mutating ``_skill_token`` directly.  Used by
        the chat runner for slash-activated messages where
        ``skip_active_skill=True`` was passed to the constructor but the
        caller still needs to activate a skill after ``__aenter__``.

        The token is tracked so ``__aexit__`` resets it correctly.
        """
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            set_active_skill,
        )

        self._skill_token = set_active_skill(skill_name or self.skill_name)

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

        **Transparent provider fallback**: when the selected provider fails with
        a transient or quota error and no AI content has been sent yet, the
        method switches to the next available provider and retries.  Circuit
        events are reported for each failed attempt so the backend can open
        breakers proactively.
        """
        effective_thinking = (
            enable_thinking if enable_thinking is not None else self.enable_thinking
        )
        # PII redaction (Key Invariant #1) — defense-in-depth
        context = FamilyContext(family_id=self.family_id, free_text=user_message)
        redacted = pii_redactor.redact(context)

        candidates = self._fallback_candidates()

        for idx, provider in enumerate(candidates):
            # Swap provider + adapter for this attempt (first iteration keeps
            # the adapter created in __aenter__).
            if idx > 0:
                self.selected_provider = provider
                self.adapter = create_family_adapter(
                    self.family_id,
                    provider,
                    **self._adapter_kwargs,
                )
                logger.info(
                    "[%s] run=%s falling back to provider config_id=%s (attempt %d)",
                    self.app_name,
                    self.run_id,
                    provider.get("config_id"),
                    idx + 1,
                )
                # Publish a custom event so the frontend can show a notice
                await self.bridge.publish(
                    self.run_id,
                    "custom",
                    {
                        "type": "provider_fallback",
                        "attempt": idx + 1,
                    },
                )

            try:
                await self._dispatch_once(
                    redacted, effective_thinking, enable_reasoning_delta
                )
                return  # success
            except Exception as exc:
                # Report circuit event for this failed provider attempt
                try:
                    await _report_circuit_on_failure(self.family_id, provider, exc)
                    self._circuit_reported_during_fallback = True
                except Exception as report_exc:
                    logger.warning(
                        "[run_pipeline] circuit report failed config_id=%s err=%s",
                        provider.get("config_id"),
                        type(report_exc).__name__,
                    )

                # Only fall back if no AI content has been sent yet — once
                # content frames are on the wire, a retry would produce
                # duplicate / inconsistent output.
                if self.ai_response_parts:
                    logger.warning(
                        "[%s] run=%s provider failed after partial content, "
                        "cannot fall back: %s",
                        self.app_name,
                        self.run_id,
                        exc,
                    )
                    raise

                if idx >= len(candidates) - 1:
                    # Last candidate — let the exception propagate to __aexit__
                    logger.warning(
                        "[%s] run=%s all %d providers exhausted: %s",
                        self.app_name,
                        self.run_id,
                        len(candidates),
                        exc,
                    )
                    raise

                # Classify the error to decide if fallback is appropriate
                error_code, error_message = _extract_llm_error_info(exc)
                error_type = classify_error_type(error_code, error_message)
                if not _is_fallback_eligible(error_type):
                    logger.info(
                        "[%s] run=%s non-retryable error (%s), not falling back",
                        self.app_name,
                        self.run_id,
                        error_type,
                    )
                    raise

                logger.info(
                    "[%s] run=%s transient error on provider config_id=%s (%s), "
                    "trying next provider",
                    self.app_name,
                    self.run_id,
                    provider.get("config_id"),
                    error_type,
                )
                # Reset collected state before retry
                self.ai_response_parts.clear()
                self.thinking_parts.clear()
                self.captured_tool_calls.clear()
                self.cumulative_usage = None

    async def _dispatch_once(
        self,
        redacted: RedactedContext,
        enable_thinking: bool,
        enable_reasoning_delta: bool,
    ) -> None:
        """Run a single dispatch attempt and forward frames to bridge.

        Raises on adapter errors so the caller (run_skill) can decide whether
        to retry with a different provider.
        """
        # Stream via typed_stream_dispatch → publish to bridge
        async for sse_type, data in self.adapter.typed_stream_dispatch(
            skill_name=self.skill_name,
            context=redacted,
            thread_id=self.thread_id,
            enable_thinking=enable_thinking,
            checkpoint_id=self.checkpoint_id,
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
                # If the error arrives before any AI content, it may be
                # retriable (e.g. quota, server error).  Raise a synthetic
                # exception so run_skill()'s fallback loop can catch it and
                # try the next provider.  When content has already been sent,
                # we cannot retry — the error is terminal for this turn.
                if not self.ai_response_parts:
                    error_msg = (
                        data.get("message") if isinstance(data, dict) else str(data)
                    )
                    raise RuntimeError(f"Stream error (pre-content): {error_msg}")
                break

            if sse_type == "messages" and isinstance(data, dict):
                msg_type = data.get("type")
                if msg_type == "ai":
                    # DeerFlow error-fallback detection (P0 fix):
                    # When LLMErrorHandlingMiddleware exhausts retries, it returns
                    # a graceful AIMessage with ``deerflow_error_fallback=True``
                    # instead of raising.  Numina's provider-fallback loop in
                    # ``run_skill`` only triggers on exceptions, so we must
                    # detect this signal and raise to activate multi-provider
                    # failover.
                    additional_kwargs = data.get("additional_kwargs") or {}
                    if additional_kwargs.get("deerflow_error_fallback"):
                        error_reason = additional_kwargs.get(
                            "error_reason", "unknown"
                        )
                        error_detail = additional_kwargs.get(
                            "error_detail", ""
                        )
                        logger.warning(
                            "[%s] run=%s DeerFlow error fallback detected: "
                            "reason=%s detail=%s",
                            self.app_name,
                            self.run_id,
                            error_reason,
                            error_detail[:200],
                        )
                        if not self.ai_response_parts:
                            # No content produced yet — raise to trigger
                            # provider fallback in ``run_skill``.
                            raise RuntimeError(
                                f"DeerFlow provider fallback ({error_reason}): "
                                f"{error_detail}"
                            )
                        # Content already streamed — cannot retry.
                        # Mark as error so the lifecycle consumer fails the task.
                        self.set_error(
                            error_detail or f"AI provider failed: {error_reason}",
                            error_type="DeerFlowFallback",
                        )
                        break

                    # Reasoning-delta path (dashboard-narrative, literacy-report):
                    # extract reasoning_content, publish as reasoning_delta custom
                    # event, forward content-only message (strip reasoning to
                    # avoid duplication).
                    #
                    # Supports two formats:
                    # 1. Claude non-streaming: additional_kwargs.reasoning_content
                    # 2. Anthropic streaming: content is a list of blocks where
                    #    {"type": "thinking", "thinking": "..."} carries thinking
                    #    and {"type": "text", "text": "..."} carries the response.
                    if enable_reasoning_delta:
                        reasoning = additional_kwargs.get("reasoning_content")
                        content = data.get("content")

                        # Anthropic streaming: content is a list of blocks
                        if isinstance(content, list):
                            text_parts: list[str] = []
                            for block in content:
                                if isinstance(block, dict):
                                    if block.get("type") == "thinking" and block.get("thinking"):
                                        thinking_block = block["thinking"]
                                        self.thinking_parts.append(thinking_block)
                                        await self.bridge.publish(
                                            self.run_id,
                                            "custom",
                                            {"type": "reasoning_delta", "content": thinking_block},
                                        )
                                    elif block.get("type") == "text" and block.get("text"):
                                        text_parts.append(block["text"])
                            content = "".join(text_parts) if text_parts else None
                        elif not reasoning and isinstance(content, str):
                            # Fallback: check for <think> tags in plain string content
                            # (some providers wrap thinking in XML tags)
                            import re
                            think_match = re.search(r"<think>\s*(.*?)\s*</think>", content, re.DOTALL | re.IGNORECASE)
                            if think_match:
                                reasoning = think_match.group(1)
                                content = re.sub(r"<think>\s*.*?\s*</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()

                        if isinstance(reasoning, str) and reasoning:
                            self.thinking_parts.append(reasoning)
                            await self.bridge.publish(
                                self.run_id,
                                "custom",
                                {"type": "reasoning_delta", "content": reasoning},
                            )
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

    def _fallback_candidates(self) -> list[dict[str, Any]]:
        """Build ordered fallback candidates from the stored provider list.

        Excludes the currently-selected provider (returned first) and providers
        with circuit_state == 'open'.  The remaining candidates preserve their
        display_order so the next provider in line is tried next.
        """
        if not self._providers or len(self._providers) <= 1:
            return [self.selected_provider] if self.selected_provider else []

        current_id = (
            self.selected_provider.get("config_id") if self.selected_provider else None
        )
        candidates: list[dict[str, Any]] = []
        for p in self._providers:
            if p.get("circuit_state") == "open":
                continue
            if p.get("config_id") == current_id:
                continue
            candidates.append(p)

        if not self.selected_provider:
            return candidates
        return [self.selected_provider] + candidates

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
        from packages.security.service_auth.agent_jwt import create_agent_token

        expected_prefix = settings.BACKEND_BASE_URL.rstrip("/")
        for srv in mcp_servers:
            actual_url = (srv.get("url") or "").rstrip("/")
            # Inject auth headers into ANY server pointing at the backend's
            # internal MCP SSE endpoint — not just the one named
            # "Numina Backend MCP".  Legacy records (e.g. "numina-family-data",
            # type=general) point at the same URL and previously missed headers,
            # causing a 401 on the MCP SSE handshake.
            is_backend_mcp = (
                srv.get("name") == "Numina Backend MCP"
                or "/internal/mcp/" in (srv.get("url") or "")
                or actual_url == f"{expected_prefix}/api/v1/internal/mcp/{family_id}/sse"
            )
            if is_backend_mcp:
                if not actual_url.startswith(expected_prefix):
                    srv["url"] = (
                        expected_prefix + "/api/v1/internal/mcp/" + family_id + "/sse"
                    )
                mcp_headers: dict[str, str] = {
                    "X-Agent-Token": create_agent_token(family_id),
                    "X-Family-Id": family_id,
                }
                if user_id:
                    mcp_headers["X-Caller-User-Id"] = user_id
                srv["headers"] = mcp_headers
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
