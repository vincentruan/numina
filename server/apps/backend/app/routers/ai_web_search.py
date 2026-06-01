"""Web Search Provider CRUD router."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.models.user import User
from apps.backend.app.schemas.web_search_provider import (
    WebSearchProviderCreate,
    WebSearchProviderResponse,
    WebSearchProviderTemplate,
    WebSearchProviderUpdate,
    WebSearchStatusResponse,
)
from apps.backend.app.services.ai_crypto import encrypt_api_key
from apps.backend.app.services.security_log import _log_security_event
from apps.backend.app.services.web_search_provider_registry import (
    get_provider_template,
    list_provider_templates,
)

router = APIRouter(prefix="/ai/web-search", tags=["ai-web-search"])
logger = logging.getLogger(__name__)


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
    return [WebSearchProviderResponse.model_validate(p) for p in providers]


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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="不支持的搜索引擎类型",
        )

    # Check if API key is required
    if template["requires_api_key"] and not payload.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该搜索引擎需要 API Key",
        )

    # Encrypt API key if provided
    api_key_encrypted = None
    if payload.api_key:
        api_key_encrypted = encrypt_api_key(payload.api_key)
        if api_key_encrypted is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="加密服务不可用",
            )

    # Auto-assign display_order if not provided
    display_order = payload.display_order
    if display_order is None:
        max_order = (
            db.query(FamilyWebSearchProvider)
            .filter(FamilyWebSearchProvider.family_id == current_user.family_id)
            .count()
        )
        display_order = max_order

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

    return WebSearchProviderResponse.model_validate(provider)


@router.put("/{provider_id}", response_model=WebSearchProviderResponse)
def update_provider(
    provider_id: str,  # String from URL, convert to int
    payload: WebSearchProviderUpdate,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Update a web search provider (owner only)."""
    # Convert provider_id from string to int
    try:
        pid = int(provider_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的搜索引擎配置 ID",
        ) from None

    # Find provider
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == pid,
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="搜索引擎配置不存在",
        )

    # Update fields
    if payload.api_key is not None:
        if payload.api_key == "":
            provider.api_key_encrypted = None
        else:
            encrypted = encrypt_api_key(payload.api_key)
            if encrypted is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="加密服务不可用",
                )
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

    return WebSearchProviderResponse.model_validate(provider)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(
    provider_id: str,  # String from URL, convert to int
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    """Delete a web search provider (owner only)."""
    # Convert provider_id from string to int
    try:
        pid = int(provider_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的搜索引擎配置 ID",
        ) from None

    # Find provider
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == pid,
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="搜索引擎配置不存在",
        )

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
    provider_id: str,  # String from URL, convert to int
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Enable a web search provider (owner only)."""
    # Convert provider_id from string to int
    try:
        pid = int(provider_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的搜索引擎配置 ID",
        ) from None

    # Find provider
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == pid,
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="搜索引擎配置不存在",
        )

    provider.is_enabled = True
    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_enabled",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return WebSearchProviderResponse.model_validate(provider)


@router.post("/{provider_id}/disable", response_model=WebSearchProviderResponse)
def disable_provider(
    provider_id: str,  # String from URL, convert to int
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> WebSearchProviderResponse:
    """Disable a web search provider (owner only)."""
    # Convert provider_id from string to int
    try:
        pid = int(provider_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的搜索引擎配置 ID",
        ) from None

    # Find provider
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == pid,
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="搜索引擎配置不存在",
        )

    provider.is_enabled = False
    db.commit()
    db.refresh(provider)

    _log_security_event(
        "web_search_provider_disabled",
        user_id=current_user.id,
        family_id=current_user.family_id,
        provider=provider.provider_name,
    )

    return WebSearchProviderResponse.model_validate(provider)


@router.post("/{provider_id}/test")
def test_provider(
    provider_id: str,  # String from URL, convert to int
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> dict:
    """Test web search provider connectivity (stub for now, owner only)."""
    # Convert provider_id from string to int
    try:
        pid = int(provider_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的搜索引擎配置 ID",
        ) from None

    # Find provider
    provider = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.id == pid,
            FamilyWebSearchProvider.family_id == current_user.family_id,
        )
        .first()
    )
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="搜索引擎配置不存在",
        )

    # Stub implementation - will be implemented in Task 6
    return {
        "success": False,
        "message": "测试功能尚未实现",
    }