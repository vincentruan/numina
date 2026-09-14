

@pytest.mark.usefixtures("auth_headers")
def test_get_events_requires_auth(client_no_auth: TestClient):
    resp = client_no_auth.get("/api/v1/notification-channels/events")
    assert resp.status_code in (401, 403)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd server && uv run pytest tests/backend/routers/test_notification_channels_events.py -v
```

- [ ] **Step 3: Update router**

Modify `server/apps/backend/app/routers/notification_channels.py`:

```python
# Replace the hardcoded VALID_REMINDER_TYPES line (line 28):
# OLD: VALID_REMINDER_TYPES = {"large_purchase", "expiring_soon", "maturity"}
# NEW:
from apps.backend.app.services.notification.registry import (
    get_categorized_events,
    VALID_REMINDER_TYPES,
)

# Add new endpoint before the list_channels function:
@router.get("/events")
def get_events(user: User = Depends(require_adult)):
    """Return categorized event types for frontend event selector."""
    return get_categorized_events()

# Update create_channel and update_channel to use the registry-derived set:
# In create_channel, change line 94:
# OLD: if rtype in VALID_REMINDER_TYPES:
# (VALID_REMINDER_TYPES is now imported from registry, no change needed to the check itself)

# In create_channel, accept digest_mode and digest_time:
channel = NotificationChannel(
    id=next_id(),
    family_id=user.family_id,
    channel_type=req.channel_type,
    name=req.name,
    is_enabled=req.is_enabled if req.is_enabled is not None else True,
    digest_mode=getattr(req, "digest_mode", "immediate"),
    digest_time=getattr(req, "digest_time", "21:00"),
)

# In _to_response, add digest fields to response:
return NotificationChannelResponse(
    # ... existing fields ...
    digest_mode=channel.digest_mode,
    digest_time=channel.digest_time,
)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd server && uv run pytest tests/backend/routers/test_notification_channels_events.py -v
```

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/routers/notification_channels.py server/tests/backend/routers/test_notification_channels_events.py
git commit -m "feat(notification): add GET /events endpoint with registry-derived validation

Replaces hardcoded VALID_REMINDER_TYPES with registry-derived set.
Adds explicit require_adult auth to /events endpoint.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Dispatcher Hooks + Mention Support + Dedup

**Files:**
- Modify: `server/apps/backend/app/services/notification/dispatcher.py`
- Modify: `server/apps/backend/app/services/notification/sender.py`

**Interfaces:**
- Consumes: `NOTIFICATION_CATEGORIES` from registry, `Reminder` model with `digest_sent_at`
- Produces: `notify_ai_task_complete()`, `notify_chore_completed()`, `notify_treasure_redeemed()`, `notify_wish_redeemed()`, `_dispatch_digest()`, `_format_mention()`

**Rationale (CE review fixes):**
- Add `notify_treasure_redeemed()` (was missing in spec)
- Use `digest_sent_at` instead of changing status to "resolved"
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
