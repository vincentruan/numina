"""DeerFlow追问建议生成端点（由 backend 调用）。

Phase 7: 生成用户可能的追问建议。
"""

import hmac
import logging
import re

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.core.backend_client import BackendClient
from apps.agent.core.llm import LLMClient

router = APIRouter(prefix="/suggestions", tags=["suggestions"])
logger = logging.getLogger(__name__)

# System prompt for generating follow-up suggestions
SUGGESTIONS_SYSTEM_PROMPT = """你是一个对话助手，负责根据用户的对话历史生成3个可能的追问建议。
建议应该简洁、自然、口语化，符合中文用户的提问习惯。
每个建议应该是10-20字的简短问题，涵盖用户可能感兴趣的延伸话题。

输出格式要求：
每行一个建议，不要加序号或其他符号。例如：
我的净资产健康吗？
如何优化资产配置？
最近投资收益如何？"""

SUGGESTIONS_USER_PROMPT_TEMPLATE = """以下是用户与助手的对话历史：

{conversation}

请生成3个用户可能会继续追问的问题建议。每个建议一行，简洁口语化，10-20字。"""


class SuggestionsGenerateRequest(BaseModel):
    """Backend → Agent suggestions request."""
    conversation: str  # 已格式化的对话历史 "用户: ...\n助手: ..."
    n: int = 3  # 生成数量
    model_name: str | None = None  # 可选模型名


class SuggestionsGenerateResponse(BaseModel):
    """Agent → Backend suggestions response."""
    suggestions: list[str]


@router.post("/generate")
async def generate_suggestions(
    body: SuggestionsGenerateRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """生成追问建议。

    调用租户配置的 LLM 生成 n 条追问建议。
    """
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(
        x_agent_token, settings.AGENT_INTERNAL_TOKEN
    ):
        raise HTTPException(status_code=401, detail="invalid token")

    if not body.conversation.strip():
        return SuggestionsGenerateResponse(suggestions=[])

    n = body.n
    if n <= 0:
        return SuggestionsGenerateResponse(suggestions=[])

    # Fetch AI config for this family
    try:
        client = BackendClient(family_id=x_family_id)
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        logger.error("fetch ai_config failed family=%s: %s", x_family_id, e)
        return SuggestionsGenerateResponse(suggestions=[])

    providers = ai_config.get("providers", [])
    if not providers:
        logger.warning("no AI providers configured for family=%s", x_family_id)
        return SuggestionsGenerateResponse(suggestions=[])

    # Select first available provider
    provider = providers[0]
    api_key = provider.get("api_key")
    model_id = body.model_name or provider.get("ai_model_id") or provider.get("model_id")

    if not api_key or not model_id:
        logger.warning("missing api_key or model_id for family=%s", x_family_id)
        return SuggestionsGenerateResponse(suggestions=[])

    # Create LLM client
    try:
        llm_client = LLMClient(
            provider=provider.get("provider", "openai"),
            api_key=api_key,
            model_id=model_id,
            base_url=provider.get("base_url"),
            timeout=30.0,
        )
    except Exception as e:
        logger.error("create LLM client failed family=%s: %s", x_family_id, e)
        return SuggestionsGenerateResponse(suggestions=[])

    # Generate suggestions
    prompt = SUGGESTIONS_USER_PROMPT_TEMPLATE.format(conversation=body.conversation)

    try:
        response_text = await llm_client.complete(
            prompt=prompt,
            max_tokens=256,
            system=SUGGESTIONS_SYSTEM_PROMPT,
        )
    except Exception as e:
        logger.error("LLM complete failed family=%s: %s", x_family_id, e)
        return SuggestionsGenerateResponse(suggestions=[])

    # Parse suggestions from response
    # Each line should be a suggestion
    lines = response_text.strip().split("\n")
    suggestions = []
    for line in lines:
        line = line.strip()
        # Remove common prefixes like "1.", "一、", "- " etc.
        line = re.sub(r"^[\d一二三四五六七八九十]+[.、\-:\s]*", "", line).strip()
        # Skip empty lines or lines that are too long
        if line and len(line) <= 50:
            suggestions.append(line)

    return SuggestionsGenerateResponse(suggestions=suggestions[:n])