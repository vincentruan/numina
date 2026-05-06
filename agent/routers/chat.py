"""问答助手 agent 路由。"""

import json
import logging
import time
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import settings
from core.backend_client import BackendClient
from core.llm import LLMClient
from schemas.policy import CapabilityPolicy
from services.audit_logger import AuditEntry, audit_logger
from services.orchestrator import orchestrator
from services.pii_redactor import pii_redactor
from services.policy_guard import policy_guard

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str


class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False


@router.post("/ask")
async def ask(
    body: ChatRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="chat",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=body.question,
        thread_id=x_thread_id,
    )
    return response.model_dump()


@router.post("/ask/stream")
async def ask_stream(
    body: ChatStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
):
    """流式问答，支持 deep_think 模式。
    输出格式：每个 chunk 以 [THINK] 或 [TEXT] 前缀标识块类型。
    """
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def generate():
        audit_id = str(uuid.uuid4())
        start_ms = int(time.monotonic() * 1000)
        success = False
        try:
            client = BackendClient(family_id=x_family_id)
            try:
                ai_config = await client.get_family_ai_config()
            except Exception as e:
                logger.error(f"[chat/stream] fetch ai_config failed: {e}")
                yield "[TEXT]暂时无法获取 AI 配置，请稍后重试。"
                return

            policy = CapabilityPolicy(
                ai_enabled=ai_config.get("ai_enabled", False),
                allowed_capabilities=ai_config.get("allowed_capabilities", []),
                admin_only_capabilities=ai_config.get("admin_only_capabilities", []),
                member_role=ai_config.get("member_role", "member"),
            )
            decision = policy_guard.check(policy, "chat")
            if not decision.allowed:
                yield f"[TEXT]{decision.reason}"
                return

            llm = LLMClient(
                provider=ai_config.get("ai_provider", ""),
                api_key=ai_config.get("api_key", ""),
                model_id=ai_config.get("ai_model_id", ""),
                base_url=ai_config.get("ai_base_url"),
                timeout=float(ai_config.get("timeout_seconds", 60)),
            )

            # PII redaction before passing user question to LLM
            redacted_question, _ = pii_redactor.redact_text(body.question)

            from services.chat import (
                ANSWER_PROMPT,
                _classify_intent,
                _fetch_data_for_intent,
            )
            intent = await _classify_intent(redacted_question, llm)
            try:
                data = await _fetch_data_for_intent(intent, client)
            except Exception as e:
                logger.error(f"[chat/stream] data fetch failed: {e}")
                data = {}

            if intent == "unknown":
                yield "[TEXT]抱歉，我目前只能回答关于净资产、资产配置、负债、趋势、日均成本、低效资产和到期资产的问题。"
                return

            prompt = ANSWER_PROMPT.format(
                question=redacted_question,
                data=json.dumps(data, ensure_ascii=False, default=str),
            )

            if body.deep_think:
                async for block_type, chunk in llm.stream_with_thinking(
                    prompt, max_tokens=8000, thinking_budget=5000
                ):
                    prefix = "[THINK]" if block_type == "thinking" else "[TEXT]"
                    yield f"{prefix}{chunk}"
            else:
                async for chunk in llm.stream_text(prompt, max_tokens=1024):
                    yield f"[TEXT]{chunk}"

            success = True

        except Exception as e:
            logger.error(f"[chat/stream] unhandled error: {e}")
            yield "[TEXT]抱歉，AI 服务暂时不可用，请稍后重试。"
        finally:
            audit_logger.log_call(AuditEntry(
                family_id=x_family_id,
                capability="chat",
                success=success,
                audit_id=audit_id,
                user_id=x_user_id,
                duration_ms=int(time.monotonic() * 1000) - start_ms,
            ))

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
