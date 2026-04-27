"""Agent 内部 API — 缓存管理端点。

供 backend 调用，通知 agent 清理家庭的 DeerFlowAdapter 缓存。
"""

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from services.deerflow_adapter.adapter import invalidate_family_adapter_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/cache", tags=["internal"])


@router.post("/invalidate/{family_id}")
def invalidate_cache(
    family_id: str,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> dict:
    """清理家庭的 DeerFlowAdapter 缓存。

    Backend 在以下场景调用此端点：
    - 家庭更新 AI 配置（provider/api_key/model_id 变化）
    - 家庭禁用 AI 功能
    - 家庭删除

    Args:
        family_id: 家庭 ID
        x_agent_token: 内部认证 token

    Returns:
        {"success": True, "family_id": "..."}
    """
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    invalidate_family_adapter_cache(family_id)
    logger.info(f"[agent/cache] invalidated adapter cache for family={family_id}")
    return {"success": True, "family_id": family_id}