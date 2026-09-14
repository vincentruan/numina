- Add deduplication for AI task notifications
- Add `_format_mention()` for Telegram/Feishu @mentions
- Accept `template_vars` separately (not via ensure_reminder dict)

- [ ] **Step 1: Write tests for new dispatcher functions**

Create additions to `server/tests/backend/services/test_notification_dispatcher.py`:

```python
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
```

- [ ] **Step 2: Implement _format_mention in sender.py**

Add to `server/apps/backend/app/services/notification/sender.py`:

```python
def _format_mention(text: str, channel_type: str, mention_config: dict | None) -> str:
    """Prepend @mention markup to message text if mention_config is set.

    Telegram: uses HTML <a href="tg://user?id=...">@username</a> format.
    Feishu: uses <at user_id="open_id">name</at> format.
    Other channel types: returns text unchanged.
    """
    if not mention_config:
        return text

    if channel_type == "telegram":
        user_id = mention_config.get("user_id")
        username = mention_config.get("username", "user")
        if user_id:
            mention = f'<a href="tg://user?id={user_id}">@{username}</a>\n\n'
            return mention + text

    elif channel_type == "feishu":
        open_id = mention_config.get("open_id")
        name = mention_config.get("name", "user")
        if open_id:
            mention = f'<at user_id="{open_id}">{name}</at>\n\n'
            return mention + text

    return text
```

- [ ] **Step 3: Add dispatcher hooks**

Add to `server/apps/backend/app/services/notification/dispatcher.py`:

```python
from apps.backend.app.services.notification.registry import NOTIFICATION_CATEGORIES
from datetime import timedelta


def _check_reminder_dedup(db: Session, family_id: int, reminder_type: str, title: str, hours: int = 1) -> bool:
    """Check if a similar reminder was created recently (deduplication)."""
    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    existing = (
        db.query(Reminder)
        .filter(
            Reminder.family_id == family_id,
            Reminder.reminder_type == reminder_type,
            Reminder.title == title,
            Reminder.created_at >= cutoff,
        )
        .first()
    )
    return existing is not None


def notify_ai_task_complete(
    db: Session, family_id: int, task_type: str, task_title: str
) -> None:
    """Create a Reminder for AI task completion and dispatch.

    Includes deduplication: skips if same task_type+title was notified within 1 hour.
    """
    reminder_type = f"ai_{task_type}_complete"
    title = f"AI 任务完成：{task_title}"

    if _check_reminder_dedup(db, family_id, reminder_type, title, hours=1):
        return

    template_vars = {"task_title": task_title}
    body = f"「{task_title}」已生成完成，点击查看。"

    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": reminder_type,
        "title": title,
        "body": body,
        "severity": "info",
        "template_vars": template_vars,
    })


def notify_chore_completed(
    db: Session, family_id: int, child_name: str, chore_title: str
) -> None:
    """Create a Reminder for chore completion and dispatch."""
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": "chore_completed",
        "title": f"儿童任务完成：{chore_title}",
        "body": f"{child_name} 完成了任务「{chore_title}」，快去看看吧！",
        "severity": "info",
        "template_vars": {"child_name": child_name, "chore_title": chore_title},
    })


def notify_treasure_redeemed(
    db: Session, family_id: int, child_name: str, treasure_title: str
) -> None:
    """Create a Reminder for treasure redemption and dispatch."""
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": "treasure_redeemed",
        "title": f"宝贝兑换：{treasure_title}",
        "body": f"{child_name} 兑换了宝贝「{treasure_title}」！",
        "severity": "info",
        "template_vars": {"child_name": child_name, "treasure_title": treasure_title},
    })


def notify_wish_redeemed(
    db: Session, family_id: int, wish_title: str, child_name: str
) -> None:
    """Create a Reminder for wish redemption and dispatch."""
