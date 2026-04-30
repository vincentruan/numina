"""AI 配置管理路由。"""

import logging
import time
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_owner
from app.auth.deps import require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_provider_config import AIProviderConfig, AIProviderTestResult
from app.models.user import User
from app.schemas.ai_config import (
    AIConfigCreate,
    AIConfigListResponse,
    AIConfigResponse,
    AIConfigTestResult,
    AIConfigUpdate,
    AIProviderTestResultResponse,
)
from app.services.ai_crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.security_log import _log_security_event
from app.services.vision_test_image import (
    get_expected_ocr_text,
    get_test_image_data_url,
)

router = APIRouter(prefix="/ai", tags=["ai-config"])

logger = logging.getLogger(__name__)


def _build_endpoint(base_url: str | None, default_base: str, path: str) -> str:
    """智能拼接 endpoint，避免 /v1 重复。"""
    base = (base_url or default_base).rstrip("/")
    if path.startswith("/v1") and base.endswith("/v1"):
        return f"{base}{path[3:]}"
    else:
        return f"{base}{path}"


def _cfg_to_response(cfg: AIProviderConfig, test_results: list, api_key_masked: str | None) -> AIConfigResponse:
    return AIConfigResponse(
        id=cfg.id,
        name=cfg.name,
        provider=cfg.provider,
        ai_api_key_masked=api_key_masked,
        base_url=cfg.base_url,
        model_id=cfg.model_id,
        vision_model_id=cfg.vision_model_id,
        is_active=cfg.is_active,
        test_results=[AIProviderTestResultResponse.model_validate(r) for r in test_results],
    )


@router.get("/config", response_model=AIConfigListResponse)
def get_ai_configs(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AIConfigListResponse:
    """获取当前家庭所有 AI 配置（所有成员可查看）。"""
    configs = (
        db.query(AIProviderConfig)
        .filter(AIProviderConfig.family_id == current_user.family_id)
        .order_by(AIProviderConfig.created_at)
        .all()
    )
    result = []
    for cfg in configs:
        test_results = (
            db.query(AIProviderTestResult)
            .filter(AIProviderTestResult.config_id == cfg.id)
            .all()
        )
        api_key_masked = None
        if cfg.api_key_encrypted:
            decrypted = decrypt_api_key(cfg.api_key_encrypted)
            if decrypted:
                api_key_masked = mask_api_key(decrypted)
        result.append(_cfg_to_response(cfg, test_results, api_key_masked))
    return AIConfigListResponse(configs=result)


@router.post("/config", response_model=AIConfigResponse, status_code=201)
def create_ai_config(
    payload: AIConfigCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """创建新 AI 配置（仅 owner）。"""
    if payload.is_active:
        db.query(AIProviderConfig).filter(
            AIProviderConfig.family_id == current_user.family_id
        ).update({"is_active": False})

    encrypted = None
    if payload.ai_api_key:
        encrypted = encrypt_api_key(payload.ai_api_key)
        if encrypted is None:
            raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    cfg = AIProviderConfig(
        family_id=current_user.family_id,
        name=payload.name,
        provider=payload.provider,
        api_key_encrypted=encrypted,
        base_url=payload.base_url,
        model_id=payload.model_id,
        vision_model_id=payload.vision_model_id,
        is_active=payload.is_active,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)

    _log_security_event(
        "ai_config_created",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=cfg.provider,
    )

    return _cfg_to_response(cfg, [], None)


@router.put("/config/{config_id}", response_model=AIConfigResponse)
def update_ai_config(
    config_id: int,
    payload: AIConfigUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigResponse:
    """更新 AI 配置（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    if payload.is_active is True:
        db.query(AIProviderConfig).filter(
            AIProviderConfig.family_id == current_user.family_id,
            AIProviderConfig.id != config_id,
        ).update({"is_active": False})

    if payload.name is not None:
        cfg.name = payload.name
    if payload.provider is not None:
        cfg.provider = payload.provider
    if payload.base_url is not None:
        cfg.base_url = payload.base_url
    if payload.model_id is not None:
        cfg.model_id = payload.model_id
    if payload.vision_model_id is not None:
        cfg.vision_model_id = payload.vision_model_id
    if payload.is_active is not None:
        cfg.is_active = payload.is_active
    if payload.ai_api_key is not None:
        if payload.ai_api_key == "":
            cfg.api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.ai_api_key)
            if encrypted is None:
                raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)
            cfg.api_key_encrypted = encrypted
        # 清空测试结果（API Key 变更后需重新测试）
        db.query(AIProviderTestResult).filter_by(config_id=cfg.id).delete()

    db.commit()
    db.refresh(cfg)

    _log_security_event(
        "ai_config_updated",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=cfg.provider,
    )

    test_results = db.query(AIProviderTestResult).filter_by(config_id=cfg.id).all()
    api_key_masked = None
    if cfg.api_key_encrypted:
        decrypted = decrypt_api_key(cfg.api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)

    return _cfg_to_response(cfg, test_results, api_key_masked)


@router.delete("/config/{config_id}", status_code=204)
def delete_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """删除 AI 配置（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    db.query(AIProviderTestResult).filter_by(config_id=cfg.id).delete()
    db.delete(cfg)
    db.commit()


@router.post("/config/{config_id}/test", response_model=AIConfigTestResult)
async def test_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试指定 AI 配置的连通性和模型能力（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    if not cfg.api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(cfg.api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()
    model = cfg.model_id
    if not model:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    def _upsert_test(test_type: str, success: bool | None, message: str, latency_ms: int | None) -> None:
        existing = db.query(AIProviderTestResult).filter_by(config_id=cfg.id, test_type=test_type).first()
        if existing:
            existing.success = success
            existing.message = message
            existing.latency_ms = latency_ms
            existing.tested_at = datetime.utcnow()
        else:
            db.add(AIProviderTestResult(
                config_id=cfg.id,
                test_type=test_type,
                success=success,
                message=message,
                latency_ms=latency_ms,
            ))
        db.commit()

    class _CfgProxy:
        def __init__(self, c: AIProviderConfig) -> None:
            self.ai_provider = c.provider
            self.ai_base_url = c.base_url
            self.ai_model_id = c.model_id
            self.ai_vision_model_id = c.vision_model_id

    proxy = _CfgProxy(cfg)
    connection_result = await _test_connection(proxy, api_key, model)

    thinking_result = None
    if connection_result["connected"]:
        thinking_result = await _test_thinking(proxy, api_key, model)

    vision_test_result = None
    if cfg.vision_model_id and cfg.vision_model_id != model:
        vision_test_result = await _test_vision_model(proxy, api_key, cfg.vision_model_id)

    _upsert_test("main", connection_result["connected"], connection_result["message"], connection_result["latency_ms"])
    if thinking_result:
        _upsert_test("thinking", thinking_result["success"], thinking_result["message"], thinking_result["latency_ms"])
    if vision_test_result:
        _upsert_test("vision", vision_test_result["success"], vision_test_result["message"], vision_test_result["latency_ms"])

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


async def _test_connection(family: object, api_key: str, model: str) -> dict:
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
                    return {"connected": True, "message": "主模型连接成功", "latency_ms": latency}
                else:
                    return {"connected": False, "message": f"主模型连接失败: HTTP {resp.status_code}", "latency_ms": None}

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
                    return {"connected": True, "message": "主模型连接成功", "latency_ms": latency}
                else:
                    return {"connected": False, "message": f"主模型连接失败: HTTP {resp.status_code}", "latency_ms": None}

    except httpx.TimeoutException:
        return {"connected": False, "message": "主模型连接超时（30秒）", "latency_ms": None}
    except Exception as e:
        return {"connected": False, "message": f"主模型连接失败: {str(e)}", "latency_ms": None}

    return {"connected": False, "message": f"不支持的 Provider: {family.ai_provider}", "latency_ms": None}


async def _test_thinking(family: object, api_key: str, model: str) -> dict:
    """测试主模型思考能力。"""
    start = time.monotonic()

    try:
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

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=request_body,
                )

                if resp.status_code == 200:
                    latency = int((time.monotonic() - start) * 1000)
                    return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                elif resp.status_code == 400:
                    try:
                        error_data = resp.json()
                        error_type = error_data.get("error", {}).get("type", "")
                        latency = int((time.monotonic() - start) * 1000)
                        if error_type == "invalid_request_error":
                            return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                        else:
                            return {"success": False, "message": "不支持思考能力", "latency_ms": latency}
                    except Exception:
                        latency = int((time.monotonic() - start) * 1000)
                        return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                else:
                    latency = int((time.monotonic() - start) * 1000)
                    return {"success": False, "message": f"思考测试失败: HTTP {resp.status_code}", "latency_ms": latency}

        elif family.ai_provider == "openai":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )

            async with httpx.AsyncClient(timeout=120.0) as client:
                request_body = {
                    "model": model,
                    "max_completion_tokens": 1,
                    "reasoning_effort": "low",
                    "messages": [{"role": "user", "content": "think"}],
                }

                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )

                if resp.status_code == 200:
                    latency = int((time.monotonic() - start) * 1000)
                    return {"success": True, "message": "支持推理能力 (reasoning_effort)", "latency_ms": latency}
                elif resp.status_code in (400, 404):
                    request_body2 = {
                        "model": model,
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "think"}],
                    }

                    resp2 = await client.post(
                        endpoint,
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json=request_body2,
                    )

                    latency = int((time.monotonic() - start) * 1000)
                    if resp2.status_code == 200:
                        return {"success": True, "message": "模型可用（不支持 reasoning_effort）", "latency_ms": latency}
                    else:
                        return {"success": False, "message": f"测试失败: HTTP {resp2.status_code}", "latency_ms": latency}
                else:
                    latency = int((time.monotonic() - start) * 1000)
                    return {"success": False, "message": f"测试失败: HTTP {resp.status_code}", "latency_ms": latency}

    except httpx.TimeoutException:
        return {"success": False, "message": "思考能力测试超时（120秒）", "latency_ms": None}
    except Exception as e:
        return {"success": False, "message": f"思考能力测试失败: {str(e)}", "latency_ms": None}

    return {"success": False, "message": f"不支持的 Provider: {family.ai_provider}", "latency_ms": None}


async def _test_vision_model(family: object, api_key: str, vision_model: str) -> dict:
    """测试图像模型能力。"""
    start = time.monotonic()

    try:
        if family.ai_provider == "anthropic":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                    return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
                else:
                    return {"success": False, "message": f"图像模型测试失败: HTTP {resp.status_code}", "latency_ms": None}

        elif family.ai_provider == "openai":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            async with httpx.AsyncClient(timeout=120.0) as client:
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
                                        "image_url": {"url": "https://httpbin.org/image/png"},
                                    },
                                ],
                            }
                        ],
                    },
                )
                if resp.status_code in (200, 400):
                    latency = int((time.monotonic() - start) * 1000)
                    return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
                else:
                    return {"success": False, "message": f"图像模型测试失败: HTTP {resp.status_code}", "latency_ms": None}

    except httpx.TimeoutException:
        return {"success": False, "message": "图像模型连接超时（120秒）", "latency_ms": None}
    except Exception as e:
        return {"success": False, "message": f"图像模型连接失败: {str(e)}", "latency_ms": None}

    return {"success": False, "message": f"不支持的 Provider: {family.ai_provider}", "latency_ms": None}


async def _test_vision_text_ocr(family: object, api_key: str, vision_model: str) -> dict:
    """测试图像模型 OCR 文本准确度。"""
    start = time.monotonic()
    test_image_url = get_test_image_data_url()
    expected_text = get_expected_ocr_text()

    try:
        if family.ai_provider == "anthropic":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.anthropic.com", "/v1/messages"
            )
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": vision_model,
                        "max_tokens": 100,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "请识别图片中的文字内容"},
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": "image/png",
                                            "data": test_image_url.replace("data:image/png;base64,", ""),
                                        },
                                    },
                                ],
                            }
                        ],
                    },
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    result = resp.json()
                    recognized_text = result["content"][0]["text"]
                    accuracy = _calculate_ocr_accuracy(recognized_text, expected_text)
                    if accuracy >= 0.8:
                        return {"success": True, "message": f"OCR 准确度 {accuracy:.0%}", "latency_ms": latency}
                    else:
                        return {"success": False, "message": f"OCR 准确度 {accuracy:.0%}，低于 80% 阈值", "latency_ms": latency}
                else:
                    return {"success": False, "message": f"OCR 测试失败: HTTP {resp.status_code}", "latency_ms": latency}

        elif family.ai_provider == "openai":
            endpoint = _build_endpoint(
                family.ai_base_url, "https://api.openai.com", "/v1/chat/completions"
            )
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": vision_model,
                        "max_tokens": 100,
                        "messages": [
                            {
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "请识别图片中的文字内容"},
                                    {"type": "image_url", "image_url": {"url": test_image_url}},
                                ],
                            }
                        ],
                    },
                )
                latency = int((time.monotonic() - start) * 1000)
                if resp.status_code == 200:
                    result = resp.json()
                    recognized_text = result["choices"][0]["message"]["content"]
                    accuracy = _calculate_ocr_accuracy(recognized_text, expected_text)
                    if accuracy >= 0.8:
                        return {"success": True, "message": f"OCR 准确度 {accuracy:.0%}", "latency_ms": latency}
                    else:
                        return {"success": False, "message": f"OCR 准确度 {accuracy:.0%}，低于 80% 阈值", "latency_ms": latency}
                else:
                    return {"success": False, "message": f"OCR 测试失败: HTTP {resp.status_code}", "latency_ms": latency}

    except httpx.TimeoutException:
        return {"success": False, "message": "OCR 测试超时（120秒）", "latency_ms": None}
    except Exception as e:
        return {"success": False, "message": f"OCR 测试失败: {str(e)}", "latency_ms": None}

    return {"success": False, "message": f"不支持的 Provider: {family.ai_provider}", "latency_ms": None}


def _calculate_ocr_accuracy(recognized: str, expected: str) -> float:
    """计算 OCR 识别准确度（最长公共子序列）。"""
    recognized_clean = recognized.strip()
    expected_clean = expected.strip()

    if not expected_clean:
        return 1.0 if not recognized_clean else 0.0

    if recognized_clean == expected_clean:
        return 1.0

    m, n = len(recognized_clean), len(expected_clean)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if recognized_clean[i - 1] == expected_clean[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    lcs_length = dp[m][n]
    return lcs_length / n
