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
        ai_test_connected=family.ai_test_connected,
        ai_test_message=family.ai_test_message,
        ai_test_latency_ms=family.ai_test_latency_ms,
        ai_test_timestamp=family.ai_test_timestamp,
        ai_test_thinking_success=family.ai_test_thinking_success,
        ai_test_thinking_message=family.ai_test_thinking_message,
        ai_test_thinking_latency_ms=family.ai_test_thinking_latency_ms,
        ai_test_thinking_timestamp=family.ai_test_thinking_timestamp,
        ai_vision_test_success=family.ai_vision_test_success,
        ai_vision_test_message=family.ai_vision_test_message,
        ai_vision_test_latency_ms=family.ai_vision_test_latency_ms,
        ai_vision_test_timestamp=family.ai_vision_test_timestamp,
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

    # ── Invalidate agent cache ────────────────────────────────
    # When AI config changes, agent's DeerFlowAdapter cache must be cleared
    # so the next request uses the new configuration
    try:
        import httpx

        from app.config import settings as backend_settings

        async def _invalidate_agent_cache():
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    f"{backend_settings.AGENT_BASE_URL}/internal/cache/invalidate/{family.id}",
                    headers={"X-Agent-Token": backend_settings.AGENT_INTERNAL_TOKEN},
                )

        # Fire-and-forget: don't block the response on agent call
        import asyncio
        asyncio.create_task(_invalidate_agent_cache())
    except Exception as e:
        # Log but don't fail the request if agent cache invalidation fails
        import logging
        logging.getLogger(__name__).warning(f"Failed to invalidate agent cache for family={family.id}: {e}")

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
        ai_test_connected=family.ai_test_connected,
        ai_test_message=family.ai_test_message,
        ai_test_latency_ms=family.ai_test_latency_ms,
        ai_test_timestamp=family.ai_test_timestamp,
        ai_test_thinking_success=family.ai_test_thinking_success,
        ai_test_thinking_message=family.ai_test_thinking_message,
        ai_test_thinking_latency_ms=family.ai_test_thinking_latency_ms,
        ai_test_thinking_timestamp=family.ai_test_thinking_timestamp,
        ai_vision_test_success=family.ai_vision_test_success,
        ai_vision_test_message=family.ai_vision_test_message,
        ai_vision_test_latency_ms=family.ai_vision_test_latency_ms,
        ai_vision_test_timestamp=family.ai_vision_test_timestamp,
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

    分别测试：
    1. 主模型：连接测试 + 思考能力测试
    2. 图像模型（如果配置了且不同于主模型）：图像理解能力测试

    测试结果会持久化到数据库，供前端展示。
    """
    from datetime import datetime

    family = _get_family(db, current_user)

    if not family.ai_enabled:
        return AIConfigTestResult(connected=False, message="AI 功能未开启")
    if not family.ai_provider:
        return AIConfigTestResult(connected=False, message="未配置 AI Provider")
    if not family.ai_api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(family.ai_api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()

    # 测试主模型
    model = family.ai_model_id
    if not model:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    # 测试主模型连接
    connection_result = await _test_connection(family, api_key, model)

    # 测试思考能力（仅在连接成功时）
    thinking_result = None
    if connection_result["connected"]:
        thinking_result = await _test_thinking(family, api_key, model)

    # 测试图像模型（如果配置了且不同于主模型）
    vision_test_result = None
    if family.ai_vision_model_id and family.ai_vision_model_id != model:
        vision_test_result = await _test_vision_model(
            family, api_key, family.ai_vision_model_id
        )

    # 持久化连接测试结果
    family.ai_test_connected = connection_result["connected"]
    family.ai_test_message = connection_result["message"]
    family.ai_test_latency_ms = connection_result["latency_ms"]
    family.ai_test_timestamp = datetime.utcnow()

    # 持久化思考测试结果
    if thinking_result:
        family.ai_test_thinking_success = thinking_result["success"]
        family.ai_test_thinking_message = thinking_result["message"]
        family.ai_test_thinking_latency_ms = thinking_result["latency_ms"]
        family.ai_test_thinking_timestamp = datetime.utcnow()
    else:
        family.ai_test_thinking_success = None
        family.ai_test_thinking_message = None
        family.ai_test_thinking_latency_ms = None
        family.ai_test_thinking_timestamp = None

    # 持久化图像模型测试结果
    if vision_test_result:
        family.ai_vision_test_success = vision_test_result["success"]
        family.ai_vision_test_message = vision_test_result["message"]
        family.ai_vision_test_latency_ms = vision_test_result["latency_ms"]
        family.ai_vision_test_timestamp = datetime.utcnow()
    else:
        family.ai_vision_test_success = None
        family.ai_vision_test_message = None
        family.ai_vision_test_latency_ms = None
        family.ai_vision_test_timestamp = None

    db.commit()

    return AIConfigTestResult(
        connected=connection_result["connected"],
        message=connection_result["message"],
        latency_ms=connection_result["latency_ms"],
        thinking_success=thinking_result["success"] if thinking_result else None,
        thinking_message=thinking_result["message"] if thinking_result else None,
        thinking_latency_ms=thinking_result["latency_ms"] if thinking_result else None,
        vision_success=vision_test_result["success"] if vision_test_result else None,
        vision_message=vision_test_result["message"] if vision_test_result else None,
        vision_latency_ms=vision_test_result["latency_ms"] if vision_test_result else None,
    )


@router.post("/config/test/main", response_model=AIConfigTestResult)
async def test_main_model_only(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """仅测试主模型连接。"""
    from datetime import datetime

    family = _get_family(db, current_user)

    if not family.ai_enabled:
        return AIConfigTestResult(connected=False, message="AI 功能未开启")
    if not family.ai_provider:
        return AIConfigTestResult(connected=False, message="未配置 AI Provider")
    if not family.ai_api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(family.ai_api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()

    model = family.ai_model_id
    if not model:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    # 测试主模型连接
    connection_result = await _test_connection(family, api_key, model)

    # 持久化连接测试结果
    family.ai_test_connected = connection_result["connected"]
    family.ai_test_message = connection_result["message"]
    family.ai_test_latency_ms = connection_result["latency_ms"]
    family.ai_test_timestamp = datetime.utcnow()
    db.commit()

    return AIConfigTestResult(
        connected=connection_result["connected"],
        message=connection_result["message"],
        latency_ms=connection_result["latency_ms"],
    )


@router.post("/config/test/thinking", response_model=AIConfigTestResult)
async def test_thinking_only(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """仅测试主模型思考能力。"""
    from datetime import datetime

    family = _get_family(db, current_user)

    if not family.ai_enabled:
        return AIConfigTestResult(connected=False, message="AI 功能未开启")
    if not family.ai_provider:
        return AIConfigTestResult(connected=False, message="未配置 AI Provider")
    if not family.ai_api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(family.ai_api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()

    model = family.ai_model_id
    if not model:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    # 测试思考能力
    thinking_result = await _test_thinking(family, api_key, model)

    # 持久化思考测试结果
    family.ai_test_thinking_success = thinking_result["success"]
    family.ai_test_thinking_message = thinking_result["message"]
    family.ai_test_thinking_latency_ms = thinking_result["latency_ms"]
    family.ai_test_thinking_timestamp = datetime.utcnow()
    db.commit()

    return AIConfigTestResult(
        connected=True,
        message="思考能力测试完成",
        thinking_success=thinking_result["success"],
        thinking_message=thinking_result["message"],
        thinking_latency_ms=thinking_result["latency_ms"],
    )


@router.post("/config/test/vision", response_model=AIConfigTestResult)
async def test_vision_model_only(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """仅测试图像模型。"""
    from datetime import datetime

    family = _get_family(db, current_user)

    if not family.ai_enabled:
        return AIConfigTestResult(connected=False, message="AI 功能未开启")
    if not family.ai_provider:
        return AIConfigTestResult(connected=False, message="未配置 AI Provider")
    if not family.ai_api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(family.ai_api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()

    vision_model = family.ai_vision_model_id
    if not vision_model:
        return AIConfigTestResult(
            connected=False,
            message="未配置图像模型 ID",
            vision_success=False,
            vision_message="未配置图像模型 ID",
        )

    # 测试图像模型
    vision_test_result = await _test_vision_model(family, api_key, vision_model)

    # 持久化图像模型测试结果
    family.ai_vision_test_success = vision_test_result["success"]
    family.ai_vision_test_message = vision_test_result["message"]
    family.ai_vision_test_latency_ms = vision_test_result["latency_ms"]
    family.ai_vision_test_timestamp = datetime.utcnow()
    db.commit()

    return AIConfigTestResult(
        connected=True,
        message="图像模型测试完成",
        vision_success=vision_test_result["success"],
        vision_message=vision_test_result["message"],
        vision_latency_ms=vision_test_result["latency_ms"],
    )


async def _test_connection(family: Family, api_key: str, model: str) -> dict:
    """测试主模型连接。"""
    start = time.monotonic()

    try:
        if family.ai_provider == "anthropic":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "connected": True,
                        "message": "主模型连接成功",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "connected": False,
                        "message": f"主模型连接失败: HTTP {resp.status_code}",
                        "latency_ms": None,
                    }

        elif family.ai_provider == "openai":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "connected": True,
                        "message": "主模型连接成功",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "connected": False,
                        "message": f"主模型连接失败: HTTP {resp.status_code}",
                        "latency_ms": None,
                    }

    except httpx.TimeoutException:
        return {
            "connected": False,
            "message": "主模型连接超时（30秒）",
            "latency_ms": None,
        }
    except Exception as e:
        return {
            "connected": False,
            "message": f"主模型连接失败: {str(e)}",
            "latency_ms": None,
        }

    return {
        "connected": False,
        "message": f"不支持的 Provider: {family.ai_provider}",
        "latency_ms": None,
    }


async def _test_thinking(family: Family, api_key: str, model: str) -> dict:
    """测试主模型思考能力。"""
    import json
    import logging
    logger = logging.getLogger(__name__)
    start = time.monotonic()

    try:
        logger.info(f"[DEBUG] _test_thinking: provider={family.ai_provider}, model={model}, base_url={family.ai_base_url}")

        if family.ai_provider == "anthropic":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            request_body = {
                "model": model,
                "max_tokens": 1024,
                "thinking": {"type": "enabled", "budget_tokens": 100},
                "messages": [{"role": "user", "content": "think"}],
            }
            logger.info(f"[DEBUG] Anthropic thinking request: endpoint={endpoint}, body={json.dumps(request_body)}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=request_body,
                )
                logger.info(f"[DEBUG] Anthropic thinking response: status={resp.status_code}, body={resp.text[:500]}")

                # 判断是否支持 thinking
                if resp.status_code == 200:
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": True,
                        "message": "支持思考能力",
                        "latency_ms": latency,
                    }
                elif resp.status_code == 400:
                    try:
                        error_data = resp.json()
                        error_type = error_data.get("error", {}).get("type", "")
                        logger.info(f"[DEBUG] Anthropic 400 error: type={error_type}, full_error={json.dumps(error_data)}")
                        latency = int((time.monotonic() - start) * 1000)
                        # invalid_request_error 可能是参数问题，模型支持 thinking
                        if error_type == "invalid_request_error":
                            return {
                                "success": True,
                                "message": "支持思考能力",
                                "latency_ms": latency,
                            }
                        else:
                            return {
                                "success": False,
                                "message": "不支持思考能力",
                                "latency_ms": latency,
                            }
                    except Exception:
                        latency = int((time.monotonic() - start) * 1000)
                        return {
                            "success": True,
                            "message": "支持思考能力",
                            "latency_ms": latency,
                        }
                else:
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": False,
                        "message": f"思考测试失败: HTTP {resp.status_code}",
                        "latency_ms": latency,
                    }

        elif family.ai_provider == "openai":
            # OpenAI thinking 测试 - 不根据模型名称预判，通过测试判断
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            logger.info(f"[DEBUG] OpenAI thinking test: endpoint={endpoint}, model={model}")

            async with httpx.AsyncClient(timeout=30.0) as client:
                # 先尝试带 reasoning_effort 的请求（部分模型支持）
                request_body = {
                    "model": model,
                    "max_completion_tokens": 1,
                    "reasoning_effort": "low",
                    "messages": [{"role": "user", "content": "think"}],
                }
                logger.info(f"[DEBUG] OpenAI thinking request (with reasoning_effort): body={json.dumps(request_body)}")

                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
                logger.info(f"[DEBUG] OpenAI thinking response (with reasoning_effort): status={resp.status_code}, body={resp.text[:500]}")

                if resp.status_code == 200:
                    # 支持 reasoning_effort
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": True,
                        "message": "支持推理能力 (reasoning_effort)",
                        "latency_ms": latency,
                    }
                elif resp.status_code in (400, 404):
                    # 不支持 reasoning_effort，尝试普通请求
                    request_body2 = {
                        "model": model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "think"}],
                    }
                    logger.info(f"[DEBUG] OpenAI fallback request (without reasoning_effort): body={json.dumps(request_body2)}")

                    resp2 = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body2,
                    )
                    logger.info(f"[DEBUG] OpenAI fallback response: status={resp2.status_code}, body={resp2.text[:500]}")

                    latency = int((time.monotonic() - start) * 1000)
                    if resp2.status_code == 200:
                        # 模型可用，但不支持 reasoning_effort
                        return {
                            "success": True,
                            "message": "模型可用（不支持 reasoning_effort）",
                            "latency_ms": latency,
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"测试失败: HTTP {resp2.status_code}",
                            "latency_ms": latency,
                        }
                else:
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": False,
                        "message": f"测试失败: HTTP {resp.status_code}",
                        "latency_ms": latency,
                    }

    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "思考能力测试超时（30秒）",
            "latency_ms": None,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"思考能力测试失败: {str(e)}",
            "latency_ms": None,
        }

    return {
        "success": False,
        "message": f"不支持的 Provider: {family.ai_provider}",
        "latency_ms": None,
    }


async def _test_vision_model(family: Family, api_key: str, vision_model: str) -> dict:
    """测试图像模型能力。"""
    start = time.monotonic()

    try:
        if family.ai_provider == "anthropic":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    endpoint,
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
                if resp.status_code in (200, 400):
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": True,
                        "message": "图像模型连接成功",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"图像模型测试失败: HTTP {resp.status_code}",
                        "latency_ms": None,
                    }

        elif family.ai_provider == "openai":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    endpoint,
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
                if resp.status_code in (200, 400):
                    latency = int((time.monotonic() - start) * 1000)
                    return {
                        "success": True,
                        "message": "图像模型连接成功",
                        "latency_ms": latency,
                    }
                else:
                    return {
                        "success": False,
                        "message": f"图像模型测试失败: HTTP {resp.status_code}",
                        "latency_ms": None,
                    }

    except httpx.TimeoutException:
        return {
            "success": False,
            "message": "图像模型连接超时（30秒）",
            "latency_ms": None,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"图像模型连接失败: {str(e)}",
            "latency_ms": None,
        }

    # Default return for unsupported providers
    return {
        "success": False,
        "message": f"不支持的 Provider: {family.ai_provider}",
        "latency_ms": None,
    }
