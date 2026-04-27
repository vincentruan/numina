"""按家庭缓存的 DeerFlowAdapter — 支持动态注入家庭级 AI 配置。

方案 B 实现：
- 每家庭一个 DeerFlowClient 实例（LRU 缓存）
- 动态生成临时配置文件，注入家庭的 api_key/model_id
- 缓存失效：家庭禁用 AI 或配置变更时清理
"""

import logging
import os
import tempfile
import shutil
from collections import OrderedDict
from pathlib import Path
from typing import Any

from deerflow.client import DeerFlowClient
from deerflow.config.app_config import reload_app_config

logger = logging.getLogger(__name__)

# LRU 缓存：最多 100 个家庭
_MAX_CACHE_SIZE = 100
_adapter_cache: OrderedDict[str, tuple[DeerFlowClient, Path]] = OrderedDict()


def _generate_temp_config(
    base_config_dir: str,
    ai_config: dict[str, Any],
) -> Path:
    """生成临时配置文件，注入家庭的 AI 配置。

    Args:
        base_config_dir: 基础配置目录路径
        ai_config: 家庭的 AI 配置（api_key, ai_provider, ai_model_id 等）

    Returns:
        临时配置文件的路径
    """
    # 复制 base config 作为模板
    base_config_path = Path(base_config_dir) / "base" / "config.yaml"
    if not base_config_path.exists():
        raise FileNotFoundError(f"Base config not found: {base_config_path}")

    # 读取模板内容
    with open(base_config_path, encoding="utf-8") as f:
        content = f.read()

    # 替换环境变量占位符为实际值
    # DeerFlow 配置格式：$AI_MODEL → 替换为实际模型名
    api_key = ai_config.get("api_key", "")
    model_id = ai_config.get("ai_model_id", "claude-haiku-4-5")
    provider = ai_config.get("ai_provider", "anthropic")
    base_url = ai_config.get("ai_base_url", "")

    # 构建新配置内容
    # 替换 llm 部分
    content = content.replace("$AI_MODEL", model_id)
    content = content.replace("$AI_API_KEY", api_key)

    # 如果有自定义 base_url，注入到配置
    if base_url:
        # 在 llm 部分添加 base_url（需要 YAML 格式处理）
        lines = content.split("\n")
        new_lines = []
        in_llm_section = False
        for line in lines:
            new_lines.append(line)
            if line.startswith("llm:"):
                in_llm_section = True
            elif in_llm_section and line.strip() and not line.startswith("  ") and not line.startswith("#"):
                in_llm_section = False
            elif in_llm_section and "api_key:" in line:
                new_lines.append(f"  base_url: {base_url}")

        content = "\n".join(new_lines)

    # 写入临时文件
    temp_dir = Path(tempfile.mkdtemp(prefix="deerflow_config_"))
    temp_config_path = temp_dir / "config.yaml"
    with open(temp_config_path, "w", encoding="utf-8") as f:
        f.write(content)

    return temp_config_path


def get_family_adapter(
    family_id: str,
    ai_config: dict[str, Any],
    base_config_dir: str | None = None,
    timeout_seconds: int = 120,
) -> DeerFlowClient:
    """获取家庭的 DeerFlowClient 实例（带缓存）。

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

    # 检查缓存
    if family_id in _adapter_cache:
        client, _ = _adapter_cache[family_id]
        # 移到末尾（LRU 更新）
        _adapter_cache.move_to_end(family_id)
        logger.debug(f"[deerflow_cache] reuse cached adapter for family={family_id}")
        return client

    # 缓存满时清理最旧的
    if len(_adapter_cache) >= _MAX_CACHE_SIZE:
        oldest_family_id, (_, oldest_config_path) = _adapter_cache.popitem(last=False)
        # 清理临时配置目录
        try:
            shutil.rmtree(oldest_config_path.parent, ignore_errors=True)
        except Exception:
            pass
        logger.debug(f"[deerflow_cache] evicted adapter for family={oldest_family_id}")

    # 生成临时配置
    temp_config_path = _generate_temp_config(base_config_dir, ai_config)

    # 设置环境变量（DeerFlow 需要）
    os.environ["DEER_FLOW_CONFIG_PATH"] = str(temp_config_path)
    os.environ["AI_MODEL"] = ai_config.get("ai_model_id", "claude-haiku-4-5")
    os.environ["AI_API_KEY"] = ai_config.get("api_key", "")

    # 初始化 DeerFlowClient
    try:
        reload_app_config(str(temp_config_path))
        client = DeerFlowClient(config_path=str(temp_config_path))
        # 缓存
        _adapter_cache[family_id] = (client, temp_config_path)
        logger.info(f"[deerflow_cache] created new adapter for family={family_id}, model={ai_config.get('ai_model_id')}")
        return client
    except Exception as e:
        # 清理临时配置
        try:
            shutil.rmtree(temp_config_path.parent, ignore_errors=True)
        except Exception:
            pass
        raise RuntimeError(f"Failed to initialize DeerFlowClient for family={family_id}: {e}") from e


def invalidate_family_adapter(family_id: str) -> None:
    """清理家庭的缓存实例。

    Args:
        family_id: 家庭 ID
    """
    if family_id in _adapter_cache:
        _, config_path = _adapter_cache.pop(family_id)
        try:
            shutil.rmtree(config_path.parent, ignore_errors=True)
        except Exception:
            pass
        logger.info(f"[deerflow_cache] invalidated adapter for family={family_id}")


def clear_cache() -> None:
    """清理所有缓存实例。"""
    for family_id, (_, config_path) in list(_adapter_cache.items()):
        try:
            shutil.rmtree(config_path.parent, ignore_errors=True)
        except Exception:
            pass
    _adapter_cache.clear()
    logger.info("[deerflow_cache] cleared all cached adapters")


def get_cache_stats() -> dict[str, int]:
    """获取缓存统计信息。"""
    return {
        "cached_families": len(_adapter_cache),
        "max_size": _MAX_CACHE_SIZE,
    }