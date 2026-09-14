---
date: 2026-09-14
title: Notification Module Enhancement — Categorized Events, AI Task Hooks, Bot Mentions, Digest Mode
status: draft
author: Vincent Ruan + Claude
---

# Notification Module Enhancement Design

## Problem Statement

The current notification module supports only 3 hardcoded event types (`large_purchase`, `expiring_soon`, `maturity`) displayed as flat inline checkboxes. The project has grown to include AI async tasks (report generation, finance coach, wish advice), children's chore completion, and wish redemption — none of which trigger notifications. Additionally, Telegram/Feishu bots running in group chats cannot @mention specific users, and there is no batched digest mode for reducing notification noise.

## Goals

1. **Expand event taxonomy** — structured registry of events organized by category, extensible without code changes to the frontend
2. **Improve event selection UX** — categorized bottom-sheet popup replacing flat checkboxes
3. **Hook AI async tasks** — notify on completion of report, finance coach, wish advice, literacy report
4. **Hook children events** — notify on chore completion and wish redemption
5. **Bot @mention support** — configure user identity per channel for Telegram/Feishu group @mentions
6. **Daily digest mode** — per-channel option to batch notifications into a daily summary

## Non-Goals

- Per-event scheduling (each event type has its own cron) — YAGNI
- Per-user channel subscriptions (subscriptions remain family-level) — future consideration
- Notification inbox / read history UI — separate feature
- SMS / WhatsApp channel support — out of scope

---

## Architecture

### Component Diagram

```
─────────────────────────────────────────────────────────────┐
│                     Frontend (Vue 3)                        │
│                                                             │
│  NotificationConfigPage.vue                                 │
│  ├── Channel list (van-swipe-cell)                          │
│  ├── Add/Edit popup (van-popup bottom)                      │
│  │   ├── Channel type fields (Telegram/Feishu/Email)        │
│  │   ├── Mention config section (new)                       │
│  │   └── Event selector button → EventSelectorPopup (new)   │
│  ── EventSelectorPopup (new)                               │
│      ├── Category sections (Asset/AI/Children/Wish)         │
│      ├── Checkboxes per event                               │
│      └── Select all / deselect all                          │
└──────────────────────────┬──────────────────────────────────
                           │ GET /notification-channels/events
                           │ GET/POST/PUT/DELETE /notification-channels
┌──────────────────────────┴──────────────────────────────────┐
│                   Backend (FastAPI)                          │
│                                                             │
│  notification_registry.py (new)                             │
│  ├── NOTIFICATION_CATEGORIES dict                           │
│  └── get_categorized_events() → API response                │
│                                                             │
│  notification_channels router                               │
│  ├── GET /events (new) — returns categorized events         │
│  └── Existing CRUD (expanded validation)                    │
│                                                             │
│  dispatcher.py                                              │
│  ├── ensure_reminder() — existing, expanded for new types   │
│  ├── notify_ai_task_complete() (new)                        │
│  ├── notify_chore_completed() (new)                         │
│  └── notify_wish_redeemed() (new)                           │
│                                                             │
│  sender.py                                                  │
│  └── _format_mention() — Telegram/Feishu @mention helper    │
│                                                             │
│  notification_channel model (expanded)                      │
│  ├── digest_mode: str = "immediate" | "daily"               │
│  └── digest_time: str = "21:00"                             │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────┴──────────────────────────────────┐
│               Scheduler Worker (APScheduler)                 │
│                                                             │
│  notification_digest_job (new)                              │
│  ├── Trigger: cron daily at 21:00 (configurable)            │
│  ├── Query channels with digest_mode="daily"                │
│  ├── Collect unresolved reminders since last digest         │
│  ├── Render summary per channel                             │
│  └── Dispatch via existing sender functions                 │
└─────────────────────────────────────────────────────────────┘
```

### Event Registry

**File**: `server/packages/core/notification_registry.py`

```python
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
    """Return categorized event list for frontend rendering."""
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
```

### New API Endpoint

**`GET /api/v1/notification-channels/events`**

Response:
```json
[
  {
    "category": "asset",
    "label_key": "reminders.categories.asset",
    "icon": "cube-outline",
    "events": [
      {"type": "large_purchase", "label_key": "reminders.types.large_purchase", "severity": "warning"},
      {"type": "expiring_soon", "label_key": "reminders.types.expiring_soon", "severity": "warning"},
      {"type": "maturity", "label_key": "reminders.types.maturity", "severity": "warning"}
    ]
  },
  ...
]
```

This replaces the frontend's hardcoded `reminderTypes` array. The frontend fetches this once and uses it to render the categorized selector.

---

## Database Migration

**Add columns to `notification_channels` table:**

```python
# alembic revision
def upgrade():
    op.add_column(
        "notification_channels",
        sa.Column("digest_mode", sa.String(20), nullable=False, server_default="immediate"),
    )
    op.add_column(
        "notification_channels",
        sa.Column("digest_time", sa.String(10), nullable=False, server_default="21:00"),
    )

def downgrade():
    op.drop_column("notification_channels", "digest_time")
    op.drop_column("notification_channels", "digest_mode")
```

**No new tables needed.** The `mention_config` is stored as an encrypted key-value pair in the existing `notification_channel_configs` table (key: `mention_config`, value: JSON string).

---

## Backend Changes

### 1. Model Updates

**`server/packages/db/models/notification_channel.py`**:
- Add `digest_mode: Mapped[str]` (default "immediate")
- Add `digest_time: Mapped[str]` (default "21:00")

### 2. Schema Updates

**`server/apps/backend/app/schemas/notification_channel.py`**:
- Add `digest_mode: str = "immediate"` to `NotificationChannelCreate` and `NotificationChannelResponse`
- Add `digest_time: str = "21:00"` to both schemas

### 3. Router Updates

**`server/apps/backend/app/routers/notification_channels.py`**:
- Add `GET /events` endpoint returning `get_categorized_events()`
- Expand `VALID_REMINDER_TYPES` to include all new event types (or remove the hardcoded set entirely and validate against the registry)
- Accept `digest_mode` and `digest_time` in create/update requests

### 4. Dispatcher Hooks

**`server/apps/backend/app/services/notification/dispatcher.py`**:

Add three new public functions:

```python
def notify_ai_task_complete(db: Session, family_id: int, task_type: str, task_title: str) -> None:
    """Create a Reminder for AI task completion and dispatch."""
    reminder_type = f"ai_{task_type}_complete"
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": reminder_type,
        "title": f"AI 任务完成：{task_title}",
        "body": f"「{task_title}」已生成完成，点击查看。",
        "severity": "info",
        "template_vars": {"task_title": task_title},
    })

def notify_chore_completed(db: Session, family_id: int, child_name: str, chore_title: str) -> None:
    """Create a Reminder for chore completion."""
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": "chore_completed",
        "title": f"儿童任务完成：{chore_title}",
        "body": f"{child_name} 完成了任务「{chore_title}」，快去看看吧！",
        "severity": "info",
        "template_vars": {"child_name": child_name, "chore_title": chore_title},
    })

def notify_wish_redeemed(db: Session, family_id: int, wish_title: str, child_name: str) -> None:
    """Create a Reminder for wish redemption."""
    ensure_reminder(db, {
        "family_id": family_id,
        "reminder_type": "wish_redeemed",
        "title": f"心愿兑现：{wish_title}",
        "body": f"{child_name} 的心愿「{wish_title}」已兑现！",
        "severity": "info",
        "template_vars": {"wish_title": wish_title, "child_name": child_name},
    })
```

### 5. Sender @Mention Support

**`server/apps/backend/app/services/notification/sender.py`**:

Add mention formatting helper:

```python
def _format_mention(text: str, channel_type: str, mention_config: dict | None) -> str:
    """Prepend @mention markup to message text if mention_config is set."""
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

Update `_send_telegram_async` and `_send_feishu_async` in `dispatcher.py` to call `_format_mention()` before sending. The `mention_config` is read from the channel's decrypted config under the key `mention_config`.

### 6. Integration Points

**AI task completion** — hook into `server/apps/backend/app/routers/ai_internal.py` at the `internal_task_complete` endpoint (line 1266). After marking the task as completed, call `notify_ai_task_complete()`.

**Chore completion** — hook into the chore approval endpoint in `server/apps/backend/app/routers/chores.py`. When a chore instance status changes to `approved`, call `notify_chore_completed()`.

**Wish redemption** — hook into the wish redemption endpoint in `server/apps/backend/app/routers/child_wishes.py` or the treasure redemption flow. When a wish is redeemed, call `notify_wish_redeemed()`.

---

## Frontend Changes

### 1. API Type Updates

**`frontend/apps/main/src/api/notificationChannels.ts`**:

```typescript
export interface NotificationEvent {
  type: string
  label_key: string
  severity: string
}

export interface NotificationEventCategory {
  category: string
  label_key: string
  icon: string
  events: NotificationEvent[]
}

export interface NotificationChannelResponse {
  // ... existing fields
  digest_mode: 'immediate' | 'daily'
  digest_time: string
}
```

Add API function:
```typescript
getEvents(): Promise<NotificationEventCategory[]> {
  return http.get<NotificationEventCategory[]>('/notification-channels/events').then((r) => r.data)
}
```

### 2. Event Selector Component

**New component**: `frontend/apps/main/src/components/notification/EventSelectorPopup.vue`

```vue
<template>
  <van-popup v-model:show="visible" position="bottom" round teleport="body" :style="{ height: '60%' }">
    <div class="popup-content">
      <van-nav-bar title="订阅事件">
        <template #right>
          <van-icon name="cross" @click="visible = false" />
        </template>
      </van-nav-bar>

      <van-cell-group inset>
        <div v-for="cat in categories" :key="cat.category" class="category-section">
          <div class="category-header">
            <van-icon :name="cat.icon" />
            <span>{{ t(cat.label_key) }}</span>
          </div>
          <van-checkbox-group v-model="selectedTypes">
            <van-cell
              v-for="event in cat.events"
              :key="event.type"
              :title="t(event.label_key)"
              clickable
              @click="toggleEvent(event.type)"
            >
              <template #right-icon>
                <van-checkbox :name="event.type" shape="square" />
              </template>
            </van-cell>
          </van-checkbox-group>
        </div>

        <div class="action-row">
          <van-button size="small" plain @click="selectAll">全选</van-button>
          <van-button size="small" plain @click="deselectAll">全不选</van-button>
        </div>
      </van-cell-group>

      <div class="save-row">
        <van-button type="primary" block @click="onSave">保存</van-button>
      </div>
    </div>
  </van-popup>
</template>
```

### 3. NotificationConfigPage Updates

**`frontend/apps/main/src/pages/NotificationConfigPage.vue`**:

- Replace the inline `van-checkbox-group` (lines 65-79) with a `van-cell` that opens the `EventSelectorPopup`
- Add mention config section for Telegram/Feishu channels:
  ```html
  <template v-if="form.channel_type === 'telegram' || form.channel_type === 'feishu'">
    <van-cell :title="t('reminders.mentionConfig')" is-link @click="showMentionSheet = true" />
  </template>
  ```
- Add digest mode toggle:
  ```html
  <van-cell :title="t('reminders.digestMode')">
    <template #value>
      <van-switch v-model="digestEnabled" />
    </template>
  </van-cell>
  ```

### 4. i18n Keys

**`frontend/apps/main/src/i18n/locales/zh-CN.ts`** — add under `reminders`:

```typescript
reminders: {
  // Categories
  'categories.asset': '资产',
  'categories.ai_task': 'AI 任务',
  'categories.children': '儿童任务',
  'categories.wish': '心愿',

  // New event types
  'types.ai_report_complete': '家庭报告生成完成',
  'types.ai_finance_coach_complete': '理财教练建议完成',
  'types.ai_wish_advice_complete': '心愿建议完成',
  'types.ai_literacy_report_complete': '识字周报生成完成',
  'types.chore_completed': '儿童任务完成',
  'types.treasure_redeemed': '宝贝兑换成功',
  'types.wish_redeemed': '心愿兑现',

  // New UI labels
  'mentionConfig': '通知提及',
  'mentionUserId': '用户 ID',
  'mentionUsername': '用户名',
  'mentionOpenId': 'Open ID',
  'digestMode': '每日摘要',
  'digestTime': '摘要发送时间',
  'selectAll': '全选',
  'deselectAll': '全不选',
  'selectEvents': '选择事件',
}
```

---

## Scheduler: Daily Digest Job

**File**: `server/apps/scheduler_worker/jobs/__init__.py`

```python
def notification_digest_job() -> None:
    """Send daily digest notifications for channels with digest_mode='daily'."""
    from packages.core.settings import settings  # noqa: PLC0415
    from sqlalchemy.orm import SessionLocal  # noqa: PLC0415
    from packages.db.session import SessionLocal  # noqa: PLC0415

    db = SessionLocal()
    try:
        from apps.backend.app.services.notification.dispatcher import (  # noqa: PLC0415
            _dispatch_digest,
        )
        _dispatch_digest(db)
    except Exception as e:
        logger.exception(f"Digest job failed: {e}")
    finally:
        db.close()
```

**Registration** in `scheduler.py`:
```python
scheduler.add_job(
    notification_digest_job,
    trigger="cron",
    hour=21,
    minute=0,
    id="notification_digest",
    name="notification_digest_job",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
```

**`_dispatch_digest(db)`** in `dispatcher.py`:
```python
def _dispatch_digest(db: Session) -> None:
    """Send daily digest for channels configured with digest_mode='daily'."""
    from datetime import UTC, datetime, timedelta  # noqa: PLC0415

    channels = (
        db.query(NotificationChannel)
        .filter(NotificationChannel.is_enabled, NotificationChannel.digest_mode == "daily")
        .all()
    )
    cutoff = datetime.now(UTC) - timedelta(hours=24)

    for channel in channels:
        # Collect unresolved reminders for this family since cutoff
        reminders = (
            db.query(Reminder)
            .filter(
                Reminder.family_id == channel.family_id,
                Reminder.status == "active",
                Reminder.created_at >= cutoff,
            )
            .all()
        )
        if not reminders:
            continue

        # Render summary
        summary_lines = []
        for r in reminders:
            summary_lines.append(f"• {r.title}")
        text = f"📋 今日通知摘要（{len(reminders)} 条）\n\n" + "\n".join(summary_lines)

        # Send via channel's sender (reuse existing sender functions)
        # ... (Telegram/Feishu/Email/WebPush dispatch with mention support)

        # Mark reminders as resolved (digest sent)
        for r in reminders:
            r.status = "resolved"
            r.resolved_at = datetime.now(UTC)
    db.commit()
```

---

## Notification Templates

**New template files** in `server/apps/backend/app/services/notification/templates/`:

- `ai_report_complete.json`
- `ai_finance_coach_complete.json`
- `ai_wish_advice_complete.json`
- `ai_literacy_report_complete.json`
- `chore_completed.json`
- `treasure_redeemed.json`
- `wish_redeemed.json`

Each template follows the existing format:
```json
{
  "telegram": {"text": " {task_title} 已生成完成，点击查看。"},
  "email_subject": "AI 任务完成：{task_title}",
  "email_body": "<p>{task_title} 已生成完成。</p>",
  "feishu": {"text": "🤖 {task_title} 已生成完成，点击查看。"},
  "webpush_title": "AI 任务完成",
  "webpush_body": "{task_title} 已生成完成"
}
```

---

## Testing Strategy

### Backend
1. **Unit tests** for `notification_registry.py` — verify `get_categorized_events()` returns correct structure
2. **Unit tests** for `_format_mention()` — verify Telegram/Feishu mention formatting with/without config
3. **Integration tests** for new dispatcher hooks — mock DB session, verify `ensure_reminder()` is called with correct params
4. **API tests** for `GET /notification-channels/events` — verify response structure

### Frontend
1. **Component tests** for `EventSelectorPopup` — verify category rendering, checkbox toggle, select all/deselect all
2. **Integration test** for `NotificationConfigPage` — verify event selection flow end-to-end
3. **Type check** — all new types are properly defined

### Manual Testing
1. Create a Telegram channel with mention config → trigger AI report → verify @mention in group
2. Create a Feishu channel with digest mode → wait for daily digest → verify summary message
3. Complete a chore as a child → verify parent receives notification

---

## Migration Plan

1. **Backend first**: Add registry, new endpoint, model columns, templates
2. **Frontend second**: Update API types, add EventSelectorPopup, update config page
3. **Scheduler third**: Add digest job
4. **Integration hooks last**: Wire up AI task, chore, and wish completion endpoints

### Rollback
- Remove new columns (safe with `server_default`)
- Revert frontend to hardcoded 3 event types
- Disable digest job in scheduler

---

## Files Modified Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `server/packages/core/notification_registry.py` | **NEW** | Event registry + `get_categorized_events()` |
| `server/packages/db/models/notification_channel.py` | MODIFY | Add `digest_mode`, `digest_time` columns |
| `server/apps/backend/app/schemas/notification_channel.py` | MODIFY | Add `digest_mode`, `digest_time` to schemas |
| `server/apps/backend/app/routers/notification_channels.py` | MODIFY | Add `GET /events`, expand validation |
| `server/apps/backend/app/services/notification/dispatcher.py` | MODIFY | Add AI/chore/wish hooks, `_dispatch_digest()`, mention support |
| `server/apps/backend/app/services/notification/sender.py` | MODIFY | Add `_format_mention()` helper |
| `server/apps/backend/app/services/notification/templates/*.json` | **NEW** (7 files) | Templates for new event types |
| `server/apps/scheduler_worker/jobs/__init__.py` | MODIFY | Add `notification_digest_job` |
| `server/apps/scheduler_worker/scheduler.py` | MODIFY | Register digest job |
| `server/apps/backend/app/routers/ai_internal.py` | MODIFY | Hook `notify_ai_task_complete()` |
| `server/apps/backend/app/routers/chores.py` | MODIFY | Hook `notify_chore_completed()` |
| `server/apps/backend/app/routers/child_wishes.py` | MODIFY | Hook `notify_wish_redeemed()` |
| `server/apps/backend/alembic/versions/xxx_add_digest_columns.py` | **NEW** | Migration for new columns |
| `frontend/apps/main/src/api/notificationChannels.ts` | MODIFY | Add `getEvents()`, update types |
| `frontend/apps/main/src/components/notification/EventSelectorPopup.vue` | **NEW** | Categorized event selector |
| `frontend/apps/main/src/pages/NotificationConfigPage.vue` | MODIFY | Use EventSelectorPopup, add mention/digest UI |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | MODIFY | Add all new i18n keys |

---

## Success Criteria

- [ ] `GET /notification-channels/events` returns 4 categories with 10 event types
- [ ] Frontend renders categorized bottom-sheet selector with correct i18n labels
- [ ] Creating a channel with new event types saves subscriptions correctly
- [ ] AI task completion triggers notification to subscribed channels
- [ ] Chore completion triggers notification to subscribed channels
- [ ] Wish redemption triggers notification to subscribed channels
- [ ] Telegram channel with mention config sends @username in group
- [ ] Feishu channel with mention config sends @user in group
- [ ] Channel with `digest_mode="daily"` receives one summary at 21:00
- [ ] Existing channels (immediate mode) continue to work without regression
- [ ] All tests pass (`pytest`, `ruff check`, `mypy`, `pnpm typecheck`)
