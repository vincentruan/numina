"""Web Search Provider CRUD router."""

import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.user import User
from apps.backend.app.schemas.web_search_provider import (
    WebSearchKeyRevealResponse,
    WebSearchProviderCreate,
    WebSearchProviderResponse,
    WebSearchProviderTemplate,
    WebSearchProviderUpdate,
    WebSearchStatusResponse,
    WebSearchTestResponse,
)
from apps.backend.app.services.ai_crypto import (
    decrypt_api_key,
    encrypt_api_key,
    mask_api_key,
)
from apps.backend.app.services.security_log import _log_security_event
from apps.backend.app.services.web_search_provider_registry import (
    get_provider_template,
    list_provider_templates,
)

router = APIRouter(prefix="/ai/web-search", tags=["ai-web-search"])
logger = logging.getLogger(__name__)


def _get_provider_or_404(provider_id: int, family_id: int, db: Session) -> FamilyWebSearchProvider:
    """Fetch provider by id, raising 404 if not found."""
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == provider_id,
            FamilyWebSearchProvider.family_id == family_id,
        )
        .first()
    )
    if not provider:
        raise AppError(ErrorCode.NOT_FOUND, "搜索引擎配置不存在")
    return provider


def _provider_to_response(provider: FamilyWebSearchProvider) -> WebSearchProviderResponse:
    """Convert ORM model to response schema with masked API key."""
    has_api_key = provider.api_key_encrypted is not None
    api_key_masked = None
    if provider.api_key_encrypted:
        decrypted = decrypt_api_key(provider.api_key_encrypted)
        if decrypted:
            api_key_masked = mask_api_key(decrypted)
    return WebSearchProviderResponse(
        id=provider.id,
        family_id=provider.family_id,
        provider_name=provider.provider_name,
        display_name=provider.display_name,
        is_enabled=provider.is_enabled,
        display_order=provider.display_order,
        max_results=provider.max_results,
        has_api_key=has_api_key,
        api_key_masked=api_key_masked,
        circuit_state=provider.circuit_state,
        circuit_reason=provider.circuit_reason,
        recovery_schedule=provider.recovery_schedule,
        last_failure_type=provider.last_failure_type,
        half_open_window_start=provider.half_open_window_start,
        failure_count=provider.failure_count,
        last_failure_at=provider.last_failure_at,
        created_at=provider.created_at,
        updated_at=provider.updated_at,
    )


@router.get("/templates", response_model=list[WebSearchProviderTemplate])
def list_templates(
    current_user: User = Depends(require_adult),
) -> list[WebSearchProviderTemplate]:
    """Return all provider templates from registry (all adult members)."""
    templates = list_provider_templates()
    return [WebSearchProviderTemplate(**t) for t in templates]


@router.get("/status", response_model=WebSearchStatusResponse)
def get_status(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> WebSearchStatusResponse:
    """Return web search availability status for the family."""
    enabled_count = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == current_user.family_id,
            FamilyWebSearchProvider.is_enabled.is_(True),
            FamilyWebSearchProvider.circuit_state != "open",
        )
        .count()
    )
    return WebSearchStatusResponse(
        has_web_search=enabled_count > 0,
        enabled_count=enabled_count,
    )


@router.get("", response_model=list[WebSearchProviderResponse])
def list_providers(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[WebSearchProviderResponse]:
    """List all web search providers for the family (all adult members)."""
    providers = (
        db.query(FamilyWebSearchProvider)
        .filter(FamilyWebSearchProvider.family_id == current_user.family_id)
        .order_by(FamilyWebSearchProvider.display_order)
        .all()
    )
    return [_provider_to_response(p) for p in providers]


@router.post("", response_model=WebSearchProviderResponse, status_code=201)
def create_provider(
    payload: WebSearchProviderCreate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Create a new web search provider (owner only)."""
    # Validate provider_name against registry
    template = get_provider_template(payload.provider_name)
    if not template:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不支持的搜索引擎类型")

    # Check if API key is required
    if template["requires_api_key"] and not payload.api_key:
        raise AppError(ErrorCode.VALIDATION_ERROR, "该搜索引擎需要 API Key")

    # Encrypt API key if provided
    api_key_encrypted = None
    if payload.api_key:
        api_key_encrypted = encrypt_api_key(payload.api_key)
        if api_key_encrypted is None:
            raise AppError(ErrorCode.INTERNAL_ERROR, "加密服务不可用")

    # Auto-assign display_order if not provided
    display_order = payload.display_order
    if display_order is None:
        max_order = (
            db.query(func.coalesce(func.max(FamilyWebSearchProvider.display_order), -1))
            .filter(FamilyWebSearchProvider.family_id == current_user.family_id)
            .scalar()
        )
        display_order = max_order + 1

    # Create provider
    provider = FamilyWebSearchProvider(
        family_id=current_user.family_id,
        provider_name=payload.provider_name,
        display_name=payload.display_name or template["display_name"],
        api_key_encrypted=api_key_encrypted,
        max_results=payload.max_results,
        display_order=display_order,
        is_enabled=False,  # Disabled by default
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_created",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=payload.provider_name,
    )

    return _provider_to_response(provider)


@router.put("/{provider_id}", response_model=WebSearchProviderResponse)
def update_provider(
    provider_id: int,
    payload: WebSearchProviderUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Update a web search provider (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)

    # Update fields
    if payload.api_key is not None:
        if payload.api_key == "":
            provider.api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.api_key)
            if encrypted is None:
                raise AppError(ErrorCode.INTERNAL_ERROR, "加密服务不可用")
            provider.api_key_encrypted = encrypted

    if payload.max_results is not None:
        provider.max_results = payload.max_results

    if payload.display_name is not None:
        provider.display_name = payload.display_name

    if payload.display_order is not None:
        provider.display_order = payload.display_order

    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_updated",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return _provider_to_response(provider)


@router.post("/{provider_id}/reveal-key", response_model=WebSearchKeyRevealResponse)
def reveal_provider_key(
    provider_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchKeyRevealResponse:
    """Reveal the decrypted API key for a web search provider (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)

    if not provider.api_key_encrypted:
        raise AppError(ErrorCode.VALIDATION_ERROR, "该搜索引擎未配置 API Key")

    decrypted = decrypt_api_key(provider.api_key_encrypted)
    if not decrypted:
        raise AppError(ErrorCode.INTERNAL_ERROR, "解密服务不可用")

    _log_security_event(
        "web_search_key_revealed",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return WebSearchKeyRevealResponse(api_key=decrypted)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(
    provider_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """Delete a web search provider (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)

    db.delete(provider)
    db.commit()

    _log_security_event(
        "web_search_provider_deleted",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )


@router.post("/{provider_id}/enable", response_model=WebSearchProviderResponse)
def enable_provider(
    provider_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Enable a web search provider (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)

    # Validate API key requirement
    template = get_provider_template(provider.provider_name)
    if template and template.get("requires_api_key") and not provider.api_key_encrypted:
        raise AppError(ErrorCode.VALIDATION_ERROR, "该搜索引擎需要 API Key 才能启用")

    provider.is_enabled = True
    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_enabled",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return _provider_to_response(provider)


@router.post("/{provider_id}/disable", response_model=WebSearchProviderResponse)
def disable_provider(
    provider_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Disable a web search provider (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)

    provider.is_enabled = False
    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_disabled",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return _provider_to_response(provider)


@router.post("/{provider_id}/test", response_model=WebSearchTestResponse)
def test_provider(
    provider_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchTestResponse:
    """Test web search provider connectivity (owner only)."""
    provider = _get_provider_or_404(provider_id, current_user.family_id, db)
    template = get_provider_template(provider.provider_name)

    if not template:
        return WebSearchTestResponse(success=False, message="未知的搜索引擎类型")

    provider_name = provider.provider_name

    try:
        # Test based on provider type
        if provider_name == "tavily":
            return _test_tavily(provider)
        elif provider_name == "ddg_search":
            return _test_duckduckgo(provider)
        elif provider_name == "exa":
            return _test_exa(provider)
        elif provider_name == "serper":
            return _test_serper(provider)
        elif provider_name == "firecrawl":
            return _test_firecrawl(provider)
        else:
            return WebSearchTestResponse(success=False, message="该搜索引擎暂不支持连通性测试")
    except Exception as e:
        logger.exception("Web search provider test failed")
        return WebSearchTestResponse(success=False, message=str(e))


def _test_tavily(provider: FamilyWebSearchProvider) -> WebSearchTestResponse:
    """Test Tavily API connectivity."""
    if not provider.api_key_encrypted:
        return WebSearchTestResponse(success=False, message="未配置 API Key")

    api_key = decrypt_api_key(provider.api_key_encrypted)
    if not api_key:
        return WebSearchTestResponse(success=False, message="解密 API Key 失败")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": "test",
                    "max_results": 1,
                },
            )
            if 200 <= resp.status_code < 300:
                return WebSearchTestResponse(success=True, message="连接成功")
            elif resp.status_code == 401:
                return WebSearchTestResponse(success=False, message="API Key 无效")
            else:
                return WebSearchTestResponse(
                    success=False, message=f"API 返回错误: {resp.status_code}"
                )
    except httpx.TimeoutException:
        return WebSearchTestResponse(success=False, message="连接超时")
    except httpx.RequestError as e:
        return WebSearchTestResponse(success=False, message=f"网络错误: {str(e)}")


def _test_duckduckgo(provider: FamilyWebSearchProvider) -> WebSearchTestResponse:
    """Test DuckDuckGo connectivity (no API key required)."""
    try:
        with httpx.Client(timeout=10.0) as client:
            # DuckDuckGo HTML search endpoint - just verify the service is reachable
            resp = client.get("https://duckduckgo.com/", params={"q": "test"})
            if 200 <= resp.status_code < 300:
                return WebSearchTestResponse(success=True, message="连接成功")
            else:
                return WebSearchTestResponse(
                    success=False, message=f"服务返回错误: {resp.status_code}"
                )
    except httpx.TimeoutException:
        return WebSearchTestResponse(success=False, message="连接超时")
    except httpx.RequestError as e:
        return WebSearchTestResponse(success=False, message=f"网络错误: {str(e)}")


def _test_exa(provider: FamilyWebSearchProvider) -> WebSearchTestResponse:
    """Test Exa API connectivity."""
    if not provider.api_key_encrypted:
        return WebSearchTestResponse(success=False, message="未配置 API Key")

    api_key = decrypt_api_key(provider.api_key_encrypted)
    if not api_key:
        return WebSearchTestResponse(success=False, message="解密 API Key 失败")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://api.exa.ai/search",
                headers={"x-api-key": api_key},
                json={"query": "test", "numResults": 1},
            )
            if 200 <= resp.status_code < 300:
                return WebSearchTestResponse(success=True, message="连接成功")
            elif resp.status_code == 401:
                return WebSearchTestResponse(success=False, message="API Key 无效")
            else:
                return WebSearchTestResponse(
                    success=False, message=f"API 返回错误: {resp.status_code}"
                )
    except httpx.TimeoutException:
        return WebSearchTestResponse(success=False, message="连接超时")
    except httpx.RequestError as e:
        return WebSearchTestResponse(success=False, message=f"网络错误: {str(e)}")


def _test_serper(provider: FamilyWebSearchProvider) -> WebSearchTestResponse:
    """Test Serper (Google Search) API connectivity."""
    if not provider.api_key_encrypted:
        return WebSearchTestResponse(success=False, message="未配置 API Key")

    api_key = decrypt_api_key(provider.api_key_encrypted)
    if not api_key:
        return WebSearchTestResponse(success=False, message="解密 API Key 失败")

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": api_key},
                json={"q": "test"},
            )
            if 200 <= resp.status_code < 300:
                return WebSearchTestResponse(success=True, message="连接成功")
            elif resp.status_code == 401:
                return WebSearchTestResponse(success=False, message="API Key 无效")
            else:
                return WebSearchTestResponse(
                    success=False, message=f"API 返回错误: {resp.status_code}"
                )
    except httpx.TimeoutException:
        return WebSearchTestResponse(success=False, message="连接超时")
    except httpx.RequestError as e:
        return WebSearchTestResponse(success=False, message=f"网络错误: {str(e)}")


def _test_firecrawl(provider: FamilyWebSearchProvider) -> WebSearchTestResponse:
    """Test Firecrawl API connectivity."""
    if not provider.api_key_encrypted:
        return WebSearchTestResponse(success=False, message="未配置 API Key")

    api_key = decrypt_api_key(provider.api_key_encrypted)
    if not api_key:
        return WebSearchTestResponse(success=False, message="解密 API Key 失败")

    try:
        with httpx.Client(timeout=10.0) as client:
            # Firecrawl has a /status endpoint to check API health
            resp = client.get(
                "https://api.firecrawl.dev/v1/status",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            if 200 <= resp.status_code < 300:
                return WebSearchTestResponse(success=True, message="连接成功")
            elif resp.status_code == 401:
                return WebSearchTestResponse(success=False, message="API Key 无效")
            else:
                return WebSearchTestResponse(
                    success=False, message=f"API 返回错误: {resp.status_code}"
                )
    except httpx.TimeoutException:
        return WebSearchTestResponse(success=False, message="连接超时")
    except httpx.RequestError as e:
        return WebSearchTestResponse(success=False, message=f"网络错误: {str(e)}")