"""Schemas for family/user configurable settings."""
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class SettingDefinitionResponse(BaseModel):
    """Metadata about a setting (returned by GET /definitions)."""
    type: Literal["int", "float", "string", "bool"]
    default: int | float | str | bool
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    allowed_values: list[str] | None = None
    label_key: str
    description_key: str | None = None


class FamilyConfigUpdate(BaseModel):
    """PATCH body for family config."""
    settings: dict[str, Any]

    @field_validator("settings")
    @classmethod
    def _non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("settings must not be empty")
        return v


class UserConfigUpdate(BaseModel):
    """PATCH body for user config."""
    settings: dict[str, Any]

    @field_validator("settings")
    @classmethod
    def _non_empty(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("settings must not be empty")
        return v


class FamilyConfigResponse(BaseModel):
    """All family settings merged with defaults."""
    ai_cache_ttl_report: int
    ai_cache_ttl_finance_coach: int
    ai_cache_ttl_dashboard_narrative: int
    dashboard_min_asset_count: int
    dashboard_min_history_months: int
    dashboard_expiring_days_threshold: int
    scheduled_monthly_report_day: int
    scheduled_monthly_report_hour: int
    scheduled_weekly_scan_day: int
    scheduled_weekly_scan_hour: int
    literacy_report_day: int
    literacy_report_hour: int
    ai_cache_ttl_literacy_weekly_report: int


class UserConfigResponse(BaseModel):
    """All user settings merged with defaults."""
    dashboard_trend_period: str
    activity_feed_page_size: int
    onboarding_guide_version: int
    onboarding_attempts: int
    onboarding_completions: int
