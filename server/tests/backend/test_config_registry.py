"""Tests for config_registry: validation, defaults, type coercion."""
import pytest

from apps.backend.app.services.config_registry import (
    FAMILY_SETTING_DEFINITIONS,
    USER_SETTING_DEFINITIONS,
    get_definition,
    validate_value,
)


class TestGetDefinition:
    def test_known_family_key(self):
        defn = get_definition("family", "ai_cache_ttl_report")
        assert defn.type == "int"
        assert defn.default == 60
        assert defn.min == 5
        assert defn.max == 480

    def test_known_user_key(self):
        defn = get_definition("user", "dashboard_trend_period")
        assert defn.type == "string"
        assert defn.default == "month"
        assert defn.allowed_values == ["month", "quarter", "year"]

    def test_unknown_key_raises(self):
        with pytest.raises(KeyError, match="Unknown family setting key"):
            get_definition("family", "nonexistent_key")


class TestValidateValue:
    # --- int type ---
    def test_int_valid(self):
        assert validate_value("family", "ai_cache_ttl_report", 120) == 120

    def test_int_coercion_from_string(self):
        assert validate_value("family", "ai_cache_ttl_report", "120") == 120

    def test_int_below_min(self):
        with pytest.raises(ValueError, match="must be >= 5"):
            validate_value("family", "ai_cache_ttl_report", 3)

    def test_int_above_max(self):
        with pytest.raises(ValueError, match="must be <= 480"):
            validate_value("family", "ai_cache_ttl_report", 999)

    def test_int_at_boundary_min(self):
        assert validate_value("family", "ai_cache_ttl_report", 5) == 5

    def test_int_at_boundary_max(self):
        assert validate_value("family", "ai_cache_ttl_report", 480) == 480

    def test_bool_rejected_as_int(self):
        with pytest.raises(ValueError, match="must be an integer"):
            validate_value("family", "ai_cache_ttl_report", True)

    # --- string type ---
    def test_string_valid(self):
        assert validate_value("user", "dashboard_trend_period", "quarter") == "quarter"

    def test_string_not_allowed(self):
        with pytest.raises(ValueError, match="must be one of"):
            validate_value("user", "dashboard_trend_period", "decade")

    def test_string_wrong_type(self):
        with pytest.raises(ValueError, match="must be a string"):
            validate_value("user", "dashboard_trend_period", 123)

    # --- unknown key ---
    def test_unknown_key_raises(self):
        with pytest.raises(KeyError):
            validate_value("family", "bogus_key", 42)


class TestDefinitionsCompleteness:
    def test_all_family_keys_have_labels(self):
        for key, defn in FAMILY_SETTING_DEFINITIONS.items():
            assert defn.label_key, f"{key} missing label_key"

    def test_all_user_keys_have_labels(self):
        for key, defn in USER_SETTING_DEFINITIONS.items():
            assert defn.label_key, f"{key} missing label_key"

    def test_family_count(self):
        assert len(FAMILY_SETTING_DEFINITIONS) == 13

    def test_user_count(self):
        assert len(USER_SETTING_DEFINITIONS) == 2


def test_literacy_report_settings_registered():
    from apps.backend.app.services.config_registry import FAMILY_SETTING_DEFINITIONS
    assert "literacy_report_day" in FAMILY_SETTING_DEFINITIONS
    assert "literacy_report_hour" in FAMILY_SETTING_DEFINITIONS
    assert "ai_cache_ttl_literacy_weekly_report" in FAMILY_SETTING_DEFINITIONS
    # Default: Sunday (0), 8am, 7-day TTL
    assert FAMILY_SETTING_DEFINITIONS["literacy_report_day"].default == 0
    assert FAMILY_SETTING_DEFINITIONS["literacy_report_hour"].default == 8
