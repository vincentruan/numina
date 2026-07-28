"""AI 资产录入建议端点 — 代理转发给 agent 服务。"""

import logging

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient

router = APIRouter(prefix="/ai/suggest", tags=["ai-suggest"])
logger = logging.getLogger(__name__)


class AssetSuggestRequest(BaseModel):
    name: str
    category: str
    asset_type: str = "physical"

    @field_validator("name", "category")
    @classmethod
    def not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("不能为空")
        if len(v) > 100:
            raise ValueError("不能超过100字")
        return v


@router.post("/asset")
async def suggest_asset_fields(
    body: AssetSuggestRequest,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
):
    """调用 agent 服务，返回资产字段 AI 建议。"""
    try:
        agent_client = AgentClient(current_user.family_id, current_user.id, timeout=45.0)
        resp = await agent_client.post(
            "/suggest/asset",
            json=body.model_dump(),
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT)
    except Exception as e:
        logger.error(f"调用 agent suggest 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
