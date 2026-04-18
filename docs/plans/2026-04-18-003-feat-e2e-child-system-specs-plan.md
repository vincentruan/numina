---
title: "feat: E2E Child-System Spec Coverage (Phase 2)"
type: feat
status: active
date: 2026-04-18
origin: docs/plans/2026-04-17-001-comprehensive-implementation-roadmap.md
---

# feat: E2E Child-System Spec Coverage (Phase 2)

## Problem Frame

Phase 1 enabled the existing 5 E2E spec files in CI. None of them cover the child-system flows (chore approval, wish fulfillment, milestones, child navigation guards). These flows are the core of the gamification system and have no automated regression protection.

Phase 2 adds:
1. A `test_child` seed account (child user in `test_rich`'s family) in `seed-accounts.sh`
2. A `childFamily()` fixture in `tests/lib/fixtures.ts` that handles child PIN auth
3. Four new spec files covering the child-system flows

## Requirements Trace

- R1. `seed-accounts.sh` creates a child user in `test_rich`'s family with a known PIN
- R2. `childFamily()` fixture logs in as that child and returns a ready `Page`
- R3. `chore-approval-flow.spec.ts` — parent creates template → child marks complete → parent approves → coins credited
- R4. `wish-fulfillment-flow.spec.ts` — child creates wish → parent approves with cost → child requests redemption → parent realizes → coins deducted
- R5. `child-milestone-flow.spec.ts` — first chore approval triggers `first_chore` milestone; celebration UI visible
- R6. `child-navigation.spec.ts` — child session blocked from adult routes; adult session blocked from child routes; unauthenticated redirects to `/login`
- R7. All 9 spec files (5 existing + 4 new) pass in CI

## Scope Boundaries

- Only the 4 spec files listed above; no other spec files
- `childFamily()` fixture covers a single child (no sibling scenarios)
- Milestone spec covers only `first_chore` (not streak milestones — those require multi-day data)
- No changes to backend code or frontend code
- No changes to Playwright config

## Architecture Decisions

### Child seed account in `seed-accounts.sh`

`seed-accounts.sh` already creates `test_rich` with a known token. The child creation endpoint is `POST /family/children` (requires adult auth). The script will:
1. Log in as `test_rich` to get a token
2. Check if a child named `test_child` already exists (`GET /family/children`)
3. If not, create it with PIN `["🐱","🐶","🐸","🦊"]` and avatar color `#FF6B6B`
4. Also create a chore template (`POST /family/chore-templates`) for use in specs

This keeps the seed script idempotent (already-exists check before creation).

### `childFamily()` fixture design

Mirrors `loginAs()` but for child PIN auth:
1. `POST /api/v1/auth/login` as `test_rich` → get adult `access_token`
2. `GET /api/v1/family/children` → find child with `display_name === 'test_child'`, extract `child_id`
3. `POST /api/v1/auth/child/login` with `{ child_id, pin_sequence: ["🐱","🐶","🐸","🦊"] }` → get child `access_token`
4. `GET /api/v1/auth/me` with child Bearer token → get child user object
5. Navigate to `/`, inject `localStorage['numina_user']` with child user object

Returns `{ childId, parentToken }` for specs that need both contexts (e.g., parent approves after child submits).

### Multi-context pattern for approval flows

Approval flows need two simultaneous sessions: child submits, parent approves. Use the `cross-family-isolation.spec.ts` pattern:
```
ctxChild = browser.newContext()  → childFamily(pageChild)
ctxParent = browser.newContext() → richFamily(pageParent)
```
API calls via `page.request` for state setup; UI navigation for assertion.

### Milestone spec approach

`first_chore` triggers on the first chore approval for a child. The spec:
1. Uses API calls to set up state (create instance, mark complete, approve)
2. Navigates to `/child/tasks` and checks for the `MilestoneCelebration` modal
3. Clears `seen_milestones` from localStorage before navigating to ensure the modal shows

The milestone modal is driven by `GET /child/milestones` filtered against `localStorage['seen_milestones']`. The spec must clear that key before navigating.

### Child navigation spec approach

Three guard scenarios:
1. **Child session → adult route**: Log in as child, navigate to `/assets` → expect redirect to `/child/`
2. **Adult session → child route**: Log in as adult, navigate to `/child` → expect redirect to `/`
3. **Unauthenticated → child route**: Clear localStorage, navigate to `/child` → expect redirect to `/login`

These are pure navigation tests — no API state needed beyond login.

## Research Findings

### Relevant patterns

- `tests/lib/auth.ts` — `loginAs()` pattern to replicate for child auth
- `tests/lib/fixtures.ts` — `emptyFamily()`, `richFamily()`, `singleAsset()` — return `Credentials`
- `tests/e2e/cross-family-isolation.spec.ts` — multi-context pattern with `browser.newContext()`
- `tests/e2e/auth-guards.spec.ts` — navigation guard assertion pattern
- `tests/seed-accounts.sh` — idempotent seed pattern with `register_or_login()`

### Key API endpoints

| Purpose | Method | Path |
|---------|--------|------|
| Create child | POST | `/family/children` |
| List children | GET | `/family/children` |
| Child PIN login | POST | `/auth/child/login` |
| Create chore template | POST | `/family/chore-templates` |
| Get/create chore instances | GET | `/child/chores?date=YYYY-MM-DD` |
| Mark chore complete | POST | `/child/chores/{id}/complete` |
| List pending approvals | GET | `/family/chore-approvals` |
| Approve chore | POST | `/family/chore-approvals/{id}/approve` |
| Create wish | POST | `/child/wishes` |
| List child wishes (parent) | GET | `/family/child-wishes` |
| Approve wish | POST | `/family/child-wishes/{id}/approve` |
| Request redemption | POST | `/child/wishes/{id}/request-redemption` |
| Realize wish | POST | `/family/child-wishes/{id}/realize` |
| Get balance | GET | `/child/coins/balance` |
| Get milestones | GET | `/child/milestones` |

### Key UI selectors

- Child tasks: `.chore-card`, `.btn-complete`, `.status-badge`
- Child wishes: `.wish-card`, `.btn-redeem`, `.status-badge`
- Milestone modal: `MilestoneCelebration` component — look for `.milestone-modal` or `text=恭喜` / `text=first_chore`
- Child home balance: `text=我的星星币`
- Child nav redirect: `expect(page).toHaveURL(/\/child\//)`

### Institutional learnings

No directly relevant solutions in `docs/solutions/`. The cross-family isolation spec is the closest prior art for multi-context patterns.

## Implementation Units

- [ ] **Unit 1: Extend `seed-accounts.sh` with child user and chore template**

**Goal:** Add `test_child` (child user in `test_rich`'s family) and a reusable chore template to the seed script.

**Files:**
- Modify: `tests/seed-accounts.sh`

**Approach:**
- After the `test_rich` block, add a new section that:
  1. Uses `TOKEN_RICH` (already obtained) to call `GET /family/children`
  2. Checks if a child with `display_name == "test_child"` exists
  3. If not, calls `POST /family/children` with `{ display_name: "test_child", avatar_color: "#FF6B6B", pin: ["🐱","🐶","🐸","🦊"] }`
  4. Logs the child ID for reference
- Add a chore template creation step:
  1. Calls `GET /family/chore-templates` to check if `"测试家务"` template exists
  2. If not, calls `POST /family/chore-templates` with `{ name: "测试家务", emoji: "🧹", coin_reward: 10, recurrence: "daily" }`
- Both steps are idempotent (check before create)

**Patterns to follow:**
- `register_or_login()` pattern in `seed-accounts.sh` — check existence, skip if present
- Use `jq -r` for JSON parsing, same as existing script

**Test scenarios:**
- Run script twice: second run skips child creation (idempotent)
- Child user appears in `GET /family/children` response after seeding
- Chore template appears in `GET /family/chore-templates` after seeding

**Verification:**
- `bash tests/seed-accounts.sh` exits 0 with "test_child 就绪" log line
- Running again exits 0 with "test_child 已存在，跳过" log line

---

- [ ] **Unit 2: Add `childFamily()` fixture and `loginAsChild()` helper**

**Goal:** Provide a reusable fixture that logs in as `test_child` and returns a ready `Page` plus parent token.

**Files:**
- Modify: `tests/lib/fixtures.ts`
- Modify: `tests/lib/auth.ts` — add `loginAsChild(page, parentUsername, parentPassword, childDisplayName, pin)` helper

**Approach:**

`loginAsChild()` in `tests/lib/auth.ts`:
1. `POST /api/v1/auth/login` as parent → get `parentToken`
2. `GET /api/v1/family/children` with `parentToken` → find child by `display_name`, extract `child_id`
3. `POST /api/v1/auth/child/login` with `{ child_id, pin_sequence }` → get child `access_token`
4. `GET /api/v1/auth/me` with child Bearer token → get child user object
5. Navigate to `/`, inject `localStorage['numina_user']` with child user object
6. Return `{ childId: string, parentToken: string }`

`childFamily()` in `tests/lib/fixtures.ts`:
- Calls `loginAsChild(page, 'test_rich', 'TestRich123!', 'test_child', ['🐱','🐶','🐸','🦊'])`
- Returns `{ childId, parentToken }` for specs that need both

**Patterns to follow:**
- `loginAs()` in `tests/lib/auth.ts` — exact same structure, replace password login with PIN login
- `richFamily()` in `tests/lib/fixtures.ts` — same return shape

**Test scenarios:**
- `childFamily(page)` returns non-null `childId` and `parentToken`
- After calling `childFamily(page)`, `page.goto('/child')` does not redirect to `/login`
- After calling `childFamily(page)`, `page.goto('/assets')` redirects to `/child/`

**Verification:**
- Fixture can be imported and called in a test without throwing
- Child session is active (localStorage has `numina_user` with `role: 'child'`)

---

- [ ] **Unit 3: `chore-approval-flow.spec.ts`**

**Goal:** E2E test for the full chore approval loop: child marks complete → parent approves → coins credited.

**Files:**
- Create: `tests/e2e/chore-approval-flow.spec.ts`

**Approach:**
- Use two browser contexts: child context (via `childFamily()`) and parent context (via `richFamily()`)
- State setup via API calls (not UI) to keep tests fast and deterministic:
  1. Parent context: `GET /family/chore-templates` → find `"测试家务"` template ID
  2. Child context: `GET /child/chores?date=<today>` → find instance for `"测试家务"`, get `instance_id`
  3. Child context: `POST /child/chores/{instance_id}/complete` → status becomes `pending_approval`
- Assertion via UI:
  4. Parent navigates to `/family/chore-approvals` → card for `"测试家务"` visible
  5. Parent clicks approve button → card disappears
  6. Child context: `GET /child/coins/balance` → balance increased by 10

**Test scenarios:**
- Happy path: full flow completes, balance increases by `coin_reward` (10)
- State check: after `complete`, instance status is `pending_approval` (API assertion)
- UI check: approval card shows child name `test_child` and chore name `测试家务`
- Post-approval: `GET /family/chore-approvals` returns empty list (or no card for this instance)

**Patterns to follow:**
- `cross-family-isolation.spec.ts` — multi-context setup/teardown with `try/finally { ctxA.close(); ctxB.close() }`
- `smoke.spec.ts` — console error collection pattern

**Verification:**
- Spec exits 0 with all assertions passing
- No console errors during the flow

---

- [ ] **Unit 4: `wish-fulfillment-flow.spec.ts`**

**Goal:** E2E test for the wish fulfillment pipeline: child creates wish → parent approves with cost → child requests redemption → parent realizes → coins deducted.

**Files:**
- Create: `tests/e2e/wish-fulfillment-flow.spec.ts`

**Approach:**
- Two browser contexts: child and parent
- State setup via API:
  1. Child context: `POST /child/wishes` with `{ name: "E2E测试心愿", priority: "high" }` → get `wish_id`
  2. Parent context: `POST /family/child-wishes/{wish_id}/approve` with `{ star_coin_cost: 5 }` → wish becomes `active`
  3. Child context: `POST /child/wishes/{wish_id}/request-redemption` → wish becomes `redemption_requested`
- Assertion via UI:
  4. Parent navigates to `/family/wish-review` → card for `"E2E测试心愿"` visible with "兑现申请中" status
  5. Parent clicks realize button → wish realized
  6. Child context: `GET /child/coins/balance` → balance decreased by 5

**Test scenarios:**
- Happy path: full pipeline completes, balance decreases by `star_coin_cost` (5)
- State transitions: `pending_review` → `active` → `redemption_requested` → `realized`
- UI check: wish card shows correct status badge at each stage
- Edge: if child has insufficient balance, `request-redemption` should fail (API returns 400) — verify error handling

**Patterns to follow:**
- Same multi-context pattern as Unit 3
- `cross-family-isolation.spec.ts` for context cleanup

**Verification:**
- Spec exits 0 with all assertions passing

---

- [ ] **Unit 5: `child-milestone-flow.spec.ts`**

**Goal:** Verify that completing a first chore triggers the `first_chore` milestone and the celebration UI appears.

**Files:**
- Create: `tests/e2e/child-milestone-flow.spec.ts`

**Approach:**
- This spec needs a fresh child with no prior chore history to reliably trigger `first_chore`
- Use a dedicated child context; clear `seen_milestones` from localStorage before navigating
- State setup via API:
  1. Child context: `GET /child/chores?date=<today>` → get instance for `"测试家务"`
  2. Child context: `POST /child/chores/{instance_id}/complete`
  3. Parent context: `POST /family/chore-approvals/{instance_id}/approve`
  4. Check `GET /child/milestones` → `first_chore` milestone present
- UI assertion:
  5. Child context: clear `localStorage['seen_milestones']`
  6. Navigate to `/child/tasks`
  7. Assert milestone celebration modal visible (`.milestone-modal` or `text=恭喜` or `text=first_chore`)

**Key constraint:** `first_chore` is a one-time milestone. If `test_child` has already earned it from a previous test run, this spec will not see the modal. Two mitigations:
- Check `GET /child/milestones` first; if `first_chore` already exists, skip the approval step and go straight to UI assertion (the milestone is already there, just clear `seen_milestones`)
- Document this as a known limitation in the spec comment

**Test scenarios:**
- Happy path: first chore approved → `first_chore` in milestones list → modal visible after clearing `seen_milestones`
- Already-earned path: `first_chore` already in list → skip approval, clear `seen_milestones`, assert modal still shows
- Modal dismissal: after seeing modal, `seen_milestones` in localStorage contains `first_chore`

**Patterns to follow:**
- `smoke.spec.ts` — console error collection
- `cross-family-isolation.spec.ts` — multi-context for parent approval step

**Verification:**
- Spec exits 0 with milestone modal assertion passing

---

- [ ] **Unit 6: `child-navigation.spec.ts`**

**Goal:** Verify child session is blocked from adult routes, adult session is blocked from child routes, and unauthenticated access to child routes redirects to `/login`.

**Files:**
- Create: `tests/e2e/child-navigation.spec.ts`

**Approach:**
Three independent test groups, each using a fresh page:

1. **Child → adult route blocked:**
   - `childFamily(page)` → navigate to `/assets` → expect `toHaveURL(/\/child\//)`
   - `childFamily(page)` → navigate to `/liabilities` → expect `toHaveURL(/\/child\//)`
   - `childFamily(page)` → navigate to `/settings` → expect `toHaveURL(/\/child\//)`

2. **Adult → child route blocked:**
   - `richFamily(page)` → navigate to `/child` → expect `toHaveURL(/\/$/)` (redirects to dashboard)
   - `richFamily(page)` → navigate to `/child/tasks` → expect `toHaveURL(/\/$/)` 

3. **Unauthenticated → child route → `/login`:**
   - `page.goto('/')`, clear localStorage, `page.goto('/child')` → expect `toHaveURL(/\/login/)`
   - `page.goto('/')`, clear localStorage, `page.goto('/child/tasks')` → expect `toHaveURL(/\/login/)`

**Test scenarios:**
- Child session: 3 adult routes all redirect to `/child/`
- Adult session: 2 child routes both redirect to `/`
- Unauthenticated: 2 child routes both redirect to `/login`
- Public child routes (`/child/select`, `/child/pin`, `/child/bind`) are NOT tested here (they're in `auth-guards.spec.ts` as `PUBLIC_ROUTES`)

**Patterns to follow:**
- `auth-guards.spec.ts` — navigation guard assertion pattern with `expect(page).toHaveURL()`
- `emptyFamily()` / `richFamily()` — fixture usage pattern

**Verification:**
- Spec exits 0 with all 7 navigation assertions passing

---

## Sequencing

```
Unit 1 (seed-accounts.sh)
    │
    ▼
Unit 2 (childFamily() fixture)
    │
    ├──► Unit 3 (chore-approval-flow)
    ├──► Unit 4 (wish-fulfillment-flow)
    ├──► Unit 5 (child-milestone-flow)
    └──► Unit 6 (child-navigation)
```

Units 3-6 can be implemented in parallel once Unit 2 is done. Unit 1 must precede Unit 2 (fixture depends on seed data).

## Key Risks

| Risk | Mitigation |
|------|------------|
| `first_chore` milestone already triggered for `test_child` on re-runs | Spec checks milestone list first; if already present, skips approval and goes straight to UI assertion |
| Chore instance for today may not exist if template has no recurrence | Seed template with `recurrence: "daily"` so instances are always generated for today |
| Child PIN login rate-limiting (too many failed attempts) | Use correct PIN `["🐱","🐶","🐸","🦊"]` consistently; never test wrong PINs in these specs |
| `seen_milestones` localStorage key persists across test runs | Spec explicitly clears it before navigating to `/child/tasks` |
| `test_child` may have accumulated coins from prior runs, making balance assertions fragile | Assert balance *change* (before - after) rather than absolute value |

## Test File Paths

- `tests/seed-accounts.sh` — Unit 1
- `tests/lib/auth.ts` — Unit 2 (`loginAsChild` helper)
- `tests/lib/fixtures.ts` — Unit 2 (`childFamily` fixture)
- `tests/e2e/chore-approval-flow.spec.ts` — Unit 3
- `tests/e2e/wish-fulfillment-flow.spec.ts` — Unit 4
- `tests/e2e/child-milestone-flow.spec.ts` — Unit 5
- `tests/e2e/child-navigation.spec.ts` — Unit 6

## References

- Origin roadmap: `docs/plans/2026-04-17-001-comprehensive-implementation-roadmap.md` (Phase 2)
- Prior art: `tests/e2e/cross-family-isolation.spec.ts` (multi-context pattern)
- Prior art: `tests/e2e/auth-guards.spec.ts` (navigation guard pattern)
- Prior art: `tests/lib/auth.ts` (`loginAs()` to replicate for child)
- API: `backend/app/routers/auth.py:204` (`child_login` endpoint)
- API: `backend/app/routers/children.py:25` (`create_child` endpoint)
- API: `backend/app/routers/chores.py` (chore instance endpoints)
- API: `backend/app/routers/child_wishes.py` (wish endpoints)
- API: `backend/app/routers/milestones.py` (milestone endpoints)
