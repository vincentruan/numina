{
  "telegram": {"text": "📊 {task_title} 已生成完成，点击查看。"},
  "email_subject": "AI 任务完成：{task_title}",
  "email_body": "<p>{task_title} 已生成完成，请登录查看。</p>",
  "feishu": {"text": " {task_title} 已生成完成，点击查看。"},
  "webpush_title": "AI 任务完成",
  "webpush_body": "{task_title} 已生成完成"
}
```

Create `ai_finance_coach_complete.json`, `ai_wish_advice_complete.json`, `ai_literacy_report_complete.json` with similar structure (adjust emoji and text).

- [ ] **Step 2: Create children/wish templates**

Create `chore_completed.json`:
```json
{
  "telegram": {"text": " {child_name} 完成了任务「{chore_title}」，快去看看吧！"},
  "email_subject": "儿童任务完成：{chore_title}",
  "email_body": "<p>{child_name} 完成了任务「{chore_title}」。</p>",
  "feishu": {"text": "👶 {child_name} 完成了任务「{chore_title}」，快去看看吧！"},
  "webpush_title": "儿童任务完成",
  "webpush_body": "{child_name} 完成了「{chore_title}」"
}
```

Create `treasure_redeemed.json` and `wish_redeemed.json` similarly.

- [ ] **Step 3: Commit**

```bash
git add server/apps/backend/app/services/notification/templates/ai_*.json server/apps/backend/app/services/notification/templates/chore_completed.json server/apps/backend/app/services/notification/templates/treasure_redeemed.json server/apps/backend/app/services/notification/templates/wish_redeemed.json
git commit -m "feat(notification): add 7 templates for new event types

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: API Endpoint + Router Updates

**Files:**
- Modify: `server/apps/backend/app/routers/notification_channels.py`

**Interfaces:**
- Consumes: `get_categorized_events()`, `VALID_REMINDER_TYPES` from registry
- Produces: `GET /api/v1/notification-channels/events` endpoint

**Rationale (CE review fix):** Add explicit `require_adult` auth to `/events` endpoint. Use registry-derived `VALID_REMINDER_TYPES` instead of hardcoded set.

- [ ] **Step 1: Write the test**

Create `server/tests/backend/routers/test_notification_channels_events.py`:

```python
"""Tests for GET /notification-channels/events endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.usefixtures("auth_headers")
def test_get_events_returns_four_categories(client: TestClient):
    resp = client.get("/api/v1/notification-channels/events")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 4
    categories = [c["category"] for c in data]
    assert categories == ["asset", "ai_task", "children", "wish"]


@pytest.mark.usefixtures("auth_headers")
def test_get_events_asset_category_has_three_events(client: TestClient):
    resp = client.get("/api/v1/notification-channels/events")
    asset = next(c for c in resp.json() if c["category"] == "asset")
    assert len(asset["events"]) == 3
    types = [e["type"] for e in asset["events"]]
    assert "large_purchase" in types
    assert "expiring_soon" in types
    assert "maturity" in types


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
