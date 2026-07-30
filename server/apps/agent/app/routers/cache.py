"""Agent 内部 API — 缓存管理端点。

供 backend 调用，通知 agent 清理家庭的 DeerFlowAdapter 缓存。
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from apps.agent.services.deerflow_adapter.adapter import invalidate_family_adapter_cache
from packages.security.service_auth.agent_token_verify import verify_service_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal/cache", tags=["internal"])


@router.post("/invalidate/{family_id}")
def invalidate_cache(
    family_id: str,
    token_family: str = Depends(verify_service_token),
) -> dict:
    """清理家庭的 DeerFlowAdapter 缓存。

    Backend 在以下场景调用此端点：
    - 家庭更新 AI 配置（provider/api_key/model_id 变化）
    - 家庭禁用 AI 功能
    - 家庭删除

    Args:
        family_id: 家庭 ID

    Returns:
        {"success": True, "family_id": "..."}
    """
    if family_id != token_family:
        raise HTTPException(status_code=403, detail="family_id mismatch")
    invalidate_family_adapter_cache(family_id)
    logger.info(f"[agent/cache] invalidated adapter cache for family={family_id}")
    return {"success": True, "family_id": family_id}