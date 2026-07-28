"""DeerFlowAdapter — async wrapper around DeerFlowClient.stream().

支持两种模式：
1. 全局单例模式（向后兼容）：使用全局环境变量配置
2. 家庭级缓存模式：按家庭动态注入 AI 配置（api_key, model_id）
"""

import asyncio
import contextlib
import contextvars
import json
import logging
import os
import threading
import traceback
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Literal

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.exceptions import (
    DeerFlowError,
    DeerFlowSkillNotFoundError,
    DeerFlowTimeoutError,
)
from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    get_family_adapter,
    invalidate_family_adapter,
)
from apps.agent.services.message_classifier import (
    extract_tool_calls,
    resolve_tool_metadata,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """Structured event from DeerFlow stream — replaces [THINK]/[TEXT] string prefixes."""

    type: Literal[
        "thinking", "text", "tool_call", "tool_result", "tool_progress", "plan_update"
    ]
    content: str
    data: dict[str, Any] | None = None


# Lazy-initialized executor and semaphore — read concurrency from settings at first use,
# not at import time, to avoid circular imports and allow test overrides.
_executor: ThreadPoolExecutor | None = None
_semaphore: asyncio.Semaphore | None = None
_executor_lock = (
    threading.Lock()
)  # guards lazy _executor / _semaphore initialization only

# Separate lock for SQLite checkpointer writes — prevents SQLITE_BUSY under concurrency.
# The harness uses SqliteSaver (langgraph-checkpoint-sqlite) which does not handle
# concurrent writes internally; we serialize at the adapter layer instead.
_CHECKPOINTER_LOCK = asyncio.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _executor_lock:
            if _executor is None:
                from apps.agent.app.config import settings

                _executor = ThreadPoolExecutor(
                    max_workers=settings.DEERFLOW_CONCURRENCY,
                    thread_name_prefix="deerflow",
                )
    return _executor


def _run_in_executor_with_context(
    loop: asyncio.AbstractEventLoop,
    executor: ThreadPoolExecutor,
    func: Any,
    *args: Any,
) -> asyncio.Future:
    """Submit ``func`` to ``executor`` preserving the caller's contextvars.

    ``loop.run_in_executor`` does NOT propagate ``contextvars`` from the
    calling task into the pool thread. Numina relies on two coroutine-scoped
    ContextVars set in ``worker.run_agent`` before dispatch:

    - ``sandbox_family_id`` (``set_family_sandbox_context``) —
      ``NuminaLocalSandboxProvider._build_thread_path_mappings`` reads it to
      scope sandbox paths under ``AGENT_DATA_DIR/{family_id}/sandboxes/...``.
      Without propagation the provider sees ``family_id=None`` and returns
      empty path mappings, so ``write_file`` finds no mapping for
      ``/mnt/user-data/workspace`` and the file silently never lands on disk
      (the tool still returns ``"OK"`` — fail-open). This is the F2 root cause.
    - ``numina_active_skill_name`` (``set_active_skill``) — runtime tool
      filtering via ``filter_tools_by_skill_allowed_tools``.

    Capturing ``contextvars.copy_context()`` here and running ``func`` inside
    it (the same mechanism ``asyncio.to_thread`` uses) makes both ContextVars
    visible inside the deerflow stream thread, where LangGraph's ToolNode
    invokes sandbox tools (``write_file``/``read_file``) synchronously.
    """
    ctx = contextvars.copy_context()
    return loop.run_in_executor(executor, lambda: ctx.run(func, *args))


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        with _executor_lock:
            if _semaphore is None:
                from apps.agent.app.config import settings

                _semaphore = asyncio.Semaphore(settings.DEERFLOW_CONCURRENCY)
    return _semaphore


class DeerFlowAdapter:
    """Async adapter for DeerFlowClient. Protocol translation only — no business logic.

    支持两种初始化方式：
    1. 全局配置模式：传入 config_path（向后兼容）
    2. 家庭配置模式：传入 family_id + ai_config（动态注入）
    """

    def __init__(
        self,
        config_path: str | None = None,
        timeout_seconds: int = 120,
        family_id: str | None = None,
        ai_config: dict[str, Any] | None = None,
        subagent_enabled: bool = False,
        plan_mode: bool = False,
        mcp_servers: list[dict[str, Any]] | None = None,
        agent_name: str | None = None,
        middlewares: list[Any] | None = None,
        memory_enabled: bool = True,
        available_skills: set[str] | None = None,
    ) -> None:
        """Initialize adapter.

        Args:
            config_path: 全局配置文件路径（向后兼容模式）
            timeout_seconds: DeerFlow 调用超时时间
            family_id: 家庭 ID（家庭级配置模式）
            ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）
            mcp_servers: MCP server configs to inject into DeerFlow config YAML
            agent_name: Optional DeerFlowClient agent_name. When set, DeerMem
                buckets memory per (agent_name, user_id), isolating this adapter's
                memory from others (e.g. asset-report vs chat/lead-agent). None
                falls back to the client default (lead-agent global bucket).
            middlewares: Optional list of AgentMiddleware instances to inject into
                the DeerFlow agent. None = no custom middlewares (the default
                for all current numina paths — report.step2_json is
                worker-synthesized, not middleware-emitted).
            available_skills: Optional set of skill names to make available for
                slash activation. If None (default), all scanned skills are
                available. U3: the worker fetches the family's enabled custom
                skills and passes them here so DeerFlow's SkillActivationMiddleware
                enforces the whitelist.
        """
        self._timeout = timeout_seconds
        self._family_id = family_id
        self._ai_config = ai_config
        self._mcp_servers = mcp_servers
        self._config_path: str | None = (
            None  # Store config_path for reloading before stream
        )
        self._client: Any = None
        self._is_family_mode = False

        if family_id and ai_config:
            # 家庭级配置模式：从缓存获取 DeerFlowClient 和 config_path
            self._client, config_path_obj = get_family_adapter(
                family_id,
                ai_config,
                subagent_enabled=subagent_enabled,
                plan_mode=plan_mode,
                mcp_servers=mcp_servers,
                agent_name=agent_name,
                middlewares=middlewares,
                memory_enabled=memory_enabled,
                available_skills=available_skills,
            )
            self._config_path = (
                str(config_path_obj) if config_path_obj is not None else None
            )
            self._is_family_mode = True
        elif config_path:
            # 全局配置模式：直接初始化（向后兼容）
            from apps.agent.services.deerflow_adapter.client_factory import (
                get_deerflow_client,
            )

            self._client = get_deerflow_client(config_path)
            self._is_family_mode = False
        else:
            raise ValueError(
                "Either config_path or (family_id + ai_config) must be provided"
            )

    async def dispatch(
        self, skill_name: str, context: RedactedContext, thread_id: str
    ) -> str:
        """Dispatch a skill call and return the full response string.

        _CHECKPOINTER_LOCK serializes SqliteSaver writes across concurrent calls,
        preventing SQLITE_BUSY. The lock is held on the async side (before the
        executor call) so it works correctly across threads.
        """
        async with _get_semaphore(), _CHECKPOINTER_LOCK:
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    _run_in_executor_with_context(
                        loop,
                        _get_executor(),
                        self._sync_dispatch,
                        skill_name,
                        context,
                        thread_id,
                    ),
                    timeout=self._timeout,
                )
                return str(result)
            except TimeoutError:
                raise DeerFlowTimeoutError(
                    f"DeerFlow skill '{skill_name}' timed out after {self._timeout}s"
                ) from None
            except DeerFlowSkillNotFoundError:
                raise
            except DeerFlowError:
                raise
            except Exception as e:
                raise DeerFlowError(
                    f"DeerFlow error in skill '{skill_name}': {e}"
                ) from e

    async def stream_dispatch(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Dispatch a skill call and yield text chunks as they arrive.

        enable_thinking: per-call override passed to client.stream() via **kwargs.
        DeerFlowClient.stream() routes kwargs into _get_runnable_config(), which
        overrides the init-time thinking_enabled default for this specific call.
        See HARNESS_API.md OD-4 for the two-level control model.

        _CHECKPOINTER_LOCK is NOT held across the stream — only dispatch() needs it
        for synchronous SQLite checkpoint writes. Streaming reads do not write to the
        checkpointer, so holding the lock here would serialize all concurrent streams.
        """
        async with _get_semaphore():
            async for chunk in self._async_stream_chunks(
                skill_name, context, thread_id, enable_thinking
            ):
                yield chunk

    async def raw_stream_dispatch(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool = False,
        subagent_enabled: bool | None = None,
        plan_mode: bool | None = None,
    ) -> AsyncGenerator[Any, None]:
        """Yield raw LangGraph StreamEvents from DeerFlowClient.stream()."""
        # Set the original user content ContextVar so DeerFlow's
        # SkillActivationMiddleware sees the raw user text (before JSON wrapping).
        # The ContextVar propagates into the executor thread via
        # _run_in_executor_with_context (which uses contextvars.copy_context()).
        from apps.agent.services.deerflow_adapter.original_user_content_context import (
            reset_original_user_content,
            set_original_user_content,
        )

        original_content_token = set_original_user_content(context.free_text)
        try:
            # Build per-call kwargs for DeerFlowClient.stream(). Only include
            # overrides that are explicitly set (not None) so the adapter's
            # init-time defaults are preserved when no per-call mode is specified.
            stream_kwargs: dict[str, Any] = {"thinking_enabled": enable_thinking}
            if subagent_enabled is not None:
                stream_kwargs["subagent_enabled"] = subagent_enabled
            if plan_mode is not None:
                stream_kwargs["plan_mode"] = plan_mode

            async with _get_semaphore():
                loop = asyncio.get_running_loop()
                queue: asyncio.Queue[Any] = asyncio.Queue()

                def _produce() -> None:
                    try:
                        if self._config_path:
                            from deerflow.config.app_config import (
                                pop_current_app_config,
                                push_current_app_config,
                                reload_app_config,
                            )

                            family_config = reload_app_config(str(self._config_path))
                            push_current_app_config(family_config)

                            # Set the per-run extensions_config path via ContextVar.
                            # DeerFlow's ExtensionsConfig.from_file() reads MCP server
                            # configs from this file. The extensions_config.json is
                            # generated alongside config.yaml in
                            # family_adapter_cache._generate_temp_config() when
                            # mcp_servers is provided.
                            #
                            # We use a coroutine-scoped ContextVar instead of the
                            # process-global DEER_FLOW_EXTENSIONS_CONFIG_PATH env var:
                            # the env var is a single process-wide slot that two
                            # concurrent family runs overwrite, leaking family-A's MCP
                            # SSE URL (which embeds family-A's id) into family-B's run.
                            # The ContextVar is propagated into the deerflow executor
                            # thread + sync tool-executor pool, so _patched_get_mcp_tools
                            # reads the correct per-run path. No env restore needed —
                            # ContextVar isolation is automatic.
                            from pathlib import Path as _Path

                            from apps.agent.services.runtime.sandbox_provider import (
                                set_extensions_config_path,
                            )

                            extensions_path = (
                                _Path(str(self._config_path)).parent
                                / "extensions_config.json"
                            )
                            if extensions_path.exists():
                                set_extensions_config_path(str(extensions_path))
                                # Reset MCP cache so DeerFlow picks up the new config
                                try:
                                    from deerflow.config.extensions_config import (
                                        reset_extensions_config,
                                    )
                                    from deerflow.mcp.cache import reset_mcp_tools_cache

                                    reset_mcp_tools_cache()
                                    reset_extensions_config()
                                except ImportError:
                                    pass

                            try:
                                message = self._build_prompt(skill_name, context)
                                for event in self._client.stream(
                                    message, thread_id=thread_id, **stream_kwargs
                                ):
                                    loop.call_soon_threadsafe(queue.put_nowait, event)
                            finally:
                                if extensions_path.exists():
                                    set_extensions_config_path(None)
                                pop_current_app_config()
                        else:
                            message = self._build_prompt(skill_name, context)
                            for event in self._client.stream(
                                message, thread_id=thread_id, **stream_kwargs
                            ):
                                loop.call_soon_threadsafe(queue.put_nowait, event)
                    except Exception as e:
                        loop.call_soon_threadsafe(queue.put_nowait, e)
                    finally:
                        loop.call_soon_threadsafe(queue.put_nowait, None)

                future = _run_in_executor_with_context(loop, _get_executor(), _produce)
                try:
                    while True:
                        item = await asyncio.wait_for(
                            queue.get(), timeout=self._timeout
                        )
                        if item is None:
                            break
                        if isinstance(item, BaseException):
                            raise DeerFlowError(
                                f"DeerFlow stream error: {item}"
                            ) from item
                        yield item
                except TimeoutError as e:
                    raise DeerFlowTimeoutError(f"timeout after {self._timeout}s") from e
                finally:
                    import contextlib

                    with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                        await asyncio.wait_for(asyncio.shield(future), timeout=5.0)
        finally:
            # Reset the ContextVar, but catch ValueError in case we're in a
            # different context (e.g., after GeneratorExit when client disconnects)
            try:
                reset_original_user_content(original_content_token)
            except ValueError:
                # Token was created in a different context, ignore
                pass

    async def typed_stream_dispatch(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool = False,
        subagent_enabled: bool | None = None,
        plan_mode: bool | None = None,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        """Yield (sse_event_type, data) tuples from DeerFlowClient.stream().

        Maps raw LangGraph event types to SSE-friendly event names for the
        three-track protocol (messages / custom / values / end / error).

        Event type mapping:
          - ``messages-tuple`` → ``"messages"`` (AI text, tool calls)
          - ``values``         → ``"values"`` (state snapshots, plan todos)
          - ``end``           → ``"end"`` (stream complete)
          - ``error``         → ``"error"`` (stream error)
          - All other types   → ``"custom"`` (tool progress, metadata)

        Yields:
            (sse_event_type, data_dict) tuples ready for ``format_sse()``.
        """
        async for event in self.raw_stream_dispatch(
            skill_name,
            context,
            thread_id,
            enable_thinking,
            subagent_enabled=subagent_enabled,
            plan_mode=plan_mode,
        ):
            if isinstance(event, BaseException):
                yield ("error", {"error": str(event)})
                continue
            if not (hasattr(event, "type") and hasattr(event, "data")):
                continue

            event_type = event.type
            event_data = event.data

            if event_type == "messages-tuple" and isinstance(event_data, dict):
                yield ("messages", event_data)
            elif event_type == "values" and isinstance(event_data, dict):
                yield ("values", event_data)
            elif event_type == "end":
                yield ("end", event_data)
            elif event_type == "error":
                yield ("error", {"error": str(event_data)})
            else:
                # All other event types (tool progress, metadata, etc.) → custom
                if isinstance(event_data, dict):
                    yield ("custom", event_data)
                else:
                    yield ("custom", {"type": event_type, "data": event_data})

    async def _async_stream_chunks(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Wrap synchronous DeerFlowClient.stream() to yield chunks asynchronously."""
        loop = asyncio.get_running_loop()
        # Queue carries StreamChunk chunks, None for clean end, or BaseException for errors.
        queue: asyncio.Queue[StreamChunk | BaseException | None] = asyncio.Queue()

        def _process_event(event) -> None:
            """Process a single stream event and put chunks into queue."""
            if not hasattr(event, "type"):
                return

            # ── values event: plan todos ─────────────────────────────────────
            if event.type == "values" and isinstance(event.data, dict):
                todos = event.data.get("todos")
                if todos is not None:
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        StreamChunk("plan_update", content="", data={"todos": todos}),
                    )
                return

            # ── messages-tuple events ────────────────────────────────────────
            if not (event.type == "messages-tuple" and isinstance(event.data, dict)):
                return

            msg_type = event.data.get("type")

            # Tool message (ToolMessage shape) — emit tool_result
            if msg_type == "tool":
                tool_call_id = str(event.data.get("tool_call_id") or "")
                content = event.data.get("content")
                tool_name = event.data.get("name") or ""
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    StreamChunk(
                        "tool_result",
                        content="",
                        data={
                            "tool_call_id": tool_call_id,
                            "tool_name": tool_name,
                            "content": content,
                        },
                    ),
                )
                return

            # AI message — existing thinking/text extraction + new tool_call extraction
            if msg_type != "ai":
                return

            additional_kwargs = event.data.get("additional_kwargs") or {}
            content = event.data.get("content")
            reasoning = additional_kwargs.get("reasoning_content")

            # tool_calls on AI message — emit one StreamChunk per call
            tool_calls_raw = event.data.get("tool_calls")
            if tool_calls_raw:
                calls = extract_tool_calls(event.data)
                for call in calls:
                    tool_type, display_name, icon, display_key = resolve_tool_metadata(
                        call["name"]
                    )
                    is_internal = call["name"] == "write_todos"
                    chunk_data = {
                        "tool_call_id": call["id"],
                        "tool_name": call["name"],
                        "tool_type": tool_type,
                        "display_name": display_name,
                        "icon": icon,
                        "args": call["args"],
                        "internal": is_internal,
                    }
                    if display_key:
                        chunk_data["display_key"] = display_key
                    loop.call_soon_threadsafe(
                        queue.put_nowait,
                        StreamChunk("tool_call", content="", data=chunk_data),
                    )
                return

            # thinking / text content
            if isinstance(reasoning, str) and reasoning:
                loop.call_soon_threadsafe(
                    queue.put_nowait, StreamChunk("thinking", reasoning)
                )
            if isinstance(content, list):
                text_parts: list[str] = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "thinking" and block.get("thinking"):
                            loop.call_soon_threadsafe(
                                queue.put_nowait,
                                StreamChunk("thinking", block["thinking"]),
                            )
                        elif block.get("type") == "text" and block.get("text"):
                            text_parts.append(block["text"])
                if text_parts:
                    loop.call_soon_threadsafe(
                        queue.put_nowait, StreamChunk("text", "".join(text_parts))
                    )
            elif isinstance(content, str) and content:
                loop.call_soon_threadsafe(
                    queue.put_nowait, StreamChunk("text", content)
                )

        def _produce() -> None:
            """Run in thread pool — puts StreamChunk objects into queue, None signals end."""
            try:
                if self._config_path:
                    # Use DeerFlow's ContextVar API to inject per-family config into this
                    # thread's context without touching global env vars or holding a lock.
                    # ContextVars are isolated per ThreadPoolExecutor worker, so concurrent
                    # family requests see their own config.
                    from deerflow.config.app_config import (
                        pop_current_app_config,
                        push_current_app_config,
                        reload_app_config,
                    )

                    family_config = reload_app_config(str(self._config_path))
                    push_current_app_config(family_config)

                    # Set the per-run extensions_config path via ContextVar.
                    # See raw_stream_dispatch._produce for the multi-family leak
                    # rationale (process-global env var → cross-family MCP URL
                    # leak). ContextVar is coroutine-scoped and propagated into
                    # the deerflow executor thread + sync tool pool.
                    from pathlib import Path as _Path

                    from apps.agent.services.runtime.sandbox_provider import (
                        set_extensions_config_path,
                    )

                    extensions_path = (
                        _Path(str(self._config_path)).parent / "extensions_config.json"
                    )
                    if extensions_path.exists():
                        set_extensions_config_path(str(extensions_path))
                        # Reset MCP cache so DeerFlow picks up the new config
                        try:
                            from deerflow.config.extensions_config import (
                                reset_extensions_config,
                            )
                            from deerflow.mcp.cache import reset_mcp_tools_cache

                            reset_mcp_tools_cache()
                            reset_extensions_config()
                        except ImportError:
                            pass

                    try:
                        message = self._build_prompt(skill_name, context)
                        for event in self._client.stream(
                            message,
                            thread_id=thread_id,
                            thinking_enabled=enable_thinking,
                        ):
                            _process_event(event)
                    finally:
                        if extensions_path.exists():
                            set_extensions_config_path(None)
                        pop_current_app_config()
                else:
                    # Global config mode — no per-family override needed
                    message = self._build_prompt(skill_name, context)
                    for event in self._client.stream(
                        message, thread_id=thread_id, thinking_enabled=enable_thinking
                    ):
                        _process_event(event)
            except Exception as e:
                logger.error(
                    "[deerflow] stream_chunks failed: %s\n%s", e, traceback.format_exc()
                )
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = _run_in_executor_with_context(loop, _get_executor(), _produce)
        try:
            while True:
                item = await asyncio.wait_for(queue.get(), timeout=self._timeout)
                if item is None:
                    break
                if isinstance(item, BaseException):
                    raise DeerFlowError(f"DeerFlow stream error: {item}") from item
                yield item
        except TimeoutError as e:
            raise DeerFlowTimeoutError(
                f"DeerFlow stream_dispatch timeout after {self._timeout}s"
            ) from e
        finally:
            # Wait for the producer thread to finish so it doesn't leak a thread-pool
            # slot. asyncio.shield prevents an outer cancellation from abandoning the
            # wait, but we still need to await the shielded coroutine to actually block.
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(future), timeout=5.0)

    def _sync_dispatch(
        self, skill_name: str, context: RedactedContext, thread_id: str
    ) -> str:
        """Synchronous DeerFlow call — runs in thread pool executor."""
        try:
            message = self._build_prompt(skill_name, context)
            chunks = []

            if self._config_path:
                from deerflow.config.app_config import (
                    pop_current_app_config,
                    push_current_app_config,
                    reload_app_config,
                )

                family_config = reload_app_config(str(self._config_path))
                push_current_app_config(family_config)

                # Set the per-run extensions_config path via ContextVar.
                # See raw_stream_dispatch._produce for the multi-family leak
                # rationale (process-global env var → cross-family MCP URL leak).
                from pathlib import Path as _Path

                from apps.agent.services.runtime.sandbox_provider import (
                    set_extensions_config_path,
                )

                extensions_path = (
                    _Path(str(self._config_path)).parent / "extensions_config.json"
                )
                if extensions_path.exists():
                    set_extensions_config_path(str(extensions_path))
                    # Reset MCP cache so DeerFlow picks up the new config
                    try:
                        from deerflow.config.extensions_config import (
                            reset_extensions_config,
                        )
                        from deerflow.mcp.cache import reset_mcp_tools_cache

                        reset_mcp_tools_cache()
                        reset_extensions_config()
                    except ImportError:
                        pass

                try:
                    for event in self._client.stream(
                        message=message,
                        thread_id=thread_id,
                    ):
                        if (
                            hasattr(event, "type")
                            and event.type == "messages-tuple"
                            and isinstance(event.data, dict)
                            and event.data.get("type") == "ai"
                        ):
                            content = event.data.get("content")
                            if isinstance(content, str) and content:
                                chunks.append(content)
                finally:
                    if extensions_path.exists():
                        set_extensions_config_path(None)
                    pop_current_app_config()
            else:
                for event in self._client.stream(
                    message=message,
                    thread_id=thread_id,
                ):
                    if (
                        hasattr(event, "type")
                        and event.type == "messages-tuple"
                        and isinstance(event.data, dict)
                        and event.data.get("type") == "ai"
                    ):
                        content = event.data.get("content")
                        if isinstance(content, str) and content:
                            chunks.append(content)

            return "".join(chunks)
        except Exception as e:
            err_msg = str(e).lower()
            if "skill" in err_msg and ("not found" in err_msg or "unknown" in err_msg):
                raise DeerFlowSkillNotFoundError(
                    f"Skill not found: {skill_name}"
                ) from e
            raise DeerFlowError(str(e)) from e

    def _build_prompt(self, skill_name: str, context: RedactedContext) -> str:
        """Build a skill-dispatch prompt from the redacted context.

        ``exclude_defaults=True`` omits empty data fields (assets=[], liabilities=[],
        etc.) so the chat skill's MCP-based data retrieval isn't short-circuited by
        the LLM trusting injected empty data over calling its MCP tools. The chat
        worker (worker.py) builds a minimal context with only family_id + free_text;
        pre-fetched skills that actually populate data still emit those fields.

        Note: ``skill_name`` is no longer prefixed as ``[SKILL:{name}]`` — that
        prefix had no consumer. Skill content is injected by DeerFlow's native
        ``<skill_system>`` system-prompt section (filtered by ``available_skills``
        passed to ``DeerFlowClient``), so the user message only needs the context.
        """
        ctx_dict = context.model_dump(exclude={"redaction_log"}, exclude_defaults=True)
        return json.dumps(ctx_dict, ensure_ascii=False, indent=2)


def _make_adapter() -> DeerFlowAdapter | None:
    """Construct the global singleton from settings. Returns None if config is missing.

    注意：此单例仅用于向后兼容（全局环境变量模式）。
    生产环境应使用家庭级配置模式（通过 get_family_adapter_cache）。
    """
    try:
        # DeerFlowClient expects a config file, not a directory
        config_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "deerflow_config"
        )
        # Use environment-specific config if DEERFLOW_ENV is set, otherwise base
        env = os.getenv("DEERFLOW_ENV", "base")
        config_path = os.path.join(config_dir, env, "config.yaml")

        # Set DEER_FLOW_CONFIG_PATH so deerflow-harness can find it
        # (passing config_path to DeerFlowClient doesn't work due to get_app_config() re-resolving)
        os.environ["DEER_FLOW_CONFIG_PATH"] = config_path

        return DeerFlowAdapter(config_path=config_path, timeout_seconds=120)
    except Exception as e:
        import logging as _logging

        _logging.getLogger(__name__).warning(f"DeerFlow adapter init failed: {e}")
        return None


# ── 向后兼容的全局单例（延迟初始化）──────────────────────────────────────────

_UNINITIALIZED = object()  # sentinel constant for uninitialized state
_deerflow_adapter_singleton: DeerFlowAdapter | None | object = _UNINITIALIZED


def get_global_adapter() -> DeerFlowAdapter | None:
    """获取全局单例（延迟初始化，仅用于向后兼容）。

    生产环境应使用 create_family_adapter() 或家庭级缓存模式。
    """
    global _deerflow_adapter_singleton
    if _deerflow_adapter_singleton is _UNINITIALIZED:
        _deerflow_adapter_singleton = _make_adapter()
    if isinstance(_deerflow_adapter_singleton, DeerFlowAdapter):
        return _deerflow_adapter_singleton
    return None


# 向后兼容的模块属性访问（延迟初始化）
# 使用 __getattr__ 实现，避免模块导入时立即执行
def __getattr__(name: str) -> Any:
    if name == "deerflow_adapter":
        return get_global_adapter()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# ── 家庭级配置模式的 API ──────────────────────────────────────────────────


def create_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    timeout_seconds: int = 120,
    subagent_enabled: bool = False,
    plan_mode: bool = False,
    mcp_servers: list[dict[str, Any]] | None = None,
    agent_name: str | None = None,
    middlewares: list[Any] | None = None,
    memory_enabled: bool = True,
    available_skills: set[str] | None = None,
) -> "DeerFlowAdapter":
    """创建家庭级的 DeerFlowAdapter（动态注入 AI 配置）。

    Args:
        family_id: 家庭 ID
        ai_config: 家庭的 AI 配置（从 backend 获取）
        timeout_seconds: DeerFlow 调用超时时间
        subagent_enabled: 是否启用子 agent 委托（init-time 参数）
        plan_mode: 是否启用 TodoList 规划中间件（init-time 参数）
        mcp_servers: MCP server configs to inject into DeerFlow config YAML
        agent_name: Optional DeerMem memory-bucket key (see DeerFlowAdapter.__init__)
        middlewares: Optional AgentMiddleware list (see DeerFlowAdapter.__init__)
        memory_enabled: Whether DeerMem is enabled for this agent (read from
            ai_agents.memory_enabled via AgentRegistry by the caller; False for
            stateless fixed-flow agents like asset-report).
        available_skills: Optional set of skill names to make available for slash
            activation. If None (default), all scanned skills are available. U3:
            the worker fetches the family's enabled custom skills and passes them
            here so DeerFlow's SkillActivationMiddleware enforces the whitelist.

    Returns:
        DeerFlowAdapter 实例（缓存复用）
    """
    return DeerFlowAdapter(
        family_id=family_id,
        ai_config=ai_config,
        timeout_seconds=timeout_seconds,
        subagent_enabled=subagent_enabled,
        plan_mode=plan_mode,
        mcp_servers=mcp_servers,
        agent_name=agent_name,
        middlewares=middlewares,
        memory_enabled=memory_enabled,
        available_skills=available_skills,
    )


def invalidate_family_adapter_cache(family_id: str) -> None:
    """清理家庭的 DeerFlowAdapter 缓存（当家庭禁用 AI 或配置变更时调用）。

    Args:
        family_id: 家庭 ID
    """
    invalidate_family_adapter(family_id)
