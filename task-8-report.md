# Task 8 Report: Notification Dispatcher Hooks at Existing Endpoints

## Summary

Wired up three notification dispatcher hooks at existing API endpoints, each guarded with try/except so notification failures never block the primary business operation.

## Changes Made

### 1. `server/apps/backend/app/routers/ai_internal.py`

**Endpoint:** `POST /api/v1/internal/tasks/{task_id}/complete`

**family_id verification:** ✅ Available via `family_id: str = Depends(verify_agent_token)` dependency — extracted from X-Family-Id header on the agent service token. Confirmed present in function signature before adding hook.

**Hook:** `notify_ai_task_complete(db, int(family_id), task_type, task_title)`

**Parameter derivation:**
- `task_type`: `task.skill_id or task.capability or "unknown"` — `skill_id` is the canonical field; `capability` is the legacy fallback (kept for backward compat per model comment).
- `task_title`: Priority order:
  1. `task.progress.get("result_summary")` (truncated to 100 chars) — the agent can optionally store a summary there
  2. `AIChatSession.title` or `AIChatSession.original_title` — queried via `task.session_id` when no result_summary is present
  3. Falls back to `task_type` string only if all above are empty (not passed to notify function)

**Exception handling:** Wrapped in `try/except Exception: pass` — notification failure must never block task completion.

---

### 2. `server/apps/backend/app/routers/chores.py`

**Endpoint:** `POST /api/v1/family/chore-approvals/{instance_id}/approve`

**family_id verification:** ✅ Available via `user: User = Depends(require_owner)` dependency. `user.family_id` is the authoritative family boundary. Also confirmed: `instance.family_id` from the ORM object (redundant but consistent).

**Hook:** `notify_chore_completed(db, user.family_id, child_name, chore_title)`

**Parameter derivation:**
- `child_name`: `getattr(instance, "_child_display_name", None) or (child.display_name if child else None) or "未知用户"` — `_child_display_name` is attached by `list_pending_approvals()` (service-side enrichment); falls back to querying the child User object that was already fetched for the blind-box trigger; last resort is a Chinese placeholder.
- `chore_title`: `instance.chore_name or "家务任务"` — `chore_name` is a snapshot column on ChoreInstance (preserved even if the template is renamed or deleted), making it the correct source over the template's `name`.

**Exception handling:** Wrapped in `try/except Exception: pass` — notification failure must never block chore approval.

---

### 3. `server/apps/backend/app/routers/child_wishes.py`

**Endpoint:** `POST /api/v1/family/child-wishes/{wish_id}/realize`

**family_id verification:** ✅ Available via `user: User = Depends(require_adult)` dependency. `user.family_id` is the authoritative family boundary.

**Hook:** `notify_wish_redeemed(db, user.family_id, wish_title, child_name)`

**Parameter derivation:**
- `wish_title`: `result.name` — the `ChildWish.name` field (the child-given name of the wish). Populated from `ParentWishResponse.name`.
- `child_name`: `result.child_display_name` — populated by `svc._get_child_name(db, wish.child_user_id)` inside `realize_child_wish()`, exposed on `ParentWishResponse.child_display_name` (string, non-nullable per schema).

**Exception handling:** Wrapped in `try/except Exception: pass` — notification failure must never block wish realization.

---

## Notes

- **No hardcoded family_id**: Every call uses family_id derived from the authenticated user context or the task/instance/chore object itself.
- **No integration tests added**: Per task instructions, these are integration points, not new endpoints. Existing tests continue to pass (6/6 in `test_notification_dispatcher.py`).
- **Import direction respected**: All imports flow `apps/backend → packages/db` (no reverse imports).
- **Incremental formatting**: Only touched files were formatted via `ruff check --fix`; no adjacent files modified.
- **Ruff lint**: All three files pass `ruff check` with zero errors after auto-fix of import ordering.

## Test Results

```
tests/backend/services/test_notification_dispatcher.py ......  [100%]
6 passed, 7 warnings
```

## Files Modified

- `/Volumes/LexarSSDNQ790/geek_space/github/numina_dev_space/numina/.superpowers/sdd/notification-module-enhancement/server/apps/backend/app/routers/ai_internal.py`
- `/Volumes/LexarSSDNQ790/geek_space/github/numina_dev_space/numina/.superpowers/sdd/notification-module-enhancement/server/apps/backend/app/routers/chores.py`
- `/Volumes/LexarSSDNQ790/geek_space/github/numina_dev_space/numina/.superpowers/sdd/notification-module-enhancement/server/apps/backend/app/routers/child_wishes.py`
