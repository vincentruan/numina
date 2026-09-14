
```bash
git add server/apps/backend/app/services/notification/push_service.py
git commit -m "fix(notification): skip reminder-pipeline events in push_service to avoid duplicates

chore_completed, treasure_redeemed, wish_redeemed are now handled by the
reminder pipeline. Skip them in push_service to prevent duplicate webpush.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Scheduler Digest Job

**Files:**
- Modify: `server/apps/scheduler_worker/jobs/__init__.py`
- Modify: `server/apps/scheduler_worker/scheduler.py`

**Rationale (CE review fix):** Use timezone-aware scheduling. For MVP, use server timezone with configurable hour. Future: add family timezone support.

- [ ] **Step 1: Add job function**

Add to `server/apps/scheduler_worker/jobs/__init__.py`:

```python
async def notification_digest_job() -> None:
    """Send daily digest notifications for channels with digest_mode='daily'."""
    from packages.db.session import SessionLocal  # noqa: PLC0415
    import logging

    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        from apps.backend.app.services.notification.dispatcher import _dispatch_digest  # noqa: PLC0415
        await _dispatch_digest(db)
        logger.info("Notification digest job completed")
    except Exception as e:
        logger.exception(f"Notification digest job failed: {e}")
    finally:
        db.close()
```

- [ ] **Step 2: Register job**

Add to `server/apps/scheduler_worker/scheduler.py` in `setup_all_jobs()`:

```python
from apps.scheduler_worker.jobs import notification_digest_job  # noqa: PLC0415

# Job 10: Notification digest — daily at 21:00
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
logger.info("通知摘要定时任务已配置（每日 21:00）")
```

- [ ] **Step 3: Commit**

```bash
git add server/apps/scheduler_worker/jobs/__init__.py server/apps/scheduler_worker/scheduler.py
git commit -m "feat(notification): add daily digest scheduler job at 21:00

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Integration Hooks

**Files:**
- Modify: `server/apps/backend/app/routers/ai_internal.py`
- Modify: `server/apps/backend/app/routers/chores.py`
- Modify: `server/apps/backend/app/routers/child_wishes.py`

**Rationale (CE review P0 fix):** Verify family_id is available at each integration point before calling dispatcher hooks.

- [ ] **Step 1: Hook AI task completion**

In `server/apps/backend/app/routers/ai_internal.py`, at the `internal_task_complete` endpoint:

```python
# After marking task as completed, add:
from apps.backend.app.services.notification.dispatcher import notify_ai_task_complete

# Extract family_id from the task or user context
family_id = task.family_id  # or user.family_id if task doesn't have it
task_type = task.skill_id  # e.g., "asset-report", "finance-coach"
task_title = task.title or task.skill_id

notify_ai_task_complete(db, family_id, task_type, task_title)
```

