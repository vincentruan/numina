"""Notification event registry.

Central source of truth for all notification event types.
Replaces the hardcoded VALID_REMINDER_TYPES set in notification_channels router.
"""

NOTIFICATION_CATEGORIES: dict[str, dict] = {
    "asset": {
        "label_key": "reminders.categories.asset",
        "icon": "cube-outline",
        "events": {
            "large_purchase": {
                "label_key": "reminders.types.large_purchase",
                "default_severity": "warning",
                "trigger": "realtime",
            },
            "expiring_soon": {
                "label_key": "reminders.types.expiring_soon",
                "default_severity": "warning",
                "trigger": "scheduled",
            },
            "maturity": {
                "label_key": "reminders.types.maturity",
                "default_severity": "warning",
                "trigger": "scheduled",
            },
        },
    },
    "ai_task": {
        "label_key": "reminders.categories.ai_task",
        "icon": "robot-outline",
        "events": {
            "ai_report_complete": {
                "label_key": "reminders.types.ai_report_complete",
                "default_severity": "info",
                "trigger": "realtime",
            },
            "ai_finance_coach_complete": {
                "label_key": "reminders.types.ai_finance_coach_complete",
                "default_severity": "info",
                "trigger": "realtime",
            },
            "ai_wish_advice_complete": {
                "label_key": "reminders.types.ai_wish_advice_complete",
                "default_severity": "info",
                "trigger": "realtime",
            },
            "ai_literacy_report_complete": {
                "label_key": "reminders.types.ai_literacy_report_complete",
                "default_severity": "info",
                "trigger": "realtime",
            },
        },
    },
    "children": {
        "label_key": "reminders.categories.children",
        "icon": "friends-outline",
        "events": {
            "chore_completed": {
                "label_key": "reminders.types.chore_completed",
                "default_severity": "info",
                "trigger": "realtime",
            },
            "treasure_redeemed": {
                "label_key": "reminders.types.treasure_redeemed",
                "default_severity": "info",
                "trigger": "realtime",
            },
        },
    },
    "wish": {
        "label_key": "reminders.categories.wish",
        "icon": "gift-outline",
        "events": {
            "wish_redeemed": {
                "label_key": "reminders.types.wish_redeemed",
                "default_severity": "info",
                "trigger": "realtime",
            },
        },
    },
}


def get_categorized_events() -> list[dict]:
    """Return categorized event list for frontend rendering.

    Each category includes its metadata and a list of events with:
    - type: the reminder_type string
    - label_key: i18n key for display
    - severity: default severity level
    """
    result = []
    for category_key, category in NOTIFICATION_CATEGORIES.items():
        events = []
        for event_key, event in category["events"].items():
            events.append({
                "type": event_key,
                "label_key": event["label_key"],
                "severity": event["default_severity"],
            })
        result.append({
            "category": category_key,
            "label_key": category["label_key"],
            "icon": category["icon"],
            "events": events,
        })
    return result


def get_all_reminder_types() -> set[str]:
    """Return flat set of all valid reminder_type values from the registry."""
    types = set()
    for category in NOTIFICATION_CATEGORIES.values():
        types.update(category["events"].keys())
    return types


# Backward-compatible alias for the router's VALID_REMINDER_TYPES
VALID_REMINDER_TYPES: set[str] = get_all_reminder_types()
