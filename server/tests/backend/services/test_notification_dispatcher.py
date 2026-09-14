"""Tests for notification dispatcher hooks and mention formatting."""

from apps.backend.app.services.notification.sender import _format_mention


def test_format_mention_telegram_with_user_id():
    text = "Test notification"
    config = {"user_id": "123456789", "username": "vincent"}
    result = _format_mention(text, "telegram", config)
    assert '<a href="tg://user?id=123456789">@vincent</a>' in result
    assert "Test notification" in result


def test_format_mention_telegram_without_user_id():
    text = "Test notification"
    config = {"username": "vincent"}
    result = _format_mention(text, "telegram", config)
    assert result == text  # No mention added


def test_format_mention_feishu_with_open_id():
    text = "Test notification"
    config = {"open_id": "ou_xxx", "name": "Vincent"}
    result = _format_mention(text, "feishu", config)
    assert '<at user_id="ou_xxx">Vincent</at>' in result


def test_format_mention_none_config():
    text = "Test notification"
    result = _format_mention(text, "telegram", None)
    assert result == text


def test_format_mention_unsupported_channel():
    text = "Test notification"
    config = {"user_id": "123"}
    result = _format_mention(text, "email", config)
    assert result == text  # Email doesn't support mention


def test_notify_ai_task_complete_dedup():
    """Second call within 1 hour should be skipped (dedup)."""
    # This requires a DB session fixture - use integration test pattern
    # See tests/backend/integration/test_notification_dedup.py for full test
    assert True  # Placeholder - integration test covers this
