"""AI 配置管理路由。"""

import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled, require_owner
from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.family import Family
from app.models.user import User
from app.schemas.ai_config import AIConfigResponse, AIConfigTestResult, AIConfigUpdate
from app.services.ai_crypto import decrypt_api_key, encrypt_api_key, mask_api_key
from app.services.security_log import SecurityEventType, _log_security_event

router = APIRouter(prefix="/ai", tags=["ai-config"])


def _get_family(db: Session, user: User) -> Family:
    family = db.query(Family).filter(Family.id == user.family_id).first()
    if not family:
        raise HTTPException(status_code=404, detail="Family not found")
    return family


@router.get("/config", response_model=AIConfigResponse)
def get_ai_config(
    current_user: User = Depends(get_current_user),
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

    if payload.ai_enabled is not None:
        family.ai_enabled = payload.ai_enabled
    if payload.ai_provider is not None:
        family.ai_provider = payload.ai_provider
    if payload.ai_base_url is not None or "ai_base_url" in (payload.model_fields_set or set()):
        family.ai_base_url = payload.ai_base_url
    if payload.ai_model_id is not None or "ai_model_id" in (payload.model_fields_set or set()):
        family.ai_model_id = payload.ai_model_id
    if payload.ai_vision_model_id is not None or "ai_vision_model_id" in (payload.model_fields_set or set()):
        family.ai_vision_model_id = payload.ai_vision_model_id
    if payload.ai_api_key is not None:
        if payload.ai_api_key == "":
            # 清空 API Key
            family.ai_api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.ai_api_key)
            if encrypted is None:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AI_ENCRYPTION_KEY 未配置，无法安全存储 API Key",
                )
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


@router.post("/config/test", response_model=AIConfigTestResult)
async def test_ai_config(
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试 AI API Key 连通性（仅 owner）。"""
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

    start = time.monotonic()
    try:
        if family.ai_provider == "anthropic":
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": "claude-haiku-4-5",
                        "max_tokens": 1,
                        "messages": [{"role": "user", "content": "hi"}],
                    },
                )
                if resp.status_code in (200, 400):  # 400 也说明 key 有效（参数错误）
                    latency = int((time.monotonic() - start) * 1000)
                    return AIConfigTestResult(success=True, message="连接成功", latency_ms=latency)
                else:
                    return AIConfigTestResult(success=False, message=f"API 返回错误: {resp.status_code}")

        elif family.ai_provider == "openai":
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if resp.status_code == 200:
                    latency = int((time.monotonic() - start) * 1000)
                    return AIConfigTestResult(success=True, message="连接成功", latency_ms=latency)
                else:
                    return AIConfigTestResult(success=False, message=f"API 返回错误: {resp.status_code}")

        return AIConfigTestResult(success=False, message=f"不支持的 Provider: {family.ai_provider}")

    except httpx.TimeoutException:
        return AIConfigTestResult(success=False, message="连接超时（10秒），请检查网络")
    except Exception as e:
        return AIConfigTestResult(success=False, message=f"连接失败: {str(e)}")
