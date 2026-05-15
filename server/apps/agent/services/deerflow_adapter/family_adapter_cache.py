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

import contextlib
import logging
import os
import shutil
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

from deerflow.client import DeerFlowClient
from deerflow.config.app_config import reload_app_config

logger = logging.getLogger(__name__)

# LRU 缓存：最多 100 个家庭
_MAX_CACHE_SIZE = 100
_adapter_cache: OrderedDict[str, tuple[DeerFlowClient, Path]] = OrderedDict()
# Thread lock to prevent concurrent cache mutations (works in sync context)
_cache_lock = threading.Lock()

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
    """Extract the checkpointer DB path from base/config.yaml.

    Returns the configured path, or a safe default if the config is missing
    or the checkpointer section is absent.
    """
    default = "/app/data/deerflow-checkpoints.db"
    try:
        import yaml  # type: ignore[import-untyped]

        config_path = Path(base_config_dir) / "base" / "config.yaml"
        if not config_path.exists():
            return default
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        path = cfg.get("checkpointer", {}).get("path", default)
        return path or default
    except Exception:
        return default


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
) -> Path:
    """生成临时配置文件，动态注入家庭的 AI 配置到 models 列表。

    Args:
        base_config_dir: 基础配置目录路径
        ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）

    Returns:
        临时配置文件的路径
    """
    import yaml  # type: ignore[import-untyped]

    # 复制 base config 作为模板
    base_config_path = Path(base_config_dir) / "base" / "config.yaml"
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")

    # 读取模板 YAML
    with open(base_config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 提取家庭的 AI 配置
    api_key = ai_config.get("api_key", "")
    model_id = ai_config.get("ai_model_id", "claude-haiku-4-5")
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
    thinking_supported = bool(ai_config.get("thinking_supported", False))
    # For OpenAI-compatible models that support thinking, use ReasoningChatOpenAI which
    # extracts reasoning_content from the API delta into additional_kwargs automatically.
    # Standard ChatOpenAI ignores the reasoning_content field in streaming responses.
    if thinking_supported and provider in ("openai", "openai_compatible"):
        use_class = "deerflow.models.patched_openai:ReasoningChatOpenAI"
    model_entry: dict[str, Any] = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }
    if thinking_supported and provider in ("openai", "openai_compatible"):
        # Pass enable_thinking=true in extra_body when thinking mode is active.
        # This triggers GLM-5/Qwen3/DeepSeek to return reasoning_content in the delta.
        model_entry["when_thinking_enabled"] = {"extra_body": {"enable_thinking": True}}
        # Explicitly disable thinking when deep_think=false to prevent spurious reasoning_content.
        model_entry["when_thinking_disabled"] = {"extra_body": {"enable_thinking": False}}
    if base_url:
        model_entry["base_url"] = base_url

    config["models"] = [model_entry]
    # 移除旧的 llm 节（已弃用）
    config.pop("llm", None)

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
) -> DeerFlowClient:
    """获取家庭的 DeerFlowClient 实例（带缓存）。

    Each client receives the shared checkpointer so multi-turn conversation
    state is persisted across requests. DeerFlow namespaces state by thread_id,
    so different families' conversations remain isolated even with a shared
    checkpointer instance.

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

    # 检查缓存 (thread lock to prevent race)
    with _cache_lock:
        if family_id in _adapter_cache:
            client, _ = _adapter_cache[family_id]
            # 移到末尾（LRU 更新）
            _adapter_cache.move_to_end(family_id)
            logger.debug("[deerflow_cache] reuse cached adapter for family=%s", family_id)
            return client

        # 缓存满时清理最旧的
        if len(_adapter_cache) >= _MAX_CACHE_SIZE:
            oldest_family_id, (_, oldest_config_path) = _adapter_cache.popitem(last=False)
            # 清理临时配置目录
            with contextlib.suppress(Exception):
                shutil.rmtree(oldest_config_path.parent, ignore_errors=True)
            logger.debug("[deerflow_cache] evicted adapter for family=%s", oldest_family_id)

    # 生成临时配置（outside lock to avoid blocking during file I/O）
    temp_config_path = _generate_temp_config(base_config_dir, ai_config)

    # 设置环境变量（DeerFlow harness 需要 DEER_FLOW_CONFIG_PATH）
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(temp_config_path)

    # Obtain the shared checkpointer before reload_app_config() so the
    # checkpointer DB path is read from the base config, not the per-family
    # temp config (which has the same checkpointer section but we want to
    # initialise it exactly once).
    checkpointer = _get_shared_checkpointer(base_config_dir)

    # 初始化 DeerFlowClient — pass checkpointer explicitly so each client
    # uses the shared persistent store instead of resolving get_checkpointer()
    # lazily after reload_app_config() may have changed the global config.
    try:
        reload_app_config(str(temp_config_path))
        client = DeerFlowClient(config_path=str(temp_config_path), checkpointer=checkpointer)
        # 缓存 (thread lock for safe insertion)
        with _cache_lock:
            _adapter_cache[family_id] = (client, temp_config_path)
        logger.info(
            "[deerflow_cache] created new adapter for family=%s, model=%s",
            family_id,
            ai_config.get("ai_model_id"),
        )
        return client
    except Exception as e:
        # 清理临时配置
        with contextlib.suppress(Exception):
            shutil.rmtree(temp_config_path.parent, ignore_errors=True)
        raise RuntimeError(f"Failed to initialize DeerFlowClient for family={family_id}: {e}") from e


def invalidate_family_adapter(family_id: str) -> None:
    """清理家庭的缓存实例。

    Args:
        family_id: 家庭 ID
    """
    with _cache_lock:
        if family_id in _adapter_cache:
            _, config_path = _adapter_cache.pop(family_id)
            with contextlib.suppress(Exception):
                shutil.rmtree(config_path.parent, ignore_errors=True)
            logger.info("[deerflow_cache] invalidated adapter for family=%s", family_id)


def clear_cache() -> None:
    """清理所有缓存实例。"""
    with _cache_lock:
        for _family_id, (_, config_path) in list(_adapter_cache.items()):
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