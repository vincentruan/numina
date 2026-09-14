```bash
git add server/apps/backend/app/services/notification/registry.py server/tests/backend/services/test_notification_registry.py
git commit -m "feat(notification): add event registry replacing hardcoded VALID_REMINDER_TYPES

Registry lives in apps/backend (not packages/core) since only backend
dispatcher and frontend consume events. Provides get_categorized_events()
for API and VALID_REMINDER_TYPES set for backward-compatible router use.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Database Migration

**Files:**
- Create: `server/apps/backend/alembic/versions/<timestamp>_add_notification_enhancements.py`
- Modify: `server/packages/db/models/notification_channel.py`
- Modify: `server/packages/db/models/reminder.py`

**Interfaces:**
- Consumes: nothing
- Produces: `notification_channels.digest_mode`, `notification_channels.digest_time`, `reminders.digest_sent_at`

**Rationale (CE review fix):** Add `digest_sent_at` to Reminder model (not change status to "resolved") so digest delivery is tracked separately from user acknowledgment.

- [ ] **Step 1: Update models**

Modify `server/packages/db/models/notification_channel.py` — add two columns:

```python
# Add after the is_enabled field (around line 19):
digest_mode: Mapped[str] = mapped_column(String(20), nullable=False, server_default="immediate")
digest_time: Mapped[str] = mapped_column(String(10), nullable=False, server_default="21:00")
```

Modify `server/packages/db/models/reminder.py` — add one column:

```python
# Add after the resolved_at field:
digest_sent_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
```

- [ ] **Step 2: Generate migration**

```bash
cd server/apps/backend && uv run alembic revision --autogenerate -m "add_notification_enhancements"
```

- [ ] **Step 3: Verify migration**

```bash
cd server/apps/backend && uv run alembic upgrade head
```

- [ ] **Step 4: Update schema**

Modify `server/apps/backend/app/schemas/notification_channel.py`:

```python
# Add to NotificationChannelCreate:
digest_mode: str = "immediate"
digest_time: str = "21:00"

# Add to NotificationChannelUpdate:
digest_mode: str | None = None
digest_time: str | None = None

# Add to NotificationChannelResponse:
digest_mode: str = "immediate"
digest_time: str = "21:00"
```

- [ ] **Step 5: Commit**

```bash
git add server/packages/db/models/notification_channel.py server/packages/db/models/reminder.py server/apps/backend/app/schemas/notification_channel.py server/apps/backend/alembic/versions/*notification_enhancements*
git commit -m "feat(notification): add digest_mode, digest_time, digest_sent_at columns

Adds per-channel digest configuration and tracks digest delivery separately
from user acknowledgment (digest_sent_at vs resolved_at).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Notification Templates

**Files:**
- Create: 7 template JSON files in `server/apps/backend/app/services/notification/templates/`

**Rationale (CE review fix):** Create templates for all 7 new event types. Note: `maturity.json` already exists (review finding was incorrect).

- [ ] **Step 1: Create AI task templates**

Create `server/apps/backend/app/services/notification/templates/ai_report_complete.json`:
```json
{
