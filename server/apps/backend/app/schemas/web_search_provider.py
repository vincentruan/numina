"""Web Search Provider schemas for CRUD operations."""

from datetime import datetime

from pydantic import BaseModel

from apps.backend.app.schemas.base import SnowflakeBase


class WebSearchProviderTemplate(BaseModel):
    """Provider template from registry (static metadata)."""
    provider_name: str
    display_name: str
    requires_api_key: bool
    config_fields: list[dict]
    docs_url: str | None = None
    note: str | None = None


class WebSearchProviderCreate(BaseModel):
    """Create request for a new family web search provider."""
    provider_name: str
    api_key: str | None = None
    max_results: int = 5
    display_name: str | None = None
    display_order: int | None = None


class WebSearchProviderUpdate(BaseModel):
    """Update request for an existing provider."""
    api_key: str | None = None
    max_results: int | None = None
    display_name: str | None = None
    display_order: int | None = None


class WebSearchProviderResponse(SnowflakeBase):
    """Response schema for a family web search provider."""
    id: int
    family_id: int
    provider_name: str
    display_name: str | None
    is_enabled: bool
    display_order: int
    max_results: int
    # Circuit breaker fields
    circuit_state: str = "closed"
    circuit_reason: str | None = None
    recovery_schedule: str | None = None
    last_failure_type: str | None = None
    half_open_window_start: datetime | None = None
    failure_count: int = 0
    last_failure_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebSearchStatusResponse(BaseModel):
    """Status response showing enabled count and availability."""
    has_web_search: bool
    enabled_count: int