"""Tests for U3: capability_catalog overrides cover all capabilities.

Plan U3 originally proposed removing chat and time_machine entries from
_CAPABILITY_OVERRIDES under the assumption they were skill-only metadata.
Investigation showed they are routing capabilities (per _ROUTING_CAPABILITIES
in ai_capabilities) whose canonical display names live here. Keeping the
entries is the corrected behavior — these tests pin that contract.
"""

from apps.backend.app.services.capability_catalog import (
    _CAPABILITY_OVERRIDES,
    apply_capability_overrides,
)


def test_overrides_contain_routing_capabilities():
    """chat and time_machine routing capabilities have explicit overrides."""
    assert "chat" in _CAPABILITY_OVERRIDES
    assert "time_machine" in _CAPABILITY_OVERRIDES


def test_overrides_contain_six_business_skills():
    """The six BUILTIN_CAPABILITIES skills each have an override."""
    expected_skills = {
        "report",
        "alerts",
        "allocation",
        "disposal",
        "liability",
        "spending_leak",
    }
    assert expected_skills.issubset(_CAPABILITY_OVERRIDES.keys())


def test_apply_overrides_to_chat_yields_localized_name():
    """The chat capability gets its 'AI 问答' display name (not the agent's '智能问答')."""
    result = apply_capability_overrides({"id": "chat", "name": "fallback", "ui": {}})
    assert result["name"] == "AI 问答"
    assert result["ui"]["route"] == "/ai/chat"
    assert result["ui"]["icon"] == "message-circle"


def test_apply_overrides_to_time_machine_yields_localized_name():
    """The time_machine capability gets its '资产时光机' display name."""
    result = apply_capability_overrides(
        {"id": "time_machine", "name": "fallback", "ui": {}}
    )
    assert result["name"] == "资产时光机"
    assert result["ui"]["route"] == "/ai/time-machine"


def test_apply_overrides_to_report_yields_skill_metadata():
    """A business skill (report) gets its localized name and route."""
    result = apply_capability_overrides({"id": "report", "name": "fallback", "ui": {}})
    assert result["name"] == "资产体检"
    assert result["ui"]["route"] == "/ai/report"


def test_apply_overrides_preserves_unknown_capability():
    """An unknown capability id is returned with its original fields untouched."""
    capability = {
        "id": "totally-new-skill",
        "name": "Whatever",
        "ui": {"icon": "star", "route": "/x"},
    }
    result = apply_capability_overrides(capability)
    assert result["name"] == "Whatever"
    assert result["ui"]["icon"] == "star"
    # Original input is not mutated (deepcopy).
    assert capability["name"] == "Whatever"


def test_apply_overrides_merges_ui_dict():
    """The override's ui dict is merged into the input's ui dict (override wins)."""
    capability = {
        "id": "chat",
        "name": "fallback",
        "ui": {"existing_field": "kept", "icon": "old-icon"},
    }
    result = apply_capability_overrides(capability)
    assert result["ui"]["icon"] == "message-circle"  # override wins
    assert result["ui"]["existing_field"] == "kept"  # non-overridden field survives
