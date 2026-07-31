"""Tests for onboarding guide state user settings."""
import pytest
from apps.backend.app.services.config_registry import USER_SETTING_DEFINITIONS, validate_value


def test_onboarding_settings_registered():
    assert "onboarding_guide_version" in USER_SETTING_DEFINITIONS
    assert "onboarding_attempts" in USER_SETTING_DEFINITIONS
    assert "onboarding_completions" in USER_SETTING_DEFINITIONS


def test_onboarding_defaults():
    assert USER_SETTING_DEFINITIONS["onboarding_guide_version"].default == 0
    assert USER_SETTING_DEFINITIONS["onboarding_attempts"].default == 0
    assert USER_SETTING_DEFINITIONS["onboarding_completions"].default == 0


def test_onboarding_validation():
    assert validate_value("user", "onboarding_guide_version", 2) == 2
    assert validate_value("user", "onboarding_attempts", 5) == 5
    assert validate_value("user", "onboarding_completions", 3) == 3


def test_onboarding_rejects_negative():
    with pytest.raises(ValueError):
        validate_value("user", "onboarding_attempts", -1)
