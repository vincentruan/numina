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
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

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

logger = logging.getLogger(__name__)

# Bounded thread pool — each stream() call holds a thread for its full duration
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="deerflow")
# Semaphore bounds concurrent DeerFlow calls to match the executor pool size.
# NOTE: Semaphore(4) does NOT serialize SQLite writes — it allows up to 4 concurrent
# holders. The separate _CHECKPOINTER_LOCK (limit-1) serializes checkpointer writes.
_SEMAPHORE = asyncio.Semaphore(4)
# Separate lock for SQLite checkpointer writes — prevents SQLITE_BUSY under concurrency.
# The harness uses SqliteSaver (langgraph-checkpoint-sqlite) which does not handle
# concurrent writes internally; we serialize at the adapter layer instead.
_CHECKPOINTER_LOCK = asyncio.Lock()


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
    ) -> None:
        """Initialize adapter.

        Args:
            config_path: 全局配置文件路径（向后兼容模式）
            timeout_seconds: DeerFlow 调用超时时间
            family_id: 家庭 ID（家庭级配置模式）
            ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）
        """
        self._timeout = timeout_seconds
        self._family_id = family_id
        self._ai_config = ai_config

        if family_id and ai_config:
            # 家庭级配置模式：从缓存获取 DeerFlowClient
            self._client = get_family_adapter(family_id, ai_config)
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
        async with _SEMAPHORE, _CHECKPOINTER_LOCK:
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        _EXECUTOR,
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
    ) -> AsyncGenerator[str, None]:
        """Dispatch a skill call and yield text chunks as they arrive.

        enable_thinking: if True and the model supports it, extended thinking is enabled.
        Note: thinking flag is passed via context metadata; DeerFlow harness reads it.

        _CHECKPOINTER_LOCK is NOT held across the stream — only dispatch() needs it
        for synchronous SQLite checkpoint writes. Streaming reads do not write to the
        checkpointer, so holding the lock here would serialize all concurrent streams.
        """
        async with _SEMAPHORE:
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
    ) -> AsyncGenerator[str, None]:
        """Wrap synchronous DeerFlowClient.stream() to yield chunks asynchronously."""
        loop = asyncio.get_running_loop()
        # Queue carries str chunks, None for clean end, or BaseException for errors.
        queue: asyncio.Queue[str | BaseException | None] = asyncio.Queue()

        def _produce() -> None:
            """Run in thread pool — puts chunks into queue, None signals end."""
            try:
                message = self._build_message(skill_name, context, enable_thinking=enable_thinking)
                for event in self._client.stream(message, thread_id=thread_id):
                    chunk = None
                    # DeerFlow returns StreamEvent(type="messages-tuple", data={"type": "ai", "content": "..."})
                    if (
                        hasattr(event, "type")
                        and event.type == "messages-tuple"
                        and isinstance(event.data, dict)
                        and event.data.get("type") == "ai"
                    ):
                        content = event.data.get("content")
                        if isinstance(content, str) and content:
                            chunk = content
                    if chunk:
                        loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:
                logger.error("[deerflow] stream_chunks failed: %s", e)
                # Send the exception to the consumer so it can re-raise rather than
                # silently treating the error as a clean end-of-stream.
                loop.call_soon_threadsafe(queue.put_nowait, e)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        future = loop.run_in_executor(_EXECUTOR, _produce)
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

def create_family_adapter(family_id: str, ai_config: dict[str, Any], timeout_seconds: int = 120) -> DeerFlowAdapter:
    """创建家庭级的 DeerFlowAdapter（动态注入 AI 配置）。

    Args:
        family_id: 家庭 ID
        ai_config: 家庭的 AI 配置（从 backend 获取）
        timeout_seconds: DeerFlow 调用超时时间

    Returns:
        DeerFlowAdapter 实例（缓存复用）
    """
    return DeerFlowAdapter(family_id=family_id, ai_config=ai_config, timeout_seconds=timeout_seconds)


def invalidate_family_adapter_cache(family_id: str) -> None:
    """清理家庭的 DeerFlowAdapter 缓存（当家庭禁用 AI 或配置变更时调用）。

    Args:
        family_id: 家庭 ID
    """
    invalidate_family_adapter(family_id)
