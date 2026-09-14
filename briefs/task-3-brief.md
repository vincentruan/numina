

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
