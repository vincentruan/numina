"""AI 负债优化顾问端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends

from app.auth.ai_deps import require_ai_enabled, create_agent_token
from app.auth.deps import require_adult
from app.config import settings
from app.errors import AppError, ErrorCode
from app.models.user import User

router = APIRouter(prefix="/ai/liability-advice", tags=["ai-liability"])
logger = logging.getLogger(__name__)


@router.get("")
async def get_liability_advice(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
):
    """获取负债优化建议（实时调用 agent）。"""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/liability/analyze",
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": create_agent_token(current_user.family_id),
                },
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.TimeoutException:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT)
    except Exception as e:
        logger.error(f"调用 agent liability 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
