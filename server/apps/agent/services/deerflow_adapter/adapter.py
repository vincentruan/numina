"""DeerFlowAdapter — async wrapper around DeerFlowClient.stream().

支持两种模式：
1. 全局单例模式（向后兼容）：使用全局环境变量配置
2. 家庭级缓存模式：按家庭动态注入 AI 配置（api_key, model_id）
"""

import asyncio
import contextlib
import json
import logging
import os
import threading
import traceback
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from deerflow.config.app_config import reload_app_config

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.exceptions import (
    DeerFlowError,
    DeerFlowSkillNotFoundError,
    DeerFlowTimeoutError,
)
from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _init_lock,
    get_family_adapter,
    invalidate_family_adapter,
)

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """Structured event from DeerFlow stream — replaces [THINK]/[TEXT] string prefixes."""
    type: Literal["thinking", "text"]
    content: str


# Lazy-initialized executor and semaphore — read concurrency from settings at first use,
# not at import time, to avoid circular imports and allow test overrides.
_executor: ThreadPoolExecutor | None = None
_semaphore: asyncio.Semaphore | None = None
_init_lock = threading.Lock()  # noqa: F811 — intentional redefinition; module-level lock used by _produce()

# Separate lock for SQLite checkpointer writes — prevents SQLITE_BUSY under concurrency.
# The harness uses SqliteSaver (langgraph-checkpoint-sqlite) which does not handle
# concurrent writes internally; we serialize at the adapter layer instead.
_CHECKPOINTER_LOCK = asyncio.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        with _init_lock:
            if _executor is None:
                from apps.agent.app.config import settings
                _executor = ThreadPoolExecutor(
                    max_workers=settings.DEERFLOW_CONCURRENCY,
                    thread_name_prefix="deerflow",
                )
    return _executor


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        with _init_lock:
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
    ) -> None:
        """Initialize adapter.

        Args:
            config_path: 全局配置文件路径（向后兼容模式）
            timeout_seconds: DeerFlow 调用超时时间
            family_id: 家庭 ID（家庭级配置模式）
            ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）
            mcp_servers: MCP server configs to inject into DeerFlow config YAML
        """
        self._timeout = timeout_seconds
        self._family_id = family_id
        self._ai_config = ai_config
        self._mcp_servers = mcp_servers
        self._config_path: str | None = None  # Store config_path for reloading before stream

        if family_id and ai_config:
            # 家庭级配置模式：从缓存获取 DeerFlowClient 和 config_path
            self._client, self._config_path = get_family_adapter(
                family_id, ai_config,
                subagent_enabled=subagent_enabled,
                plan_mode=plan_mode,
                mcp_servers=mcp_servers,
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
            raise ValueError("Either config_path or (family_id + ai_config) must be provided")

    async def dispatch(self, skill_name: str, context: RedactedContext, thread_id: str) -> str:
        """Dispatch a skill call and return the full response string.

        _CHECKPOINTER_LOCK serializes SqliteSaver writes across concurrent calls,
        preventing SQLITE_BUSY. The lock is held on the async side (before the
        executor call) so it works correctly across threads.
        """
        async with _get_semaphore(), _CHECKPOINTER_LOCK:
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        _get_executor(),
                        self._sync_dispatch,
                        skill_name,
                        context,
                        thread_id,
                    ),
                    timeout=self._timeout,
                )
                return result
            except TimeoutError:
                raise DeerFlowTimeoutError(
                    f"DeerFlow skill '{skill_name}' timed out after {self._timeout}s"
                ) from None
            except DeerFlowSkillNotFoundError:
                raise
            except DeerFlowError:
                raise
            except Exception as e:
                raise DeerFlowError(f"DeerFlow error in skill '{skill_name}': {e}") from e

    async def stream_dispatch(
        self,
        skill_name: str,
        context: RedactedContext,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Dispatch a skill call and yield text chunks as they arrive.

        enable_thinking: if True and the model supports it, extended thinking is enabled.
        Note: thinking flag is passed via context metadata; DeerFlow harness reads it.

        _CHECKPOINTER_LOCK is NOT held across the stream — only dispatch() needs it
        for synchronous SQLite checkpoint writes. Streaming reads do not write to the
        checkpointer, so holding the lock here would serialize all concurrent streams.
        """
        async with _get_semaphore():
            async for chunk in self._async_stream_chunks(
                skill_name, context, thread_id, enable_thinking
            ):
                yield chunk

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
            if not (
                hasattr(event, "type")
                and event.type == "messages-tuple"
                and isinstance(event.data, dict)
                and event.data.get("type") == "ai"
            ):
                return
            additional_kwargs = event.data.get("additional_kwargs") or {}
            content = event.data.get("content")
            reasoning = additional_kwargs.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                loop.call_soon_threadsafe(queue.put_nowait, StreamChunk("thinking", reasoning))
            if isinstance(content, list):
                text_parts: list[str] = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "thinking" and block.get("thinking"):
                            loop.call_soon_threadsafe(queue.put_nowait, StreamChunk("thinking", block["thinking"]))
                        elif block.get("type") == "text" and block.get("text"):
                            text_parts.append(block["text"])
                if text_parts:
                    loop.call_soon_threadsafe(queue.put_nowait, StreamChunk("text", "".join(text_parts)))
            elif isinstance(content, str) and content:
                loop.call_soon_threadsafe(queue.put_nowait, StreamChunk("text", content))

        def _produce() -> None:
            """Run in thread pool — puts StreamChunk objects into queue, None signals end."""
            try:
                # For family-mode adapters, hold _init_lock for the entire stream to prevent
                # concurrent requests from corrupting the global DeerFlow config singleton.
                # This serializes family requests but guarantees config correctness.
                if self._config_path:
                    with _init_lock:
                        # Set DEER_FLOW_CONFIG_PATH env var so get_app_config() resolves to our temp config
                        prev_config_path = os.environ.get("DEER_FLOW_CONFIG_PATH")
                        os.environ["DEER_FLOW_CONFIG_PATH"] = str(self._config_path)
                        # Set DEER_FLOW_EXTENSIONS_CONFIG_PATH so ExtensionsConfig.from_file()
                        # reads our per-family extensions_config.json (contains MCP headers
                        # including X-Caller-User-Id for caller-bound principal).
                        extensions_path = Path(self._config_path).parent / "extensions_config.json"
                        prev_extensions_path = os.environ.get("DEER_FLOW_EXTENSIONS_CONFIG_PATH")
                        if extensions_path.exists():
                            os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = str(extensions_path)
                        try:
                            reload_app_config(str(self._config_path))
                            message = self._build_message(skill_name, context, enable_thinking=enable_thinking)
                            for event in self._client.stream(message, thread_id=thread_id, thinking_enabled=enable_thinking):
                                _process_event(event)
                        finally:
                            # Restore previous value (or remove if it wasn't set)
                            if prev_config_path is not None:
                                os.environ["DEER_FLOW_CONFIG_PATH"] = prev_config_path
                            else:
                                os.environ.pop("DEER_FLOW_CONFIG_PATH", None)
                            if prev_extensions_path is not None:
                                os.environ["DEER_FLOW_EXTENSIONS_CONFIG_PATH"] = prev_extensions_path
                            else:
                                os.environ.pop("DEER_FLOW_EXTENSIONS_CONFIG_PATH", None)
                else:
                    # Global config mode - no serialization needed
                    message = self._build_message(skill_name, context, enable_thinking=enable_thinking)
                    for event in self._client.stream(message, thread_id=thread_id, thinking_enabled=enable_thinking):
                        _process_event(event)
            except Exception as e:
                logger.error("[deerflow] stream_chunks failed: %s\n%s", e, traceback.format_exc())
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(_get_executor(), _produce)
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

    def _sync_dispatch(self, skill_name: str, context: RedactedContext, thread_id: str) -> str:
        """Synchronous DeerFlow call — runs in thread pool executor."""
        try:
            prompt = self._build_prompt(skill_name, context)
            chunks = []
            for event in self._client.stream(
                message=prompt,
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
                raise DeerFlowSkillNotFoundError(f"Skill not found: {skill_name}") from e
            raise DeerFlowError(str(e)) from e

    def _build_prompt(self, skill_name: str, context: RedactedContext) -> str:
        """Build a skill-dispatch prompt from the redacted context."""
        ctx_dict = context.model_dump(exclude={"redaction_log"})
        return f"[SKILL:{skill_name}]\n{json.dumps(ctx_dict, ensure_ascii=False, indent=2)}"

    def _build_message(self, skill_name: str, context: RedactedContext, enable_thinking: bool = False) -> str:
        """Build the message to send to DeerFlow for stream_dispatch.

        Encodes skill name, context, and thinking flag as JSON.
        DeerFlow harness reads the 'thinking' field to enable extended thinking.
        """
        context_dict = context.model_dump()
        return json.dumps({
            "skill": skill_name,
            "context": context_dict,
            "thinking": enable_thinking,
        })


def _make_adapter() -> DeerFlowAdapter | None:
    """Construct the global singleton from settings. Returns None if config is missing.

    注意：此单例仅用于向后兼容（全局环境变量模式）。
    生产环境应使用家庭级配置模式（通过 get_family_adapter_cache）。
    """
    try:
        # DeerFlowClient expects a config file, not a directory
        config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "deerflow_config")
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
    return _deerflow_adapter_singleton


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
) -> "DeerFlowAdapter":
    """创建家庭级的 DeerFlowAdapter（动态注入 AI 配置）。

    Args:
        family_id: 家庭 ID
        ai_config: 家庭的 AI 配置（从 backend 获取）
        timeout_seconds: DeerFlow 调用超时时间
        subagent_enabled: 是否启用子 agent 委托（init-time 参数）
        plan_mode: 是否启用 TodoList 规划中间件（init-time 参数）
        mcp_servers: MCP server configs to inject into DeerFlow config YAML

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
    )


def invalidate_family_adapter_cache(family_id: str) -> None:
    """清理家庭的 DeerFlowAdapter 缓存（当家庭禁用 AI 或配置变更时调用）。

    Args:
        family_id: 家庭 ID
    """
    invalidate_family_adapter(family_id)
