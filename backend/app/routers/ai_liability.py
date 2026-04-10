"""AI 负债优化顾问端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import get_current_user
from app.config import settings
from app.models.user import User

router = APIRouter(prefix="/ai/liability-advice", tags=["ai-liability"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_liability_advice(
    current_user: User = Depends(get_current_user),
    _ai: None = Depends(require_ai_enabled),
):
    """获取负债优化建议（实时调用 agent）。"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/liability/analyze",
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="AI 服务响应超时")
    except Exception as e:
        logger.error(f"调用 agent liability 失败: {e}")
        raise HTTPException(status_code=503, detail="AI 服务暂时不可用")
