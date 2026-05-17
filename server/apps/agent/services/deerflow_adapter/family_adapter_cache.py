"""按家庭缓存的 DeerFlowAdapter — 支持动态注入家庭级 AI 配置。

方案 B 实现：
- 每家庭一个 DeerFlowClient 实例（LRU 缓存）
- 动态生成临时配置文件，注入家庭的 api_key/model_id
- 缓存失效：家庭禁用 AI 或配置变更时清理

Session memory injection:
- A shared SqliteSaver checkpointer is passed explicitly to every DeerFlowClient.
- Without an explicit checkpointer, DeerFlowClient falls back to get_checkpointer()
  which may return InMemorySaver (lost on restart) or a stale singleton after
  reload_app_config() resets the global config for a different family.
- All families share one checkpointer instance; DeerFlow namespaces state by
  thread_id so family isolation is maintained at the conversation level.
"""

import atexit
import contextlib
import logging
import os
import re
import shutil
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from deerflow.client import DeerFlowClient
from deerflow.config.app_config import reload_app_config

logger = logging.getLogger(__name__)

# Safe ID pattern for family_id validation (prevents path traversal)
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")

# LRU 缓存：最多 100 个家庭
_MAX_CACHE_SIZE = 100
# Values are either (DeerFlowClient, Path) for a live entry, or None as a
# placeholder while a new client is being initialised (prevents TOCTOU races
# where two threads both pass the size check and both insert).
_adapter_cache: OrderedDict[tuple[str, str, bool, bool], tuple[DeerFlowClient, Path] | None] = OrderedDict()
# Thread lock to prevent concurrent cache mutations (works in sync context)
_cache_lock = threading.Lock()
# Per-key init lock: serialises reload_app_config + DeerFlowClient() for the
# same (family_id, config_id) so concurrent requests don't interleave global
# DeerFlow config state.
_init_lock = threading.Lock()

# Shared checkpointer singleton — created once, reused by all DeerFlowClient instances.
# Guarded by _checkpointer_lock to prevent double-initialisation under concurrency.
_shared_checkpointer = None
_checkpointer_lock = threading.Lock()
_checkpointer_ctx = None  # open context manager keeping the SqliteSaver connection alive


def _get_shared_checkpointer(base_config_dir: str | None = None):
    """Return the shared LangGraph checkpointer, creating it on first call.

    Reads the checkpointer config from the base config.yaml so the DB path
    matches what the operator configured (default: /app/data/deerflow-checkpoints.db).
    Falls back to InMemorySaver if the config is absent or the sqlite package
    is not installed.
    """
    global _shared_checkpointer, _checkpointer_ctx

    with _checkpointer_lock:
        if _shared_checkpointer is not None:
            return _shared_checkpointer

        if base_config_dir is None:
            base_config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "deerflow_config")

        # Read checkpointer path from base config.yaml
        db_path = _read_checkpointer_path(base_config_dir)

        try:
            from langgraph.checkpoint.sqlite import SqliteSaver

            os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
            _checkpointer_ctx = SqliteSaver.from_conn_string(db_path)
            _shared_checkpointer = _checkpointer_ctx.__enter__()
            _shared_checkpointer.setup()
            logger.info("[deerflow_cache] shared checkpointer: SqliteSaver(%s)", db_path)
        except ImportError:
            from langgraph.checkpoint.memory import InMemorySaver

            _shared_checkpointer = InMemorySaver()
            logger.warning(
                "[deerflow_cache] langgraph-checkpoint-sqlite not installed; "
                "using InMemorySaver — multi-turn memory will not survive restarts"
            )
        except Exception as e:
            from langgraph.checkpoint.memory import InMemorySaver

            _shared_checkpointer = InMemorySaver()
            logger.warning(
                "[deerflow_cache] checkpointer init failed (%s); falling back to InMemorySaver", e
            )

        return _shared_checkpointer


def _read_checkpointer_path(base_config_dir: str) -> str:
    """Return the checkpointer DB path from settings.

    Uses settings.DEERFLOW_DB_PATH which derives from DATA_ROOT.
    """
    from apps.agent.app.config import settings

    return settings.DEERFLOW_DB_PATH


def close_shared_checkpointer() -> None:
    """Close the shared checkpointer connection. Call at process shutdown."""
    global _shared_checkpointer, _checkpointer_ctx
    with _checkpointer_lock:
        if _checkpointer_ctx is not None:
            with contextlib.suppress(Exception):
                _checkpointer_ctx.__exit__(None, None, None)
            _checkpointer_ctx = None
        _shared_checkpointer = None


def _generate_temp_config(
    base_config_dir: str,
    ai_config: dict[str, Any],
    family_id: str = "",
) -> Path:
    """生成临时配置文件，动态注入家庭的 AI 配置到 models 列表。

    Args:
        base_config_dir: 基础配置目录路径
        ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）

    Returns:
        临时配置文件的路径
    """
    import yaml  # type: ignore[import-untyped]

    # Validate family_id to prevent path traversal
    if family_id and not _SAFE_ID_PATTERN.match(family_id):
        raise ValueError(f"Invalid family_id: {family_id!r}. Must match pattern: {_SAFE_ID_PATTERN.pattern}")

    # 复制 base config 作为模板
    base_config_path = Path(base_config_dir) / "base" / "config.yaml"
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")

    # 读取模板 YAML
    with open(base_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 提取家庭的 AI 配置 — 缺少关键字段时趁早报错
    api_key = ai_config.get("api_key", "")
    model_id = ai_config.get("ai_model_id")
    if not model_id:
        raise ValueError(
            f"ai_model_id is required but not configured for family={family_id}. "
            "请在 AI 配置中填写模型 ID。"
        )
    base_url = ai_config.get("ai_base_url", "")
    provider = ai_config.get("ai_provider", "openai")

    # 映射 provider 到 LangChain 类路径（DeerFlow 期望冒号分隔格式）
    provider_class_map: dict[str, str] = {
        "anthropic": "langchain_anthropic:ChatAnthropic",
        "openai": "langchain_openai:ChatOpenAI",
        "openai_compatible": "langchain_openai:ChatOpenAI",
    }
    use_class = provider_class_map.get(provider, "langchain_openai:ChatOpenAI")

    # 构建 models 列表（DeerFlow harness 期望的格式）
    # Prefer model_1_capabilities list; fall back to legacy thinking_supported flag.
    model_1_caps = ai_config.get("model_1_capabilities")
    if model_1_caps is not None:
        thinking_supported = "deep_thinking" in model_1_caps
    else:
        thinking_supported = bool(ai_config.get("thinking_supported", False))

    # Select appropriate LangChain model class based on provider and thinking support.
    # DeerFlow provides patched model classes for specific providers that handle
    # reasoning_content extraction from streaming deltas correctly.
    if thinking_supported:
        if "deepseek" in model_id.lower():
            # DeepSeek R1 requires patched class for reasoning content
            use_class = "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
        elif provider in ("openai", "openai_compatible"):
            # OpenAI-compatible models (GLM-5, Qwen3, QwQ, etc.) that support thinking
            use_class = "deerflow.models.patched_openai:ReasoningChatOpenAI"
        elif provider == "anthropic":
            # Anthropic-compatible endpoint (including DashScope GLM/Qwen via /anthropic).
            # The adapter handles both reasoning_content and Anthropic thinking content blocks.
            use_class = "langchain_anthropic:ChatAnthropic"
        else:
            use_class = provider_class_map.get(provider, "langchain_openai:ChatOpenAI")
    else:
        # Non-thinking models use standard classes
        use_class = provider_class_map.get(provider, "langchain_openai:ChatOpenAI")

    model_entry: dict[str, Any] = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }

    # Configure when_thinking_enabled/disabled according to DeerFlow2 spec.
    # Different model families require different extra_body structures.
    if thinking_supported:
        if "deepseek" in model_id.lower():
            # DeepSeek R1 uses 'thinking.type: enabled' format
            model_entry["when_thinking_enabled"] = {
                "extra_body": {"thinking": {"type": "enabled"}}
            }
            model_entry["when_thinking_disabled"] = {
                "extra_body": {"thinking": {"type": "disabled"}}
            }
        elif provider in ("openai", "openai_compatible"):
            # OpenAI-compatible models (GLM-5, Qwen3, QwQ, etc.) use 'enable_thinking' flag.
            # Includes models accessed via Anthropic-compatible endpoints (DashScope).
            model_entry["when_thinking_enabled"] = {
                "extra_body": {"enable_thinking": True}
            }
            # Explicitly disable thinking when deep_think=false to prevent
            # spurious reasoning_content in streaming responses
            model_entry["when_thinking_disabled"] = {
                "extra_body": {"enable_thinking": False}
            }
        elif provider == "anthropic":
            # Native Anthropic Claude models use the thinking parameter directly.
            # Note: GLM/Qwen models accessed via an Anthropic-compatible endpoint
            # (e.g. DashScope /apps/anthropic) do NOT support thinking this way —
            # they require provider="openai_compatible" with the OpenAI-compatible
            # endpoint and enable_thinking=true in extra_body.
            model_entry["when_thinking_enabled"] = {
                "thinking": {"type": "enabled", "budget_tokens": 10000}
            }
            model_entry["when_thinking_disabled"] = {
                "thinking": {"type": "disabled"}
            }

    if base_url:
        model_entry["base_url"] = base_url

    config["models"] = [model_entry]
    # 移除旧的 llm 节（已弃用）
    config.pop("llm", None)

    # 注入家庭级 memory 隔离路径：每家庭独立文件，防止跨家庭 facts 污染
    # Context7 确认 DeerFlow memory 配置键为 storage_path（非 path）
    from apps.agent.app.config import settings
    memory_path = Path(settings.AGENT_DATA_DIR) / family_id / "agent" / "memory.json"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    if "memory" not in config:
        config["memory"] = {}
    config["memory"]["storage_path"] = str(memory_path)

    # 写入临时文件
    temp_dir = Path(tempfile.mkdtemp(prefix="deerflow_config_"))
    temp_config_path = temp_dir / "config.yaml"
    with open(temp_config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    return temp_config_path


def get_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    base_config_dir: str | None = None,
    timeout_seconds: int = 120,
    subagent_enabled: bool = False,
    plan_mode: bool = False,
) -> DeerFlowClient:
    """获取家庭的 DeerFlowClient 实例（带缓存）。

    Each client receives the shared checkpointer so multi-turn conversation
    state is persisted across requests. DeerFlow namespaces state by thread_id,
    so different families' conversations remain isolated even with a shared
    checkpointer instance.

    Cache key is (family_id, config_id, subagent_enabled, plan_mode) — different
    flag combinations create distinct client instances since these are init-time
    parameters on DeerFlowClient.

    Thread safety:
    - _cache_lock guards all reads/writes to _adapter_cache.
    - A None placeholder is inserted under _cache_lock before releasing it,
      so concurrent threads that miss the cache see the placeholder and wait
      on _init_lock rather than both starting initialisation.
    - _init_lock serialises reload_app_config() + DeerFlowClient() so that
      concurrent requests for different families don't interleave global
      DeerFlow config state.

    Args:
        family_id: 家庭 ID
        ai_config: 家庭的 AI 配置
        base_config_dir: 基础配置目录，默认为 agent/deerflow_config
        timeout_seconds: DeerFlow 超时时间

    Returns:
        DeerFlowClient 实例
    """
    if base_config_dir is None:
        base_config_dir = os.path.join(os.path.dirname(__file__), "..", "..", "deerflow_config")

    config_id: str = ai_config.get("config_id", "")
    cache_key: tuple[str, str, bool, bool] = (family_id, config_id, subagent_enabled, plan_mode)

    # Fast path: return cached client
    with _cache_lock:
        entry = _adapter_cache.get(cache_key)
        if entry is not None:
            client, _ = entry
            _adapter_cache.move_to_end(cache_key)
            logger.debug("[deerflow_cache] reuse cached adapter for family=%s config_id=%s subagent=%s plan=%s", family_id, config_id, subagent_enabled, plan_mode)
            return client

        # Reserve the slot with a placeholder to prevent concurrent initialisations
        # for the same key (TOCTOU fix). Also evict the oldest entry if at capacity.
        if len(_adapter_cache) >= _MAX_CACHE_SIZE:
            oldest_key, oldest_entry = _adapter_cache.popitem(last=False)
            if oldest_entry is not None:
                _, oldest_config_path = oldest_entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(oldest_config_path.parent, ignore_errors=True)
            logger.debug("[deerflow_cache] evicted adapter for key=%s", oldest_key)

        _adapter_cache[cache_key] = None  # placeholder

    # Serialise reload_app_config() + DeerFlowClient() to prevent concurrent
    # threads from interleaving global DeerFlow config state. File I/O for
    # _generate_temp_config happens outside this lock to minimise contention.
    temp_config_path = _generate_temp_config(base_config_dir, ai_config, family_id=family_id)

    # Obtain the shared checkpointer before reload_app_config() so the
    # checkpointer DB path is read from the base config, not the per-family
    # temp config (initialised exactly once).
    checkpointer = _get_shared_checkpointer(base_config_dir)

    try:
        with _init_lock:
            # Re-check: another thread may have completed init for this key
            # while we were waiting on _init_lock.
            with _cache_lock:
                entry = _adapter_cache.get(cache_key)
                if entry is not None:
                    client, _ = entry
                    _adapter_cache.move_to_end(cache_key)
                    # Clean up the temp config we generated but won't use
                    with contextlib.suppress(Exception):
                        shutil.rmtree(temp_config_path.parent, ignore_errors=True)
                    return client

            # Set DEER_FLOW_CONFIG_PATH inside the init lock so concurrent
            # threads for different families don't overwrite each other's path.
            # DeerFlowClient.__init__ calls get_app_config() which uses this
            # env var to resolve the config file path.
            prev_config_path = os.environ.get("DEER_FLOW_CONFIG_PATH")
            os.environ["DEER_FLOW_CONFIG_PATH"] = str(temp_config_path)
            try:
                reload_app_config(str(temp_config_path))
                client = DeerFlowClient(
                    config_path=str(temp_config_path),
                    checkpointer=checkpointer,
                    model_name=None,
                    thinking_enabled=bool(ai_config.get("thinking_supported", False)),
                    subagent_enabled=subagent_enabled,
                    plan_mode=plan_mode,
                )
            finally:
                # Restore previous value (or remove if it wasn't set)
                if prev_config_path is not None:
                    os.environ["DEER_FLOW_CONFIG_PATH"] = prev_config_path
                else:
                    os.environ.pop("DEER_FLOW_CONFIG_PATH", None)

        with _cache_lock:
            _adapter_cache[cache_key] = (client, temp_config_path)

        logger.info(
            "[deerflow_cache] created new adapter for family=%s config_id=%s model=%s",
            family_id,
            config_id,
            ai_config.get("ai_model_id"),
        )
        return client
    except Exception as e:
        # Remove placeholder and clean up temp config on failure
        with _cache_lock:
            if _adapter_cache.get(cache_key) is None:
                _adapter_cache.pop(cache_key, None)
        with contextlib.suppress(Exception):
            shutil.rmtree(temp_config_path.parent, ignore_errors=True)
        raise RuntimeError(f"Failed to initialize DeerFlowClient for family={family_id} config_id={config_id}: {e}") from e


def _atexit_cleanup() -> None:
    """Clean up all cached adapters and temp config dirs at process exit."""
    with contextlib.suppress(Exception):
        clear_cache()


atexit.register(_atexit_cleanup)


def invalidate_family_adapter(family_id: str) -> None:
    """清理家庭的所有缓存实例（按 family_id 批量清除所有 config_id 条目）。

    Args:
        family_id: 家庭 ID
    """
    with _cache_lock:
        keys_to_remove = [k for k in _adapter_cache if k[0] == family_id]
        for key in keys_to_remove:
            entry = _adapter_cache.pop(key)
            if entry is not None:
                _, config_path = entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(config_path.parent, ignore_errors=True)
            logger.info("[deerflow_cache] invalidated adapter for family=%s config_id=%s", family_id, key[1])


def invalidate_family_adapter_cache(family_id: str, config_id: str | None = None) -> None:
    """清理家庭的缓存实例。

    Args:
        family_id: 家庭 ID
        config_id: 供应商配置 ID。若提供则只清除该条目；若为 None 则清除该家庭所有条目。
    """
    with _cache_lock:
        if config_id is not None:
            # Remove all 4-tuple entries matching (family_id, config_id, *, *)
            keys_to_remove = [k for k in _adapter_cache if k[0] == family_id and k[1] == config_id]
            for key in keys_to_remove:
                entry = _adapter_cache.pop(key)
                if entry is not None:
                    _, config_path = entry
                    with contextlib.suppress(Exception):
                        shutil.rmtree(config_path.parent, ignore_errors=True)
                logger.info("[deerflow_cache] invalidated adapter for family=%s config_id=%s flags=%s", family_id, config_id, key[2:])
        else:
            keys_to_remove = [k for k in _adapter_cache if k[0] == family_id]
            for key in keys_to_remove:
                entry = _adapter_cache.pop(key)
                if entry is not None:
                    _, config_path = entry
                    with contextlib.suppress(Exception):
                        shutil.rmtree(config_path.parent, ignore_errors=True)
                logger.info("[deerflow_cache] invalidated adapter for family=%s config_id=%s", family_id, key[1])


def clear_cache() -> None:
    """清理所有缓存实例。"""
    with _cache_lock:
        for _key, entry in list(_adapter_cache.items()):
            if entry is not None:
                _, config_path = entry
                with contextlib.suppress(Exception):
                    shutil.rmtree(config_path.parent, ignore_errors=True)
        _adapter_cache.clear()
        logger.info("[deerflow_cache] cleared all cached adapters")


def get_cache_stats() -> dict[str, int]:
    """获取缓存统计信息。"""
    with _cache_lock:
        return {
            "cached_families": len(_adapter_cache),
            "max_size": _MAX_CACHE_SIZE,
        }