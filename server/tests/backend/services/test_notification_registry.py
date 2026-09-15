"""Tests for notification event registry."""

from apps.backend.app.services.notification.registry import (
    NOTIFICATION_CATEGORIES,
    get_categorized_events,
    VALID_REMINDER_TYPES,
)


def test_get_categorized_events_returns_four_categories():
    result = get_categorized_events()
    assert len(result) == 4
    categories = [c["category"] for c in result]
    assert categories == ["asset", "ai_task", "children", "wish"]


def test_get_categorized_events_has_ten_total_events():
    result = get_categorized_events()
    total = sum(len(c["events"]) for c in result)
    assert total == 10


def test_get_categorized_events_structure():
    result = get_categorized_events()
    asset_cat = result[0]
    assert asset_cat["category"] == "asset"
    assert "label_key" in asset_cat
    assert "icon" in asset_cat
    assert len(asset_cat["events"]) == 3
    first_event = asset_cat["events"][0]
    assert "type" in first_event
    assert "label_key" in first_event
    assert "severity" in first_event


def test_valid_reminder_types_matches_registry():
    """VALID_REMINDER_TYPES should be derived from the registry, not hardcoded."""
    registry_types = set()
    for cat in NOTIFICATION_CATEGORIES.values():
        registry_types.update(cat["events"].keys())
    assert VALID_REMINDER_TYPES == registry_types


def test_each_event_has_required_fields():
    for cat in NOTIFICATION_CATEGORIES.values():
        for event_key, event in cat["events"].items():
            assert "label_key" in event, f"Event {event_key} missing label_key"
            assert "default_severity" in event, f"Event {event_key} missing default_severity"
            assert "trigger" in event, f"Event {event_key} missing trigger"
            assert event["trigger"] in ("realtime", "scheduled"), f"Event {event_key} invalid trigger"
            assert event["default_severity"] in ("info", "warning", "critical")
