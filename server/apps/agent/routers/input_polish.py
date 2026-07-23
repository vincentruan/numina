"""输入润色端点（D3 DeerFlow 同步）。

前端 composer 直接调用（cookie 鉴权 + ``X-Family-Id``，与
``runs_stream.py`` 同形态的 ``verify_family_token`` 依赖），不走 backend 透传。
取家庭 AI config → 调 ``input_polish.polish_draft``（内部用
``_create_lightweight_llm`` + ``llm.ainvoke``，与 ``suggest`` / title 同形态）。
"""

import logging

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from apps.agent.app.auth.jwt_verify import VerifiedFamily, verify_family_token
from apps.agent.core.backend_client import BackendClient
from apps.agent.services.input_polish import polish_draft

router = APIRouter(prefix="/input-polish", tags=["input-polish"])
logger = logging.getLogger(__name__)


class InputPolishRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    locale: str | None = None
    thread_id: str | None = None


class InputPolishResponse(BaseModel):
    rewritten_text: str
    changed: bool


@router.post("", response_model=InputPolishResponse)
async def input_polish(
    body: InputPolishRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    verified: VerifiedFamily = Depends(verify_family_token),
):
    """返回改写后的草稿（同步 JSON）。``changed=False`` 表示无需替换。"""
    client = BackendClient(family_id=x_family_id)
    ai_config = await client.get_family_ai_config()
    providers = ai_config.get("providers", [])
    if not providers:
        # No AI provider configured — return original unchanged so the
        # composer is not blocked (mirrors suggest.py's safe-default fallback).
        return InputPolishResponse(rewritten_text=body.text, changed=False)

    # providers come pre-filtered to is_active==True (backend /ai/config),
    # so providers[0] is the active provider. _create_lightweight_llm reads
    # ai_provider/ai_model_id/api_key/ai_base_url from this dict.
    selected_provider = providers[0]
    rewritten, changed = await polish_draft(body.text, selected_provider)
    return InputPolishResponse(rewritten_text=rewritten, changed=changed)
