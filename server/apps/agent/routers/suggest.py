"""智能资产录入助手端点（由 backend 调用）。

U6 (Resolved-10): suggest 重构为轻量 LLM 单次调用，不再走 ``orchestrator.dispatch``
（完整 agent run）。router 取家庭 AI config → 调 ``asset_suggest.suggest_asset_fields``
（内部用 ``_create_lightweight_llm`` + ``llm.ainvoke``，与 title 生成同形态）。
"""

import logging

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.asset_suggest import _SUGGEST_DEFAULTS, suggest_asset_fields
from packages.security.service_auth.agent_token_verify import verify_service_token

router = APIRouter(prefix="/suggest", tags=["suggest"])
logger = logging.getLogger(__name__)


class AssetSuggestRequest(BaseModel):
    name: str
    category: str
    asset_type: str = "physical"


@router.post("/asset")
async def suggest_asset(
    body: AssetSuggestRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    _token_family: str = Depends(verify_service_token),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """返回资产字段 AI 建议（AssetSuggestResult，同步 JSON）。

    前端契约不变（``http.post<AssetSuggestResult>``）；backend ``ai_suggest.py``
    透传本端点的 JSON 响应。
    """
    client = BackendClient(family_id=x_family_id)
    ai_config = await client.get_family_ai_config()
    providers = ai_config.get("providers", [])
    if not providers:
        # No AI provider configured — return safe defaults so asset entry is
        # not blocked (mirrors the LLM-failure fallback in asset_suggest).
        return dict(_SUGGEST_DEFAULTS)

    # Circuit-state aware selection: skip open providers, probe half_open
    # ~10% of the time. Falls back to None when all providers are unavailable.
    from apps.agent.services.orchestrator import _select_stream_run_provider

    selected = _select_stream_run_provider(providers)
    if selected is None:
        return dict(_SUGGEST_DEFAULTS)
    selected_provider = selected
    return await suggest_asset_fields(
        name=body.name,
        category=body.category,
        asset_type=body.asset_type,
        ai_config=selected_provider,
    )
