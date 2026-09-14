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
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": "wish_redeemed",
        "title": f"心愿兑现：{wish_title}",
        "body": f"{child_name} 的心愿「{wish_title}」已兑现！",
        "severity": "info",
        "template_vars": {"wish_title": wish_title, "child_name": child_name},
    })
```

- [ ] **Step 4: Update dispatch to use mention formatting**

In `_send_telegram_async` and `_send_feishu_async` in `dispatcher.py`, add mention formatting:

```python
# In _send_telegram_async, after rendering text:
mention_config = config.get("mention_config")
if mention_config:
    text = _format_mention(text, "telegram", mention_config)

# In _send_feishu_async, after rendering text:
mention_config = config.get("mention_config")
if mention_config:
    text = _format_mention(text, "feishu", mention_config)
```

Add import at top:
```python
from apps.backend.app.services.notification.sender import _format_mention
```

- [ ] **Step 5: Add _dispatch_digest function**

```python
async def _dispatch_digest(db: Session) -> None:
    """Send daily digest for channels configured with digest_mode='daily'.

    Uses digest_sent_at to track delivery (not status='resolved').
    Must be called from an async context (scheduler worker uses AsyncIOScheduler).
    """
    channels = (
        db.query(NotificationChannel)
        .filter(NotificationChannel.is_enabled, NotificationChannel.digest_mode == "daily")
        .all()
    )

    for channel in channels:
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.family_id == channel.family_id,
                Reminder.status == "active",
                Reminder.created_at >= cutoff,
                Reminder.digest_sent_at.is_(None),
            )
            .all()
        )
        if not reminders:
            continue

        summary_lines = [f"• {r.title}" for r in reminders]
        text = f" 今日通知摘要（{len(reminders)} 条）\n\n" + "\n".join(summary_lines)

        # Apply mention formatting
        config = _get_channel_config(db, channel)
        mention_config = config.get("mention_config")
        if mention_config:
            text = _format_mention(text, channel.channel_type, mention_config)

        # Send via channel's sender (reuse existing send functions)
        if channel.channel_type == "telegram":
            await _send_telegram_text(channel, config, text, db)
        elif channel.channel_type == "feishu":
            await _send_feishu_text(channel, config, text, db)

        # Mark as digest-sent (not resolved)
        now = datetime.now(UTC)
        for r in reminders:
            r.digest_sent_at = now
    db.commit()
```

- [ ] **Step 6: Run tests**

```bash
cd server && uv run pytest tests/backend/services/test_notification_dispatcher.py -v
```

- [ ] **Step 7: Commit**

```bash
git add server/apps/backend/app/services/notification/dispatcher.py server/apps/backend/app/services/notification/sender.py server/tests/backend/services/test_notification_dispatcher.py
git commit -m "feat(notification): add dispatcher hooks, mention support, dedup, digest dispatch

- notify_ai_task_complete/chore_completed/treasure_redeemed/wish_redeemed
- _format_mention for Telegram/Feishu @mentions
- Deduplication for AI task notifications (1h window)
- _dispatch_digest using digest_sent_at (not status change)

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Push Service Coordination

**Files:**
- Modify: `server/apps/backend/app/services/notification/push_service.py`

**Rationale (CE review P0 fix):** Prevent duplicate notifications when both push_service.py and the reminder pipeline send webpush for the same events.

- [ ] **Step 1: Add skip list to push_service.py**

```python
# Events handled by the reminder pipeline — skip to avoid duplicate webpush
REMINDER_PIPELINE_EVENTS = {"chore_completed", "treasure_redeemed", "wish_redeemed"}


def send_family_interaction_push(
    db: Session,
    family_id: int,
    title: str,
    body: str,
    reminder_type: str = "family_interaction",
    navigate_to: str = "",
) -> None:
    """Send a push notification for family interaction events.

    Skips events that are now handled by the reminder pipeline
    (chore_completed, treasure_redeemed, wish_redeemed) to avoid duplicates.
    """
    if reminder_type in REMINDER_PIPELINE_EVENTS:
        return  # Handled by reminder pipeline

    # ... existing code ...
```

- [ ] **Step 2: Commit**

