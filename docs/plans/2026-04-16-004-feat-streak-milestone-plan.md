---
date: 2026-04-16
id: "2026-04-16-004"
title: "连续打卡与里程碑庆典 (Streaks & Milestone Celebrations)"
status: draft
origin: docs/brainstorms/2026-04-16-streak-milestone-requirements.md
---

# 连续打卡与里程碑庆典 — Implementation Plan

## Overview

The Core Earn Loop already has `ChoreInstance.streak_count` written on every
approval via `_compute_streak()`. This plan layers three things on top of that
foundation:

1. **Multiplier** — translate streak into a coin bonus at approval time, stored
   as `streak_bonus` on the instance and reflected in `CoinTransaction.amount`.
2. **Milestones** — a new `child_milestones` table records six achievement types;
   the approval and wish-realize paths check and record them after the primary
   transaction commits.
3. **Frontend celebration** — streak flames on the child task list, a bonus toast
   on the parent approval page, and a full-screen CSS confetti animation that
   fires once per milestone when the child next opens `ChildTasksPage`.

No scheduler is introduced. No existing transaction semantics change. The
milestone check is wrapped in `try/except` so a failure never rolls back an
approval.

---

## Requirements Trace

| Req | Description | Unit |
|-----|-------------|------|
| R1 | `streak_count` already exists, no new field needed | — (existing) |
| R2 | Add `streak_bonus` Integer nullable default 0 to `chore_instances` | U1 |
| R3 | New `child_milestones` table with schema as specified | U2 |
| R4 | `CoinTransaction` unchanged; `amount` carries actual (multiplied) value | U1 |
| R5 | Multiplier thresholds: 1–6 → 1.0x, 7–13 → 1.5x, ≥14 → 2.0x | U1 |
| R6 | `actual_amount = int(instance.coin_reward * multiplier)` | U1 |
| R7 | Multiplier applied in `approve_instance_async` after `_compute_streak` | U1 |
| R8 | `_auto_approve` uses same `_get_streak_multiplier` helper | U1 |
| R9 | Four once-per-child milestones: first_chore, first_wish_realized, coins_50, coins_200 | U2 |
| R10 | Three per-cycle milestones: streak_7, streak_14, streak_30 (no unique constraint) | U2 |
| R11 | Milestone check timing: approve → first_chore/streak_*/coins_*; realize → first_wish_realized/coins_* | U2 |
| R12 | Milestone check failure does not block main flow | U2 |
| R13 | `ChoreInstanceResponse` gains `streak_bonus: int` and `milestone_triggered: str | None` | U1, U2 |
| R14 | New endpoints `GET /child/milestones` and `GET /family/children/{id}/milestones` | U3 |
| R15 | `ParentWishResponse` gains `milestone_triggered: str | None` | U2 |
| R16 | `ChildTasksPage` shows streak flames and multiplier badge | U4 |
| R17 | `ChoreApprovalsPage` shows "+N 加成！🔥" toast when `streak_bonus > 0` | U4 |
| R18 | Full-screen CSS confetti + milestone card in `MilestoneCelebration.vue` | U5 |
| R19 | `ChildTasksPage` `onMounted` checks unshown milestones via localStorage | U5 |

---

## Architecture Decisions

**AD-1: `streak_bonus` stored on instance, not derived.**
`CoinTransaction.amount` already carries the multiplied value. Storing
`streak_bonus = actual - base` on the instance makes the bonus auditable without
joining to the ledger. The field is nullable with default 0 so existing rows
need no backfill.

**AD-2: `_get_streak_multiplier` as a pure module-level function.**
Both `approve_instance_async` and `_auto_approve` need it. A pure function with
no DB dependency is trivially testable and avoids duplication.

**AD-3: `generate_narrative` signature extended with `multiplier: float`.**
The existing `streak` parameter already exists. Adding `multiplier` lets the AI
prompt say "双倍奖励" when multiplier ≥ 1.5. The fallback narrative in
`_auto_approve` inline string also needs updating. Default `multiplier=1.0` for
backward compatibility.

**AD-4: Milestone check as a standalone service function, not inline.**
`check_and_record_milestones(db, child_user_id, family_id, context: dict) -> str | None`
returns the first newly-triggered milestone type (or None). Called after the
primary commit in both `approve_instance_async` and `realize_child_wish`. Wrapped
in `try/except Exception` — logs the error, returns None, never raises.

**AD-5: streak_7/14/30 per-cycle dedup via `ref_id` lookup.**
To avoid triggering `streak_7` twice within the same streak run, the check
queries `child_milestones` for a recent `streak_7` record whose `ref_id` points
to an instance with `streak_count < 7` (i.e., the streak was reset since last
trigger). If the current streak started fresh (no prior `streak_7` in this
cycle), record it. This avoids a separate "streak_start_instance_id" field.

Simpler alternative accepted: query `child_milestones` for `streak_7` records
where `triggered_at >= streak_start_date`. Streak start date = `approved_at` of
the instance where `streak_count = 1` for this template+child run. This is a
single extra query and avoids schema complexity.

**AD-6: coins_50/200 based on SUM of positive CoinTransactions.**
`SELECT SUM(amount) FROM coin_transactions WHERE child_user_id=? AND amount > 0`
— reuses the existing `get_balance()` pattern but filters to positive only.
Extracted as `get_total_earned(db, child_user_id) -> int`.

**AD-7: Frontend milestone state in localStorage, not server-side.**
`localStorage.getItem('shown_milestones')` stores a JSON array of milestone IDs
already shown. On `ChildTasksPage` mount, fetch `/child/milestones`, diff against
shown list, animate the first unshown one. No server round-trip to mark as shown.
Acceptable risk: clearing localStorage re-shows milestones (harmless for children).

---

## Implementation Units

### Unit 1: Multiplier Calculation + streak_bonus Field

**Execution note:** Test-first. Write tests for `_get_streak_multiplier` and the
modified `approve_instance_async` before implementing.

#### Files

| Action | Path |
|--------|------|
| New migration | `backend/alembic/versions/<hash>_add_streak_bonus_to_chore_instances.py` |
| Modify | `backend/app/models/chore.py` |
| Modify | `backend/app/services/chores.py` |
| Modify | `backend/app/services/chore_narrative.py` |
| Modify | `backend/app/schemas/chore.py` |
| Modify (tests) | `backend/tests/test_chores.py` |
| Modify (tests) | `backend/tests/test_chores_extended.py` |

#### What to Implement

**Migration:** Add `streak_bonus INTEGER NOT NULL DEFAULT 0` to `chore_instances`.
Down revision: `a1b2c3d4e5f6`.

**`chore.py`:** Add `streak_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)` to `ChoreInstance`.

**`chores.py`:**
- Add module-level `_get_streak_multiplier(streak: int) -> float`:
  - streak ≥ 14 → 2.0
  - streak ≥ 7 → 1.5
  - else → 1.0
- In `approve_instance_async`, after `streak = _compute_streak(...)`:
  - Compute `multiplier = _get_streak_multiplier(streak)`
  - Compute `actual_amount = int(instance.coin_reward * multiplier)`
  - Compute `bonus = actual_amount - instance.coin_reward`
  - Write `streak_bonus=bonus` alongside `streak_count=streak` in the UPDATE
  - Pass `actual_amount` to `CoinTransaction.amount` (currently uses `instance.coin_reward`)
  - Pass `multiplier` to `generate_narrative()`
- In `_auto_approve`: apply same multiplier logic; update inline fallback narrative
  to include bonus context when multiplier > 1.0.

**`chore_narrative.py`:** Add `multiplier: float = 1.0` parameter to
`generate_narrative()`. When `multiplier >= 1.5`, include bonus language in the
AI prompt (e.g., "今天是双倍奖励日！"). Update fallback narrative string to
mention bonus when applicable.

**`schemas/chore.py`:** Add `streak_bonus: int = 0` to `ChoreInstanceResponse`.

#### Test Scenarios

In `test_chores.py` / `test_chores_extended.py`:

1. `test_streak_multiplier_thresholds` — unit test `_get_streak_multiplier`:
   - streak=1 → 1.0, streak=6 → 1.0, streak=7 → 1.5, streak=13 → 1.5,
     streak=14 → 2.0, streak=30 → 2.0
2. `test_approve_streak_1_no_bonus` — approve instance with streak=1:
   - `CoinTransaction.amount == template.coin_reward`
   - `ChoreInstance.streak_bonus == 0`
   - `ChoreInstanceResponse.streak_bonus == 0`
3. `test_approve_streak_7_applies_1_5x` — approve 7th consecutive instance:
   - `CoinTransaction.amount == int(coin_reward * 1.5)`
   - `ChoreInstance.streak_bonus == actual - base`
4. `test_approve_streak_14_applies_2x` — approve 14th consecutive instance:
   - `CoinTransaction.amount == int(coin_reward * 2.0)`
5. `test_auto_approve_applies_multiplier` — auto-approve path (advance
   `submitted_at` past `auto_approve_hours`): verify `streak_bonus` written
   correctly for streak=7 case.
6. `test_streak_bonus_floor_division` — `coin_reward=3, streak=7`:
   - `actual = int(3 * 1.5) = 4`, `streak_bonus = 1`
7. `test_narrative_receives_multiplier` — mock `generate_narrative`; verify it
   is called with `multiplier=1.5` when streak=7.

---

### Unit 2: child_milestones Table + Milestone Check Service

**Execution note:** Test-first for milestone trigger logic.

#### Files

| Action | Path |
|--------|------|
| New migration | `backend/alembic/versions/<hash>_add_child_milestones_table.py` |
| New model | `backend/app/models/child_milestone.py` |
| New service | `backend/app/services/milestones.py` |
| Modify | `backend/app/services/chores.py` |
| Modify | `backend/app/services/child_wishes.py` |
| Modify | `backend/app/schemas/chore.py` |
| Modify | `backend/app/schemas/child_wish.py` |
| Modify | `backend/app/main.py` (import model for Alembic) |
| New tests | `backend/tests/test_milestones.py` |

#### What to Implement

**Migration:** Create `child_milestones` table:
```
id          VARCHAR(36) PK
family_id   VARCHAR(36) FK families.id NOT NULL
child_user_id VARCHAR(36) FK users.id NOT NULL
milestone_type VARCHAR(50) NOT NULL
triggered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
ref_id      VARCHAR(36) nullable
ref_type    VARCHAR(20) nullable  -- 'chore_instance' | 'child_wish'
```
Unique constraint on `(child_user_id, milestone_type)` for once-per-child types:
`first_chore`, `first_wish_realized`, `coins_50`, `coins_200`.
No unique constraint on `streak_7`, `streak_14`, `streak_30`.

**`child_milestone.py`:** ORM model matching above schema.

**`milestones.py`:** Implement `check_and_record_milestones()`:

```
check_and_record_milestones(
    db: Session,
    child_user_id: str,
    family_id: str,
    context: dict   # keys: 'instance' (ChoreInstance|None), 'wish' (ChildWish|None)
) -> str | None
```

Logic (in priority order, return first triggered):
1. `first_chore`: if `context['instance']` present and no existing `first_chore`
   record for this child → insert, return `'first_chore'`
2. `streak_7/14/30`: if `context['instance'].streak_count` hits threshold AND
   no `streak_7/14/30` record exists for the current streak cycle (query:
   `child_milestones WHERE child_user_id=? AND milestone_type=? AND ref_id` maps
   to an instance in the current streak run) → insert with `ref_id=instance.id`,
   `ref_type='chore_instance'`
3. `coins_50/200`: call `get_total_earned(db, child_user_id)`; if crosses
   threshold and no existing record → insert
4. `first_wish_realized`: if `context['wish']` present and no existing record → insert

Add `get_total_earned(db, child_user_id) -> int` to `coin_transactions.py`:
`SUM(amount) WHERE child_user_id=? AND amount > 0`.

Wrap entire function body in `try/except Exception as e: logger.error(...); return None`.

**`chores.py`:** After `db.commit()` following `CoinTransaction` write in
`approve_instance_async`, call:
```python
milestone = check_and_record_milestones(db, instance.child_user_id, ...)
```
Attach result to response (see schema change below).

**`child_wishes.py`:** After `db.commit()` in `realize_child_wish`, call
`check_and_record_milestones` with `context={'wish': wish}`.

**Schema changes:**
- `ChoreInstanceResponse`: add `milestone_triggered: str | None = None`
- `ParentWishResponse`: add `milestone_triggered: str | None = None`

Since these are ORM-mapped responses, `milestone_triggered` cannot come from
`model_validate` directly — set it manually after construction in the service
layer (e.g., `response = ChoreInstanceResponse.model_validate(instance); response.milestone_triggered = milestone`).
Use `model_config = ConfigDict(from_attributes=True)` already present.

#### Test Scenarios

In `test_milestones.py`:

1. `test_first_chore_triggers_on_first_approval` — approve first instance for
   child; verify `child_milestones` has `milestone_type='first_chore'`.
2. `test_first_chore_not_duplicated` — approve second instance; verify still
   only one `first_chore` record.
3. `test_streak_7_triggers_at_7` — approve 7 consecutive instances; verify
   `streak_7` record created with `ref_id=instance.id`.
4. `test_streak_7_not_triggered_at_6` — approve 6 consecutive; no `streak_7`.
5. `test_streak_7_retriggers_after_break` — approve 7, break, approve 7 again;
   verify two `streak_7` records (different `ref_id`).
6. `test_streak_7_not_duplicated_within_cycle` — approve 8 consecutive; only
   one `streak_7` record for this cycle.
7. `test_streak_14_triggers_independently` — approve 14 consecutive; both
   `streak_7` and `streak_14` records exist.
8. `test_coins_50_triggers_when_total_crosses` — grant coins to reach 49, then
   approve a chore worth 2; verify `coins_50` triggered.
9. `test_coins_50_not_triggered_if_already_recorded` — trigger once, earn more;
   no duplicate.
10. `test_coins_50_based_on_total_earned_not_balance` — realize a wish (spend
    coins), then earn enough to cross 50 total; verify `coins_50` triggers even
    though balance < 50.
11. `test_first_wish_realized_triggers` — realize a wish; verify
    `first_wish_realized` record.
12. `test_milestone_failure_does_not_block_approval` — mock
    `check_and_record_milestones` to raise; verify approval still succeeds and
    `CoinTransaction` is written.
13. `test_milestone_triggered_in_response` — approve instance that triggers
    `first_chore`; verify `ChoreInstanceResponse.milestone_triggered == 'first_chore'`.
14. `test_cross_family_milestone_isolation` — child from family A cannot see
    milestones of child from family B.

---

### Unit 3: Milestone Query API

#### Files

| Action | Path |
|--------|------|
| New router | `backend/app/routers/milestones.py` |
| Modify | `backend/app/schemas/child_wish.py` or new `backend/app/schemas/milestone.py` |
| Modify | `backend/app/main.py` (register router) |
| Modify (tests) | `backend/tests/test_milestones.py` |

#### What to Implement

**`milestones.py` router:**
```
GET /child/milestones
  → auth: get_current_child_user
  → returns list[MilestoneResponse] ordered by triggered_at DESC

GET /family/children/{child_id}/milestones
  → auth: require_adult
  → validates child belongs to same family
  → returns list[MilestoneResponse] ordered by triggered_at DESC
```

**`MilestoneResponse` schema:**
```python
class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    milestone_type: str
    triggered_at: datetime
    ref_id: str | None
    ref_type: str | None
```

#### Test Scenarios

Add to `test_milestones.py`:

15. `test_child_can_list_own_milestones` — child with 2 milestones; GET returns
    both ordered by `triggered_at DESC`.
16. `test_child_cannot_list_other_childs_milestones` — child A cannot access
    child B's milestones (404 or empty, not 403 leak).
17. `test_parent_can_list_child_milestones` — parent GET
    `/family/children/{child_id}/milestones` returns child's milestones.
18. `test_parent_cross_family_blocked` — parent cannot access child from another
    family (404).
19. `test_empty_milestones_returns_empty_list` — new child with no milestones
    returns `[]`.

---

### Unit 4: Frontend Streak Flames + Bonus Toast

#### Files

| Action | Path |
|--------|------|
| Modify | `frontend/src/pages/child/ChildTasksPage.vue` |
| Modify | `frontend/src/pages/ChoreApprovalsPage.vue` |
| Modify | `frontend/src/api/chores.ts` (add `streak_bonus`, `milestone_triggered` to types) |

#### What to Implement

**`chores.ts`:** Add `streak_bonus: number` and `milestone_triggered: string | null`
to `ChoreInstance` interface.

**`ChildTasksPage.vue`:**
- Add computed `streakFlames(streak: number): string`:
  - streak ≥ 14 → `'🔥🔥🔥'` (gold color class)
  - streak ≥ 7 → `'🔥🔥'`
  - streak ≥ 3 → `'🔥'`
  - else → `''`
- Add multiplier badge: when `streak >= 7`, show `×1.5` or `×2` chip next to
  chore name (small pill, amber background).
- Display: `<span class="streak-badge">{{ streakFlames(chore.streak_count) }} {{ chore.streak_count }}</span>`
  only when `streak_count >= 3`.

**`ChoreApprovalsPage.vue`:**
- After successful `approveChore()`, if `result.streak_bonus > 0`, show a toast:
  `+{result.streak_bonus} 加成！🔥` — use a `ref<string | null>(null)` toast
  message, auto-clear after 2000ms via `setTimeout`.
- Toast styling: fixed bottom bar, amber background, slides up/down with CSS
  transition.

No new dependencies. Pure Vue 3 Composition API + scoped CSS.

---

### Unit 5: Frontend Celebration Animation + Milestone Card

#### Files

| Action | Path |
|--------|------|
| New component | `frontend/src/components/child/MilestoneCelebration.vue` |
| Modify | `frontend/src/pages/child/ChildTasksPage.vue` |
| New API function | `frontend/src/api/milestones.ts` |

#### What to Implement

**`milestones.ts`:**
```typescript
export interface Milestone {
  id: string
  milestone_type: string
  triggered_at: string
  ref_id: string | null
  ref_type: string | null
}
export async function listMyMilestones(): Promise<Milestone[]>
```

**`MilestoneCelebration.vue`:**
- Props: `milestone: Milestone | null`, `visible: boolean`
- Emits: `close`
- When `visible=true`:
  - Full-screen overlay (z-index 200, semi-transparent dark background)
  - 20–30 confetti pieces: `<div class="confetti-piece">` absolutely positioned,
    random left %, random animation-delay 0–1s, `@keyframes confetti-fall`
    (translateY from -20px to 110vh + slight rotate), duration 2.5s
  - After 3s (or on click): emit `close`
  - Milestone card: centered white card with large emoji, name, description
    (derived from `milestone_type` via a local lookup map)
- Milestone display map:
  ```
  first_chore       → 🌟 初心者  "第一次完成家务！"
  first_wish_realized → 🎊 梦想成真 "第一个心愿实现了！"
  coins_50          → 💰 小富翁  "累计赚到50颗星！"
  coins_200         → 💎 积分达人 "累计赚到200颗星！"
  streak_7          → 🔥 一周坚持 "连续7天完成家务！"
  streak_14         → 🔥🔥 两周达人 "连续14天！太厉害了！"
  streak_30         → 👑 月度冠军 "连续30天！你是冠军！"
  ```
- Pure CSS confetti — no JS physics library.

**`ChildTasksPage.vue` — milestone check on mount:**
```typescript
const STORAGE_KEY = 'numina_shown_milestones'

onMounted(async () => {
  await load()  // existing chore load
  try {
    const milestones = await listMyMilestones()
    const shown: string[] = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    const unshown = milestones.filter(m => !shown.includes(m.id))
    if (unshown.length > 0) {
      // Show the most recent unshown milestone
      currentMilestone.value = unshown[0]
      showCelebration.value = true
    }
  } catch {
    // Milestone fetch failure must not break the task page
  }
})

function onCelebrationClose() {
  if (currentMilestone.value) {
    const shown = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    shown.push(currentMilestone.value.id)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(shown))
  }
  showCelebration.value = false
  currentMilestone.value = null
}
```

Add `<MilestoneCelebration :milestone="currentMilestone" :visible="showCelebration" @close="onCelebrationClose" />` to template.

---

## Scope Boundaries

### v1 Includes
- Multiplier calculation (1x / 1.5x / 2x) on per-template streak
- `streak_bonus` field on `ChoreInstance`
- `child_milestones` table with 7 milestone types
- Milestone check hooks in approve and realize flows
- `GET /child/milestones` and `GET /family/children/{id}/milestones`
- Frontend: streak flames, multiplier badge, bonus toast, CSS confetti, milestone card

### v1 Excludes
- Badge image assets and badge collection gallery (v2)
- Family-configurable multiplier thresholds (v2)
- Historical max streak display (v2)
- Real-time milestone push notifications (v2, requires WebSocket)
- Grace period for streak interruption (v2)
- Cross-template aggregate streak (explicitly rejected)
- Milestone sharing (v2)

---

## Dependencies and Sequencing

```
Unit 1 (multiplier + streak_bonus)
  └─ must complete before Unit 2 (milestone service reads streak_bonus context)
  └─ must complete before Unit 4 (frontend reads streak_bonus from API)

Unit 2 (milestones table + service)
  └─ must complete before Unit 3 (query API needs the table)
  └─ must complete before Unit 5 (frontend reads milestone list)

Unit 3 (milestone API)
  └─ must complete before Unit 5 (frontend calls /child/milestones)

Unit 4 (streak flames + bonus toast) — independent of Units 2/3/5
Unit 5 (celebration animation) — depends on Unit 3
```

Recommended execution order: **U1 → U2 → U3 → U4 → U5**
U4 can be parallelized with U2/U3 if desired.

---

## Migration Chain

```
a1b2c3d4e5f6  add_performance_indexes          (current head)
    ↓
<hash_1>      add_streak_bonus_to_chore_instances
    ↓
<hash_2>      add_child_milestones_table
```

---

## Deferred to Implementation

- Exact hash values for new Alembic migrations (generated at runtime)
- Streak cycle dedup query: exact SQL for "is this streak_7 already recorded in
  the current streak run" — implementer should verify the query against test data
  before finalizing
- `generate_narrative()` prompt wording for multiplier ≥ 1.5 — implementer
  decides exact Chinese phrasing
- Confetti piece count and animation timing — implementer tunes for visual quality
