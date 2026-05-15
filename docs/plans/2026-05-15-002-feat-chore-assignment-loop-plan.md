---
title: "feat: Chore Assignment & Claim Loop"
type: feat
status: active
date: 2026-05-15
origin: docs/brainstorms/2026-05-15-chore-assignment-loop-requirements.md
---

# feat: Chore Assignment & Claim Loop

## Overview

Closes the task management loop for pool chores by adding:

1. **Parent side (BabyPage):** task cards show claim status; parent can assign, reassign, or void individual instances.
2. **Child side (ChildTasksPage + ChildHomePage):** children see unclaimed pool tasks alongside their own; can claim or abandon with a motivational abandon dialog.
3. **Backend:** four new endpoints, two new `ChoreInstance` columns, and a widened child chore query.

## Problem Frame

Pool chores (`child_user_id == family_id`) are currently invisible to children and unmanageable at the instance level by parents. A child can only see and act on tasks already assigned to them. Parents cannot direct a specific child to do a pool task, nor cancel a task for the day. This leaves pool chores as a half-implemented feature. (See origin: `docs/brainstorms/2026-05-15-chore-assignment-loop-requirements.md`)

## Requirements Trace

- R1. Parent sees claim/assign status on every pool task card in BabyPage task tab
- R2. Parent can hard-assign a pool instance to a specific child (other children cannot see/claim it)
- R3. Parent can reassign an already-claimed/assigned instance to a different child
- R4. Parent can void an instance (hard-delete); template is preserved; next period regenerates normally
- R5. Child sees unclaimed pool tasks + tasks assigned to them in ChildTasksPage and ChildHomePage
- R6. Child can claim an unclaimed pool task (first-come-first-served, concurrency-safe)
- R7. Child sees motivational abandon dialog (coin reward + top wish progress) before confirming abandon
- R8. Abandoned task returns to unclaimed pool; parent receives silent notification
- R9. All mutations have optimistic UI updates with server-side rollback on failure
- R10. All new UI strings in zh-CN.ts and en-US.ts

## Scope Boundaries

- No child-initiated task creation
- No batch assign by parent
- No change to `assigned`-type template logic (template-level assignees unchanged)
- No change to approval/rejection flow

### Deferred to Separate Tasks

- Push notifications (mobile) for abandon events: separate notification infrastructure work
- Weekly pool chore claim semantics (current plan covers daily; weekly follows same logic but not explicitly tested)

## Context & Research

### Relevant Code and Patterns

- `server/apps/backend/app/models/chore.py` — `ChoreInstance` model; unique constraint on `(template_id, child_user_id, date_bucket)`
- `server/apps/backend/app/services/chores.py` — `mark_complete`, `approve_instance_async`, `reject_instance` as patterns for status transitions
- `server/apps/backend/app/routers/chores.py` — existing endpoint structure; `require_adult` / `require_owner` / `get_current_child_user` auth deps
- `server/apps/backend/app/services/notification_bus.py` — `fire_notification(family_id, event_dict)` for async broadcast
- `server/apps/backend/app/schemas/chore.py` — `ChoreInstanceResponse(SnowflakeBase)` for ID serialization
- `frontend/apps/main/src/pages/BabyPage.vue` — task tab uses `filteredChores` computed from `allChores`; `getChildrenChores(today)` API call
- `frontend/apps/main/src/components/dashboard/PendingApprovalsSection.vue` — piano-key button pattern to reuse for assign/void actions
- `frontend/apps/child/src/pages/ChildTasksPage.vue` — chore card loop, `complete()` action pattern
- `frontend/apps/child/src/pages/ChildHomePage.vue` — today's tasks section, same card pattern
- `frontend/apps/child/src/api/chores.ts` — `ChoreInstance` interface, `getMyChores`, `markChoreComplete`

### Institutional Learnings

- `docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md` — batch endpoints prevent N+1; pool chore `child_user_id == family_id` convention
- `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md` — acquire locks before executor; session lifecycle owned by caller
- Snowflake IDs serialize as strings via `SnowflakeBase`; never call `str()` manually in routers

### External References

- SQLAlchemy `with_for_update()` for row-level locking during claim (prevents double-claim race)

## Key Technical Decisions

- **Claim concurrency:** Use `SELECT FOR UPDATE` on the instance row inside a transaction. If `child_user_id != family_id` when the lock is acquired, raise 409 Conflict. This is simpler and more reliable than catching `IntegrityError` from a unique constraint change.
- **Assign/reassign semantics:** Mutate `child_user_id` on the existing instance (no new row). Set `assigned_by_user_id` to the parent's ID. This preserves the unique constraint `(template_id, child_user_id, date_bucket)` — but since we're changing `child_user_id` from `family_id` to a child ID, the old pool row is effectively replaced. If a child had already claimed it (child_user_id == child.id), reassign updates to the new child.
- **Void = hard delete:** Deletes the instance row. The unique constraint is released, so `get_or_create_instances` regenerates it next period. No soft-delete needed — voiding is intentional and the template is the source of truth.
- **Child chore query widening:** `GET /child/chores?date=` currently filters `child_user_id == child.id`. Widen to `child_user_id IN (child.id, child.family_id)` to include pool tasks. Exclude instances where `assigned_by_user_id IS NOT NULL AND child_user_id != child.id` (hard-assigned to someone else — these should not be visible).
- **`is_pool_unclaimed` flag:** Add a computed boolean to `ChoreInstanceResponse` so the frontend can distinguish "unclaimed pool" from "assigned to me" without re-deriving from IDs. Set server-side: `child_user_id == family_id AND assigned_by_user_id IS NULL`.
- **Abandon notification type:** `chore_abandoned` event fires to family WebSocket; parent UI can react. Child receives no notification (silent from child's perspective).
- **Motivational dialog data:** Child frontend fetches top active wish from already-available `listChildWishes()` at page load; no new API needed. Remaining coins = `wish.star_coin_cost - current_balance` (balance already loaded on page).

## Open Questions

### Resolved During Planning

- **Hard-delete vs soft-delete for void:** Hard-delete chosen. Soft-delete adds complexity (filtering voided instances everywhere) with no benefit — the template regenerates the instance next period.
- **Reassign while pending_approval:** Disallow. If status is `pending_approval` or `approved`, the assign endpoint returns 409. Parent must reject first, then reassign.
- **Abandon while pending_approval:** Disallow. Child can only abandon `available` instances.
- **Who can assign:** `require_adult` (both owner and co-parent). Void also `require_adult`.

### Deferred to Implementation

- Exact SQL for widened child query — depends on seeing the ORM filter in context
- Whether `with_for_update()` needs `skip_locked=True` or plain lock — test under SQLite (dev) vs Postgres (prod) behavior
- Whether `ChoreInstanceResponse` computed field `is_pool_unclaimed` should use `@computed_field` (Pydantic v2) or be set as a transient attribute in the router (like existing `_child_display_name` pattern)

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

### State transitions for a pool instance

```
[family_id, available]
        │
        ├─── parent assign ──────────────────────────────────────────────────────┐
        │                                                                         │
        ▼                                                                         ▼
[child_id, available]  ←── child claim ──  [family_id, available]        [child_id, available]
  (claimed/assigned)                        (still unclaimed)              (hard-assigned)
        │                                                                         │
        ├─── child abandon ──► [family_id, available]  (back to pool)            │
        │                                                                         │
        ├─── child complete ──► [child_id, pending_approval]                     │
        │                              │                                          │
        │                    approve / reject                                     │
        │                              │                                          │
        │                    [approved] / [available/rejected]                   │
        │                                                                         │
        └─── parent void ──► (row deleted)  ◄──────────────────────────────────┘
```

### New API surface

```
POST /family/chore-instances/{id}/assign
  body: { child_user_id: int }
  guard: status must be 'available'
  effect: child_user_id ← target child, assigned_by_user_id ← parent.id

DELETE /family/chore-instances/{id}
  guard: status must be 'available' (not pending/approved)
  effect: hard-delete row

POST /child/chores/{id}/claim
  guard: SELECT FOR UPDATE; child_user_id must == family_id
  effect: child_user_id ← child.id, claimed_at ← now

POST /child/chores/{id}/abandon
  guard: status must be 'available'; child_user_id must == child.id
  effect: child_user_id ← family_id, claimed_at ← null, assigned_by_user_id ← null
  side-effect: fire chore_abandoned notification to family
```

## Implementation Units

- [ ] **Unit 1: DB migration — add `assigned_by_user_id` and `claimed_at` to `chore_instances`**

  **Goal:** Add two nullable columns to `ChoreInstance` to track who assigned and when a pool task was claimed.

  **Requirements:** R2, R6, R8

  **Dependencies:** None

  **Files:**
  - Create: `server/apps/backend/alembic/versions/<rev>_add_chore_instance_assignment_fields.py`
  - Modify: `server/apps/backend/app/models/chore.py`

  **Approach:**
  - Add `assigned_by_user_id: Mapped[int | None]` (BigInteger FK to users.id, nullable)
  - Add `claimed_at: Mapped[datetime | None]` (DateTime, nullable)
  - Migration: `op.add_column` for both; `op.drop_column` in downgrade
  - No index needed on these columns (low-cardinality lookups always scoped by instance ID)

  **Patterns to follow:**
  - `server/apps/backend/app/models/chore.py` — existing `submitted_by_user_id` column as direct pattern
  - Recent migration files in `server/apps/backend/alembic/versions/` for revision ID format and docstring style

  **Test scenarios:**
  - Test expectation: none — pure schema migration; behavioral coverage in Units 2–4

  **Verification:**
  - `uv run alembic upgrade head` succeeds without error
  - `uv run alembic downgrade -1` succeeds and removes the columns

---

- [ ] **Unit 2: Backend — assign, reassign, and void endpoints**

  **Goal:** Parent can hard-assign a pool instance to a child, reassign it, or void (delete) it.

  **Requirements:** R2, R3, R4

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `server/apps/backend/app/services/chores.py`
  - Modify: `server/apps/backend/app/routers/chores.py`
  - Modify: `server/apps/backend/app/schemas/chore.py`
  - Test: `server/tests/backend/test_chore_assignment.py`

  **Approach:**
  - `assign_instance(db, parent, instance_id, target_child_id)` service function:
    - Fetch instance, verify `family_id` matches, verify status is `available`
    - Verify `target_child_id` is a child in the same family
    - Set `child_user_id = target_child_id`, `assigned_by_user_id = parent.id`
    - Clear `claimed_at` (reassign resets claim timestamp)
    - Commit and return instance
  - `void_instance(db, parent, instance_id)` service function:
    - Fetch instance, verify `family_id` matches, verify status is `available`
    - Hard-delete with `db.delete(instance)`
    - Commit; return nothing (204)
  - Router: `POST /family/chore-instances/{id}/assign` (require_adult, 200) and `DELETE /family/chore-instances/{id}` (require_adult, 204)
  - Add `AssignRequest(BaseModel)` schema with `child_user_id: int`
  - Add `assigned_by_user_id: int | None` and `claimed_at: datetime | None` to `ChoreInstanceResponse`
  - Add `is_pool_unclaimed: bool` computed field to `ChoreInstanceResponse` — set in router as transient attribute (follow `_child_display_name` pattern)

  **Patterns to follow:**
  - `reject_instance` in `server/apps/backend/app/services/chores.py` for status-guard pattern
  - `require_adult` dep in `server/apps/backend/app/routers/chores.py`
  - `SnowflakeBase` in `server/apps/backend/app/schemas/chore.py` for response schema

  **Test scenarios:**
  - Happy path: assign unclaimed pool instance → `child_user_id` updated, `assigned_by_user_id` set, 200 returned
  - Happy path: reassign already-claimed instance → `child_user_id` updated to new child, `claimed_at` cleared
  - Happy path: void available instance → row deleted, 204 returned
  - Edge case: assign to non-child user in family → 422/403
  - Edge case: assign to child in different family → 404
  - Error path: assign instance with status `pending_approval` → 409 Conflict
  - Error path: assign instance with status `approved` → 409 Conflict
  - Error path: void instance with status `pending_approval` → 409 Conflict
  - Error path: assign non-existent instance → 404
  - Integration: after void, `get_or_create_instances` for same template/child/date creates a fresh instance

  **Verification:**
  - `uv run pytest tests/backend/test_chore_assignment.py -v` passes
  - `uv run mypy app/` passes
  - `uv run ruff check .` passes

---

- [ ] **Unit 3: Backend — claim and abandon endpoints + widened child query**

  **Goal:** Child can claim an unclaimed pool task (concurrency-safe) and abandon a claimed/assigned task. Child chore query returns pool tasks alongside personal tasks.

  **Requirements:** R5, R6, R8

  **Dependencies:** Unit 1

  **Files:**
  - Modify: `server/apps/backend/app/services/chores.py`
  - Modify: `server/apps/backend/app/routers/chores.py`
  - Test: `server/tests/backend/test_chore_claim_abandon.py`

  **Approach:**
  - `claim_instance(db, child, instance_id)` service function:
    - `SELECT FOR UPDATE` on the instance row
    - Verify `child_user_id == child.family_id` (still unclaimed) — raise 409 if already claimed
    - Verify status is `available`
    - Set `child_user_id = child.id`, `claimed_at = datetime.utcnow()`
    - Commit and return instance
  - `abandon_instance(db, child, instance_id)` service function:
    - Fetch instance, verify `child_user_id == child.id` and status is `available`
    - Set `child_user_id = child.family_id`, `claimed_at = None`, `assigned_by_user_id = None`
    - Fire `chore_abandoned` notification to family
    - Commit and return instance
  - Widen `get_or_create_instances` query: include rows where `child_user_id == child.family_id AND assigned_by_user_id IS NULL` (unclaimed pool) in addition to `child_user_id == child.id`
  - Router: `POST /child/chores/{id}/claim` and `POST /child/chores/{id}/abandon` (both `get_current_child_user`)
  - Set `is_pool_unclaimed` transient attribute before returning from both endpoints

  **Patterns to follow:**
  - `mark_complete` in `server/apps/backend/app/services/chores.py` for child-side status transition pattern
  - `fire_notification` call pattern from `mark_complete`
  - `with_for_update()` SQLAlchemy pattern for claim lock

  **Test scenarios:**
  - Happy path: claim unclaimed pool instance → `child_user_id` set to child, `claimed_at` set, `is_pool_unclaimed` false
  - Happy path: abandon claimed instance → `child_user_id` reset to `family_id`, `claimed_at` null, `chore_abandoned` notification fired
  - Happy path: abandon hard-assigned instance → same reset behavior
  - Edge case: two children claim same instance concurrently → second gets 409 Conflict
  - Edge case: claim instance already claimed by another child → 409 Conflict
  - Edge case: claim instance that was hard-assigned to a different child → 404 (not visible to this child)
  - Error path: abandon instance with status `pending_approval` → 409
  - Error path: abandon instance belonging to different child → 404
  - Integration: after abandon, `get_or_create_instances` for another child includes the now-unclaimed instance
  - Integration: widened child query returns pool unclaimed tasks alongside personal tasks for same date

  **Verification:**
  - `uv run pytest tests/backend/test_chore_claim_abandon.py -v` passes
  - `uv run mypy app/` passes
  - `uv run ruff check .` passes

---

- [ ] **Unit 4: Frontend — child app task pages (ChildTasksPage + ChildHomePage)**

  **Goal:** Children see unclaimed pool tasks and their own tasks; can claim or abandon with motivational dialog.

  **Requirements:** R5, R6, R7, R8, R9, R10

  **Dependencies:** Unit 3

  **Files:**
  - Modify: `frontend/apps/child/src/api/chores.ts`
  - Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`
  - Modify: `frontend/apps/child/src/pages/ChildHomePage.vue`
  - Modify: `frontend/apps/child/src/i18n/locales/zh-CN.ts`
  - Modify: `frontend/apps/child/src/i18n/locales/en-US.ts`

  **Approach:**
  - Add `is_pool_unclaimed: boolean` and `assigned_by_user_id: string | null` and `claimed_at: string | null` to `ChoreInstance` interface in `chores.ts`
  - Add `claimChore(instanceId: string)` → `POST /child/chores/{id}/claim`
  - Add `abandonChore(instanceId: string)` → `POST /child/chores/{id}/abandon`
  - **ChildTasksPage:** Replace single `complete()` action with three: `claim()`, `complete()`, `abandon()`
    - Card action area: if `is_pool_unclaimed` → show `认领` button; else if `available` → show `完成` + `放弃` buttons
    - `claim()`: optimistic update `is_pool_unclaimed = false`, call API, revert on error
    - `abandon()`: open motivational bottom sheet (see below), on confirm call API, remove card from list
  - **Motivational abandon sheet:** Bottom popup (not `showConfirmDialog`) with:
    - Chore name + coin reward display
    - Top active wish name + remaining coins (derived from `topWish` already loaded on page; `remaining = wish.star_coin_cost - balance`)
    - Primary button: `继续完成` (brand pink, closes sheet)
    - Secondary button: `放弃任务` (gray, calls `doAbandon()`)
  - **ChildHomePage:** Apply same card action logic to `todayChores` section; reuse same `claim()` / `abandon()` pattern; `topWish` already loaded at mount
  - All new strings via i18n keys (no hardcoded Chinese)

  **Patterns to follow:**
  - `frontend/apps/child/src/pages/ChildTasksPage.vue` — existing `complete()` action and optimistic update pattern
  - `frontend/apps/main/src/components/dashboard/PendingApprovalsSection.vue` — piano-key button row style
  - `frontend/apps/child/src/pages/ChildHomePage.vue` — `topWish` and `balance` already available at mount

  **Test scenarios:**
  - Test expectation: none — UI component; verify manually in browser at 375px width
  - Typecheck: `npm run typecheck` must pass with no errors

  **Verification:**
  - `npm run typecheck` passes in `frontend/apps/child/`
  - Claim button appears on unclaimed pool tasks; disappears after claim
  - Abandon sheet shows coin reward and wish name when top wish exists
  - Abandon sheet shows only coin reward when no active wish
  - Abandoned task disappears from list
  - Optimistic update reverts if API returns error

---

- [ ] **Unit 5: Frontend — parent BabyPage task tab enhancements**

  **Goal:** Parent sees claim/assign status on pool task cards; can assign, reassign, or void instances.

  **Requirements:** R1, R2, R3, R4, R9, R10

  **Dependencies:** Unit 2

  **Files:**
  - Modify: `frontend/apps/main/src/api/chores.ts`
  - Modify: `frontend/apps/main/src/pages/BabyPage.vue`
  - Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
  - Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

  **Approach:**
  - Add `is_pool_unclaimed: boolean`, `assigned_by_user_id: string | null`, `claimed_at: string | null` to `ChoreInstance` interface in main app `chores.ts`
  - Add `assignChoreInstance(instanceId: string, childUserId: string)` → `POST /family/chore-instances/{id}/assign`
  - Add `voidChoreInstance(instanceId: string)` → `DELETE /family/chore-instances/{id}`
  - **BabyPage task tab:** Replace `van-cell` list with richer cards:
    - Show assignee avatar + name if `child_user_id` is set and not `is_pool_unclaimed`
    - Show "无主" tag if `is_pool_unclaimed`
    - Piano-key action row (follow `PendingApprovalsSection` style):
      - Unclaimed (`is_pool_unclaimed`): `指派` button
      - Claimed/assigned + `available`: `改派` + `作废` buttons
      - `pending_approval` / `approved` / `rejected`: no action buttons
    - `指派` / `改派` opens child-picker bottom sheet (reuse existing `showChildPicker` popup from grant-stars flow)
    - `作废` shows `showConfirmDialog` then calls `voidChoreInstance`
  - Optimistic update: remove voided card immediately; revert on error

  **Patterns to follow:**
  - `frontend/apps/main/src/components/dashboard/PendingApprovalsSection.vue` — piano-key `.card-actions` / `.action-btn` CSS classes
  - `frontend/apps/main/src/pages/BabyPage.vue` — existing `showChildPicker` popup and `selectChildAndGrant` pattern for child selection

  **Test scenarios:**
  - Test expectation: none — UI component; verify manually in browser at 375px width
  - Typecheck: `npm run typecheck` must pass with no errors

  **Verification:**
  - `npm run typecheck` passes in `frontend/apps/main/`
  - Pool task cards show "无主" tag when unclaimed
  - Pool task cards show assignee avatar when claimed/assigned
  - Assign flow opens child picker, updates card on success
  - Void flow shows confirm dialog, removes card on success
  - Non-pool (assigned-type) tasks show no action buttons

## System-Wide Impact

- **Interaction graph:** `get_or_create_instances` is called on every child chore page load — widening its query affects all children in the family simultaneously. Ensure the new filter does not return duplicate rows (pool instance appears once, not once per child).
- **Error propagation:** Claim 409 should surface as a friendly toast ("任务已被认领") not a generic error. Abandon 409 (wrong status) should surface similarly.
- **State lifecycle risks:** After void, the parent's `allChores` list must remove the card immediately (optimistic). If the parent refreshes before the child's next page load, the child will see the pool task regenerated on next `get_or_create_instances` call — this is correct behavior.
- **API surface parity:** `ChoreInstanceResponse` gains three new fields (`assigned_by_user_id`, `claimed_at`, `is_pool_unclaimed`). All existing callers receive these as nullable additions — no breaking change.
- **Integration coverage:** The claim concurrency scenario (two children, one instance) requires an integration test with two DB sessions, not a unit test with mocks.
- **Unchanged invariants:** Approval/rejection flow, streak computation, coin transactions, blind box trigger, and milestone checks are all untouched. The `submitted_by_user_id` field continues to track the actual submitter for pool chores after claim.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Claim race condition under concurrent load | `SELECT FOR UPDATE` inside transaction; 409 on stale read |
| `get_or_create_instances` returns duplicate pool row | Filter carefully: `child_user_id IN (child.id, family_id)` with `assigned_by_user_id IS NULL` guard for pool rows; add integration test |
| Void while child has the task open | Child's local state shows stale card; next API call returns 404 — handle gracefully with toast and list refresh |
| SQLite `SELECT FOR UPDATE` in dev/test | SQLite ignores `FOR UPDATE` but serializes writes anyway; test concurrency on Postgres in CI if available, otherwise document the limitation |
| BabyPage task tab redesign breaks existing chore display | Keep `van-cell` fallback for non-pool (assigned) tasks; only pool tasks get the new card treatment |

## Documentation / Operational Notes

- Run `uv run alembic upgrade head` on all environments before deploying (Unit 1 migration)
- New notification event type `chore_abandoned` — any WebSocket client consuming family events should handle or ignore gracefully
- `is_pool_unclaimed` is a computed response field, not stored — no migration needed for it
