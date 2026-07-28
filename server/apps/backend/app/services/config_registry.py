"""Code-side registry of setting definitions (defaults, types, validation).

Each known key has a SettingDefinition with type, default, boundaries.
The registry is the single source of truth for:
  - default values (when no DB row exists)
  - validation rules (type, min/max, allowed_values)
  - frontend rendering metadata (label_key, description_key)
"""
from typing import Any, Literal

from pydantic import BaseModel


class SettingDefinition(BaseModel):
    type: Literal["int", "float", "string", "bool"]
    default: int | float | str | bool
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    allowed_values: list[str] | None = None
    label_key: str = ""
    description_key: str | None = None


FAMILY_SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    # --- AI cache TTLs (minutes) ---
    "ai_cache_ttl_report": SettingDefinition(
        type="int", default=60, min=5, max=480, step=5,
        label_key="familyConfig.aiCacheTtlReport",
        description_key="familyConfig.aiCacheTtlReportDesc",
    ),
    "ai_cache_ttl_finance_coach": SettingDefinition(
        type="int", default=480, min=60, max=1440, step=30,
        label_key="familyConfig.aiCacheTtlFinanceCoach",
        description_key="familyConfig.aiCacheTtlFinanceCoachDesc",
    ),
    "ai_cache_ttl_dashboard_narrative": SettingDefinition(
        type="int", default=240, min=30, max=720, step=30,
        label_key="familyConfig.aiCacheTtlNarrative",
        description_key="familyConfig.aiCacheTtlNarrativeDesc",
    ),
    # --- Dashboard thresholds ---
    "dashboard_min_asset_count": SettingDefinition(
        type="int", default=5, min=1, max=50, step=1,
        label_key="familyConfig.minAssetCount",
        description_key="familyConfig.minAssetCountDesc",
    ),
    "dashboard_min_history_months": SettingDefinition(
        type="int", default=1, min=1, max=12, step=1,
        label_key="familyConfig.minHistoryMonths",
        description_key="familyConfig.minHistoryMonthsDesc",
    ),
    "dashboard_expiring_days_threshold": SettingDefinition(
        type="int", default=180, min=7, max=365, step=7,
        label_key="familyConfig.expiringDaysThreshold",
        description_key="familyConfig.expiringDaysThresholdDesc",
    ),
    # --- Scheduled tasks (currently disabled in scheduler; store preferences for future use) ---
    "scheduled_monthly_report_day": SettingDefinition(
        type="int", default=1, min=1, max=28, step=1,
        label_key="familyConfig.monthlyReportDay",
        description_key="familyConfig.monthlyReportDayDesc",
    ),
    "scheduled_monthly_report_hour": SettingDefinition(
        type="int", default=8, min=0, max=23, step=1,
        label_key="familyConfig.monthlyReportHour",
        description_key="familyConfig.monthlyReportHourDesc",
    ),
    "scheduled_weekly_scan_day": SettingDefinition(
        type="int", default=0, min=0, max=6, step=1,
        label_key="familyConfig.weeklyScanDay",
        description_key="familyConfig.weeklyScanDayDesc",
    ),
    "scheduled_weekly_scan_hour": SettingDefinition(
        type="int", default=8, min=0, max=23, step=1,
        label_key="familyConfig.weeklyScanHour",
        description_key="familyConfig.weeklyScanHourDesc",
    ),
}

USER_SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "dashboard_trend_period": SettingDefinition(
        type="string", default="month",
        allowed_values=["month", "quarter", "year"],
        label_key="userConfig.trendPeriod",
        description_key="userConfig.trendPeriodDesc",
    ),
    "activity_feed_page_size": SettingDefinition(
        type="int", default=20, min=5, max=50, step=5,
        label_key="userConfig.activityPageSize",
        description_key="userConfig.activityPageSizeDesc",
    ),
}


def get_definition(scope: Literal["family", "user"], key: str) -> SettingDefinition:
    """Look up a setting definition. Raises KeyError if unknown."""
    registry = FAMILY_SETTING_DEFINITIONS if scope == "family" else USER_SETTING_DEFINITIONS
    if key not in registry:
        raise KeyError(f"Unknown {scope} setting key: {key}")
    return registry[key]


def validate_value(
    scope: Literal["family", "user"], key: str, raw_value: Any
) -> int | float | str | bool:
    """Validate and coerce a raw value against the registry definition.

    Returns the validated value. Raises ValueError on invalid input.
    """
    defn = get_definition(scope, key)

    # Type coercion
    if defn.type == "int":
        if not isinstance(raw_value, int) or isinstance(raw_value, bool):
            try:
                raw_value = int(raw_value)
            except (TypeError, ValueError):
                raise ValueError(f"'{key}' must be an integer") from None
        if defn.min is not None and raw_value < defn.min:
            raise ValueError(f"'{key}' must be >= {defn.min}")
        if defn.max is not None and raw_value > defn.max:
            raise ValueError(f"'{key}' must be <= {defn.max}")
    elif defn.type == "float":
        if isinstance(raw_value, bool):
            raise ValueError(f"'{key}' must be a number")
        try:
            raw_value = float(raw_value)
        except (TypeError, ValueError):
            raise ValueError(f"'{key}' must be a number") from None
        if defn.min is not None and raw_value < defn.min:
            raise ValueError(f"'{key}' must be >= {defn.min}")
        if defn.max is not None and raw_value > defn.max:
            raise ValueError(f"'{key}' must be <= {defn.max}")
    elif defn.type == "string":
        if not isinstance(raw_value, str):
            raise ValueError(f"'{key}' must be a string")
        if defn.allowed_values is not None and raw_value not in defn.allowed_values:
            raise ValueError(
                f"'{key}' must be one of {defn.allowed_values}, got '{raw_value}'"
            )
    elif defn.type == "bool":
        if not isinstance(raw_value, bool):
            raise ValueError(f"'{key}' must be a boolean")

    return raw_value
