---
date: 2026-05-19
status: active
origin: docs/brainstorms/2026-05-19-blindbox-trigger-expansion-requirements.md
---

# BlindBox Trigger Expansion — Implementation Plan

Extends the blindBox reward system with two new trigger types: (1) streak/cumulative task milestone triggers, and (2) parent challenge grants with conditional targets and deadlines.

## Problem Frame

Kids currently only receive blind box draws via manual coin spending or probabilistic `base_draw_prob` on approval. This misses two key motivation moments:
1. Celebrating sustained effort patterns (streak milestones, cumulative task counts)
2. Parent-initiated goal challenges (active incentive channel, not just passive wish responses)

**Design constraints from origin doc:**
- Reuse existing milestone infrastructure, no new scheduler
- Challenge progress updates atomically within approval transaction
- Failure never blocks approval flow (try/except wrapper)

---

## Scope

### In Scope
- `streak_3` milestone (per-cycle trigger)
- `tasks_10/25/50/100` milestones (once-per-child lifetime)
- Milestone-triggered draws using surprise pool (value_score >= 7)
- Four challenge types: task_count, streak_length, specific_chore, star_earnings
- Progress tracking and completion reward (7-day BonusDraw)
- Lazy expiration check on next approval
- Cancel endpoint for parents
- Child app: active challenge progress display
- Parent app: challenge creation form

### Deferred
- Challenge completion push notifications (await notification infrastructure)
- Challenge templates/presets
- Multi-child family challenges

### Outside Identity
- Direct coin rewards (only draws)
- Badge/achievement system

---

## Implementation Units

### U1. Add `total_approved_count` to User model

**File:** `server/packages/db/models/user.py`

Add cumulative task counter for milestone thresholds:

```python
total_approved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
```

**Migration:** New Alembic migration adds column with default 0.

**Test scenarios:**
- Column exists after migration
- Default value is 0 for existing users
- Increment persists across transactions

---

### U2. Extend streak milestones (streak_3)

**File:** `server/apps/backend/app/services/milestones.py`

**Changes:**
1. Add `{3: "streak_3"}` to `_STREAK_MILESTONES`
2. Add `"streak_3"` to `_PER_CYCLE` set (re-triggers each new cycle)
3. Update `_VALID_MILESTONE_TYPES` to include new type

**Pattern reference:** Existing `streak_7/14/30` logic in `_try_record_streak_cycle_cached()` handles cycle detection via `prev_instance.streak_count` comparison.

**Test scenarios:**
- Child with streak 3 triggers `streak_3` milestone
- Same cycle: streak 4 does NOT re-trigger
- New cycle: streak drops to 0, rebuilds to 3 → triggers again
- Milestone record has correct `ref_id` and `ref_type`

---

### U3. Add task count milestones

**File:** `server/apps/backend/app/services/milestones.py`

**Changes:**
1. Define `_TASK_MILESTONES = {10: "tasks_10", 25: "tasks_25", 50: "tasks_50", 100: "tasks_100"}`
2. Add all to `_ONCE_PER_CHILD` set
3. Add `_check_task_milestones()` helper that:
   - Reads `child.total_approved_count` from context or queries User
   - Checks thresholds in ascending order
   - Calls `_try_record_once_cached()` for each eligible threshold

**Integration point:** Call `_check_task_milestones()` in `_check_milestones()` after streak logic.

**Test scenarios:**
- Child at count 10 triggers `tasks_10`
- Child at count 25 triggers both `tasks_10` AND `tasks_25` (batch)
- Already has `tasks_10`: count 11 → no new trigger
- Once-per-child: cannot re-trigger even if count resets

---

### U4. Increment counter in approval flow

**File:** `server/apps/backend/app/services/chores.py`

**Change in `approve_instance_async()`:** After successful approval, increment:

```python
child.total_approved_count += 1
```

Wrap in try/except — failure to increment should not block (log warning, continue).

**Pattern reference:** Current milestone check at line 334-338 uses try/except wrapper.

**Test scenarios:**
- Counter increments on each approval
- Counter persists across sessions
- Failure logs warning, approval still succeeds

---

### U5. Milestone-triggered draw helper

**File:** `server/apps/backend/app/services/milestones.py`

Add `_create_milestone_draw()` helper that creates `BlindBoxDraw` with:
- `coins_spent=0`
- `is_surprise=True`
- `is_auto_triggered=True`
- `status="pending_fulfillment"`
- Gift from surprise pool (`value_score >= 7`)

Reuse existing pool selection logic from `blind_box.py:should_upgrade_surprise()` — milestone draws always use surprise pool.

**Integration:** After `_insert_milestone()` flush, call `_create_milestone_draw()` for the triggered milestone.

**Error handling:** Wrap in try/except, log to `_audit_logger`, return None on failure (never blocks milestone record).

**Test scenarios:**
- Milestone triggers → BlindBoxDraw created with correct params
- Surprise pool empty → falls back to full pool
- Draw creation fails → milestone still recorded, audit log entry

---

### U6. ChallengeGrant model

**New file:** `server/apps/backend/app/models/challenge_grant.py`

```python
class ChallengeGrant(Base):
    __tablename__ = "challenge_grants"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'expired', 'cancelled')", name="ck_challenge_grant_status"),
        CheckConstraint("target_type IN ('task_count', 'streak_length', 'specific_chore', 'star_earnings')", name="ck_challenge_grant_target_type"),
    )
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    chore_template_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chore_templates.id"), nullable=True)
    current_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
```

**Validation:** `chore_template_id` required when `target_type == "specific_chore"`.

**Migration:** New Alembic migration with BigInteger Snowflake IDs, check constraints.

**Test scenarios:**
- Model validates required fields
- Check constraints reject invalid status/target_type
- Snowflake ID generation works

---

### U7. ChallengeGrant service

**New file:** `server/apps/backend/app/services/challenge_grants.py`

**Functions:**

1. `create_challenge(db, parent, child_id, target_type, target_value, deadline, message, chore_template_id)`:
   - Validate child belongs to family
   - Check `count(active) < 3` for child
   - Validate `chore_template_id` when `specific_chore`

2. `check_challenge_progress(db, child_user_id, family_id, instance)`:
   - Lazy expiration: mark `status="expired"` for any `deadline < now()` AND `status="active"`
   - For each active challenge, call `_update_progress_for_type()`
   - Check completion: if `current_progress >= target_value`, mark `status="completed"`, create `BonusDraw`

3. `_update_progress_for_type(challenge, instance, child)`:
   - `task_count`: `current_progress += 1`
   - `streak_length`: check `instance.streak_count >= target_value` (binary, not cumulative)
   - `specific_chore`: `current_progress += 1` only if `instance.template_id == challenge.chore_template_id`
   - `star_earnings`: `current_progress += (coin_reward + streak_bonus)`

4. `cancel_challenge(db, parent, challenge_id)`:
   - Validate ownership (family match)
   - Only `status="active"` can cancel
   - Set `status="cancelled"`

**Integration:** Call `check_challenge_progress()` in `approve_instance_async()` after milestone check.

**Error handling:** All challenge operations wrapped in try/except, logged, never block approval.

**Test scenarios:**
- Create succeeds when < 3 active challenges
- Create fails when >= 3 active
- Progress updates correctly per type
- Expiration marks expired before progress check
- Completion creates BonusDraw with 7-day expiry
- Cancel works on active, fails on completed/expired

---

### U8. BonusDraw source_challenge_id

**File:** `server/apps/backend/app/models/bonus_draw.py`

Add:
```python
source_challenge_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("challenge_grants.id"), nullable=True)
```

**Migration:** Add column nullable, no default.

**Test scenarios:**
- Column exists after migration
- NULL for non-challenge sources (wish milestones)
- FK constraint valid

---

### U9. Child app challenge UI

**Files:**
- `frontend/apps/child/src/types/challengeGrant.ts` (types)
- `frontend/apps/child/src/api/challengeGrant.ts` (API client)
- `frontend/apps/child/src/components/ChallengeCard.vue` (progress display)
- `frontend/apps/child/src/pages/ChildHomePage.vue` (integration)
- `frontend/apps/child/src/i18n/locales/zh-CN.ts` (i18n keys)

**ChallengeCard.vue design:**
- Show target type icon (task/streak/chore/star)
- Progress bar: `current_progress / target_value`
- Deadline countdown
- Encouragement message if set
- Vant progress bar component

**Integration:** Fetch active challenges on page load, display in section below chore list.

**i18n keys:**
```ts
challenge: {
  taskCount: '累计任务',
  streakLength: '连续打卡',
  specificChore: '指定家务',
  starEarnings: '星币累计',
  progress: '进度',
  daysLeft: '剩余 {n} 天',
  completed: '🎉 挑战完成！',
  expired: '挑战已过期',
  active: '进行中',
}
```

**Test scenarios:**
- Active challenges display with progress
- Completed challenges show celebration state
- Expired challenges show grey/expired state
- i18n keys render correctly

---

### U10. Parent app challenge creation

**Files:**
- `frontend/apps/main/src/types/challengeGrant.ts` (types)
- `frontend/apps/main/src/api/challengeGrant.ts` (API client)
- `frontend/apps/main/src/components/ChallengeCreator.vue` (creation form)
- `frontend/apps/main/src/pages/BlindBoxConfigPage.vue` (integration)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (i18n keys)

**ChallengeCreator.vue design:**
- Child selector (dropdown)
- Target type selector (4 options)
- Target value input (number)
- Deadline picker (Vant datetime picker)
- Message input (optional, max 100 chars)
- Template picker when `specific_chore` type

**i18n keys:**
```ts
challenge: {
  create: '创建挑战',
  selectChild: '选择孩子',
  targetType: '挑战类型',
  targetValue: '目标值',
  deadline: '截止日期',
  encouragement: '鼓励消息',
  selectChore: '选择家务',
  maxChallengesReached: '⚠️ 该孩子已有3个进行中的挑战',
  createdSuccess: '✅ 挑战创建成功',
}
```

**Test scenarios:**
- Form validates required fields
- Template picker shows only when specific_chore
- Max challenges check blocks creation
- Success toast on creation
- Cancel button works on existing challenges

---

## Backend API Endpoints

### Parent endpoints (in new router `challenge_grant.py`)
- `GET ""` — list all family challenges
- `POST ""` — create challenge (status 201)
- `POST "/{id}/cancel"` — cancel active challenge

### Child endpoints (child-facing router)
- `GET "/active"` — list child's active challenges with progress

**URL convention:** No trailing slashes (per CLAUDE.md `redirect_slashes=False` rule).

---

## Dependencies

1. U1 (total_approved_count) → U3 (task milestones) → U4 (increment)
2. U2 (streak_3) → U5 (milestone draw)
3. U6 (ChallengeGrant model) → U7 (service) → U8 (BonusDraw FK)
4. U6 + U7 → U9 (child UI) → U10 (parent UI)

**Recommended sequence:** U1 → U6 → U8 (models+migrations) → U2 → U3 → U4 → U5 → U7 → U9 → U10

---

## Risks

| Risk | Mitigation |
|------|------------|
| Challenge progress race condition | Wrap in transaction, use SELECT FOR UPDATE pattern from chores.py |
| Surprise pool empty | Fallback to full pool (existing behavior in blind_box.py) |
| Migration conflict with BonusDraw | Add column nullable, backfill NULL for existing |
| 3-challenge limit bypass via direct API | Enforce in service layer, not just UI |

---

## Verification Commands

After implementation:
1. `cd server/apps/backend && uv run ruff check app/models/challenge_grant.py app/services/challenge_grants.py app/services/milestones.py`
2. `cd frontend/apps/child && npm run typecheck`
3. `cd frontend/apps/main && npm run typecheck`
4. `cd server/apps/backend && uv run pytest tests/ -v -k challenge`

---

## Success Criteria (from origin doc)

1. Child with 3-day streak triggers milestone draw
2. Child with 10/25/50/100 cumulative tasks triggers milestone draw
3. Parent can create 4 challenge types with deadline and message
4. Child sees active challenge progress bar
5. Challenge completion grants 7-day BonusDraw
6. Expired challenges do not grant reward
7. All operations non-blocking on approval flow