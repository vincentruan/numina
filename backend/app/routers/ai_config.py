"""AI 配置管理路由。"""

import time

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_owner
from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.family import Family
from app.models.user import User
from app.schemas.ai_config import AIConfigResponse, AIConfigTestResult, AIConfigUpdate
from app.services.ai_crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.security_log import _log_security_event

router = APIRouter(prefix="/ai", tags=["ai-config"])


def _get_family(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    if not family:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)
    return family


@router.get("/config", response_model=AIConfigResponse)
def get_ai_config(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """获取当前家庭 AI 配置（所有成员可查看）。"""
    family = _get_family(db, current_user)

    api_key_masked = None
    if family.ai_api_key_encrypted:
        decrypted = decrypt_api_key(family.ai_api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)

    return AIConfigResponse(
        ai_enabled=family.ai_enabled,
        ai_provider=family.ai_provider,
        ai_api_key_masked=api_key_masked,
        ai_base_url=family.ai_base_url,
        ai_model_id=family.ai_model_id,
        ai_vision_model_id=family.ai_vision_model_id,
    )


@router.put("/config", response_model=AIConfigResponse)
def update_ai_config(
    payload: AIConfigUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """更新 AI 配置（仅 owner）。"""
    family = _get_family(db, current_user)

    # 配置校验：如果 AI 开启但缺少必要配置，拒绝保存
    if payload.ai_enabled is True or (payload.ai_enabled is None and family.ai_enabled):
        provider = (
            payload.ai_provider
            if payload.ai_provider is not None
            else family.ai_provider
        )
        api_key = (
            payload.ai_api_key
            if payload.ai_api_key is not None
            else (family.ai_api_key_encrypted is not None)
        )
        if provider and not api_key:
            raise AppError(ErrorCode.AI_CONFIG_MISSING_API_KEY)
        if api_key and not provider:
            raise AppError(ErrorCode.AI_CONFIG_MISSING_PROVIDER)

    if payload.ai_enabled is not None:
        family.ai_enabled = payload.ai_enabled
    if payload.ai_provider is not None:
        family.ai_provider = payload.ai_provider
    if payload.ai_base_url is not None or "ai_base_url" in (
        payload.model_fields_set or set()
    ):
        family.ai_base_url = payload.ai_base_url
    if payload.ai_model_id is not None or "ai_model_id" in (
        payload.model_fields_set or set()
    ):
        family.ai_model_id = payload.ai_model_id
    if payload.ai_vision_model_id is not None or "ai_vision_model_id" in (
        payload.model_fields_set or set()
    ):
        family.ai_vision_model_id = payload.ai_vision_model_id
    if payload.ai_api_key is not None:
        if payload.ai_api_key == "":
            # 清空 API Key
            family.ai_api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.ai_api_key)
            if encrypted is None:
                raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
            family.ai_api_key_encrypted = encrypted

    db.commit()
    db.refresh(family)

    _log_security_event(
        "ai_config_updated",
        user_id=current_user.id,
        family_id=family.id,
        ai_enabled=family.ai_enabled,
        provider=family.ai_provider,
    )

    api_key_masked = None
    if family.ai_api_key_encrypted:
        decrypted = decrypt_api_key(family.ai_api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)

    return AIConfigResponse(
        ai_enabled=family.ai_enabled,
        ai_provider=family.ai_provider,
        ai_api_key_masked=api_key_masked,
        ai_base_url=family.ai_base_url,
        ai_model_id=family.ai_model_id,
        ai_vision_model_id=family.ai_vision_model_id,
    )


def _build_endpoint(base_url: str | None, default_base: str, path: str) -> str:
    """智能拼接 endpoint，避免 /v1 重复。

    Args:
        base_url: 用户配置的 base_url (可能已包含 /v1)
        default_base: 默认 base_url (如 https://api.anthropic.com)
        path: 路径部分 (如 /v1/messages)

    Returns:
        完整 endpoint URL
    """
    base = (base_url or default_base).rstrip("/")

    # 如果 base 已包含 path 的前缀（如 /v1），直接拼接完整路径
    if path.startswith("/v1") and base.endswith("/v1"):
        # 避免 /v1/v1 重复
        return f"{base}{path[3:]}"  # 去掉 path 的前缀 /v1
    else:
        return f"{base}{path}"


@router.post("/config/test", response_model=AIConfigTestResult)
async def test_ai_config(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试 AI API Key 连通性和模型能力（仅 owner）。

    测试内容：
    1. 文本生成能力（必须）
    2. 思考能力（Anthropic Claude extended thinking / OpenAI reasoning）
    3. 图像理解能力（vision model 配置时测试）
    """
    family = _get_family(db, current_user)

    if not family.ai_enabled:
        return AIConfigTestResult(success=False, message="AI 功能未开启")
    if not family.ai_provider:
        return AIConfigTestResult(success=False, message="未配置 AI Provider")
    if not family.ai_api_key_encrypted:
        return AIConfigTestResult(success=False, message="未配置 API Key")

    api_key = decrypt_api_key(family.ai_api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(success=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()

    # 测试文本能力
    model = family.ai_model_id
    if not model:
        return AIConfigTestResult(
            success=False, message="未配置模型 ID，请在服务商配置中填写"
        )

    start = time.monotonic()
    supports_text = False
    supports_thinking = False
    supports_image = False

    try:
        if family.ai_provider == "anthropic":
            # Anthropic 文本测试
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                if resp.status_code in (200, 400):
                    supports_text = True
                else:
                    return AIConfigTestResult(
                        success=False,
                        message=f"文本模型测试失败: HTTP {resp.status_code}",
                    )

            # Anthropic thinking 测试（使用 extended thinking 参数）
            if supports_text:
                thinking_endpoint = _build_endpoint(
                    family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        resp = await client.post(
                            thinking_endpoint,
                            headers={
                                "x-api-key": api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json",
                            },
                            json={
                                "model": model,
                                "max_tokens": 1,
                                "thinking": {"type": "enabled", "budget_tokens": 100},
                                "messages": [{"role": "user", "content": "think"}],
                            },
                        )
                        # 200 = 支持 thinking，400/403 = 不支持或参数错误
                        supports_thinking = resp.status_code == 200
                    except Exception:
                        supports_thinking = False

            # Anthropic 图像测试（使用 vision model 或主模型）
            if supports_text:
                vision_model = family.ai_vision_model_id or model
                vision_endpoint = _build_endpoint(
                    family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        resp = await client.post(
                            vision_endpoint,
                            headers={
                                "x-api-key": api_key,
                                "anthropic-version": "2023-06-01",
                                "content-type": "application/json",
                            },
                            json={
                                "model": vision_model,
                                "max_tokens": 1,
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "what"},
                                            {
                                                "type": "image",
                                                "source": {
                                                    "type": "url",
                                                    "url": "https://httpbin.org/image/png",
                                                },
                                            },
                                        ],
                                    }
                                ],
                            },
                        )
                        # 200 = 支持 vision，400 = 不支持或图片错误
                        supports_image = resp.status_code == 200
                    except Exception:
                        supports_image = False

        elif family.ai_provider == "openai":
            # OpenAI 文本测试
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                if resp.status_code in (200, 400):
                    supports_text = True
                else:
                    return AIConfigTestResult(
                        success=False,
                        message=f"文本模型测试失败: HTTP {resp.status_code}",
                    )

            # OpenAI thinking 测试（o 系列模型的 reasoning_effort）
            if supports_text and model.startswith("o"):
                thinking_endpoint = _build_endpoint(
                    family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        resp = await client.post(
                            thinking_endpoint,
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": model,
                                "max_completion_tokens": 1,
                                "reasoning_effort": "low",
                                "messages": [{"role": "user", "content": "think"}],
                            },
                        )
                        supports_thinking = resp.status_code in (200, 400)
                    except Exception:
                        supports_thinking = False

            # OpenAI 图像测试
            if supports_text:
                vision_model = family.ai_vision_model_id or model
                vision_endpoint = _build_endpoint(
                    family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
                )
                async with httpx.AsyncClient(timeout=10.0) as client:
                    try:
                        resp = await client.post(
                            vision_endpoint,
                            headers={
                                "Authorization": f"Bearer {api_key}",
                                "Content-Type": "application/json",
                            },
                            json={
                                "model": vision_model,
                                "max_tokens": 1,
                                "messages": [
                                    {
                                        "role": "user",
                                        "content": [
                                            {"type": "text", "text": "what"},
                                            {
                                                "type": "image_url",
                                                "image_url": {
                                                    "url": "https://httpbin.org/image/png"
                                                },
                                            },
                                        ],
                                    }
                                ],
                            },
                        )
                        supports_image = resp.status_code in (200, 400)
                    except Exception:
                        supports_image = False

        else:
            return AIConfigTestResult(
                success=False, message=f"不支持的 Provider: {family.ai_provider}"
            )

        latency = int((time.monotonic() - start) * 1000)

        # 构建成功消息
        capabilities = []
        if supports_text:
            capabilities.append("文本")
        if supports_thinking:
            capabilities.append("思考")
        if supports_image:
            capabilities.append("图像")

        return AIConfigTestResult(
            success=True,
            message=f"连接成功，支持能力: {', '.join(capabilities) if capabilities else '文本'}",
            latency_ms=latency,
            supports_text=supports_text,
            supports_thinking=supports_thinking,
            supports_image=supports_image,
        )

    except httpx.TimeoutException:
        return AIConfigTestResult(
            success=False, message="连接超时（10秒），请检查网络或 base_url"
        )
    except Exception as e:
        return AIConfigTestResult(success=False, message=f"连接失败: {str(e)}")
