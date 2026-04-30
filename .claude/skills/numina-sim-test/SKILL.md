---
name: numina-sim-test
description: >
  Full simulation test pipeline for the Numina project. Use this skill whenever
  the user wants to run UI tests, simulate user flows, audit the interface,
  capture screenshots, check visual quality, or fix UI/UX issues found during
  testing. Covers both adult frontend and child frontend (儿童视角).
  Triggers on: "run sim test", "ui audit", "截图测试", "仿真测试",
  "ui检查", "界面审查", "run numina tests", "check the UI", "take screenshots",
  "test the app visually", "儿童测试", "child frontend test",
  or any request to verify the deployed Docker app looks correct.
---

# Numina Simulation Test Pipeline

End-to-end pipeline: Docker health → seed data → API tests → Chrome screenshots → UI/UX audit → graded fix plan → fix execution.

Covers two SPAs:
- **Adult frontend** (`http://localhost/`) — family asset management
- **Child frontend** (`http://localhost/child/`) — child role experience

## Project Context

- **Base URL**: `http://localhost/` (nginx proxy)
- **API**: `http://localhost/api/v1`
- **Adult demo account**: `demouser` / `DemoPass123`
- **Child accounts** (under demouser family):
  - 小宝: username `xiaobao`, PIN `🐱🌟🎈🐶`
  - 大宝: username `dabao`, PIN `🌈🍎🐸🦁`
- **Regression test accounts**:
  - `test_rich` / `TestRich123!` — full data (assets + liabilities + wishes + children)
  - `test_child`: username `testchild`, PIN `🐱🐶🐸🦊` (under test_rich family)
- **Frontend**: Vue 3 + TypeScript + Vant 4 + ECharts, mobile-first (375×812)
- **UI language**: 简体中文
- **Test scripts**: `tests/data/seed-data.sh`, `tests/e2e/acceptance.sh`
- **Audit report output**: `dogfood-output/report.md`
- **Issues report output**: `dogfood-output/issues-report.md`

### Monorepo Structure (feat/child-frontend-module-split branch onwards)

```
frontend/
  apps/
    main/        ← adult frontend source (was: frontend/)
    child/       ← child frontend source (was: frontend-child/)
  packages/
    auth/        ← shared auth package (was: packages/auth/)
```

> **Important**: Always edit files under `frontend/apps/child/` for child frontend changes.
> The old `frontend-child/` path no longer exists.

---

## Phase 1 — Docker Health Check

Check that all Docker services are running before doing anything else.

```bash
# Adult frontend
curl -sf http://localhost/ -o /dev/null && echo "adult: UP" || echo "adult: DOWN"
# Child frontend
curl -sf http://localhost/child/ -o /dev/null && echo "child: UP" || echo "child: DOWN"
# Backend API
curl -sf http://localhost/api/health -o /dev/null && echo "api: UP" || echo "api: DOWN"
# Container status
docker ps --format "{{.Names}}\t{{.Status}}" | grep numina
```

If any service is DOWN, tell the user:
> Services are not running. Please start them with:
> ```bash
> docker-compose up -d
> ```
> Then re-run this skill once the services are up.

Stop here if services are down — the remaining phases all depend on a live app.

**Child frontend specific checks:**
- Verify `numina-frontend-child` container is running (not just `numina-frontend`)
- Verify nginx routes `/child/` correctly — assets should load from `/child/assets/`, not `/assets/`
- If child assets return 404, check `nginx.conf`: `proxy_pass http://frontend-child/` (no `/child/` suffix)

If UP, confirm: "✓ Adult frontend UP, ✓ Child frontend UP, ✓ API UP."

---

## Phase 2 — Seed Test Data

Run the seed script to ensure all test accounts exist and data is populated.

```bash
./tests/data/seed-data.sh
```

This creates (idempotently):

**Fixed regression accounts:**
- `test_empty` / `TestEmpty123!` — empty family
- `test_asset` / `TestAsset123!` — 5 assets (in_use/idle/retired/USD/sold)
- `test_rich` / `TestRich123!` — 31 assets + 28 liabilities + 29 wishes + children
  - Child: `testchild` (display_name: `test_child`), PIN `🐱🐶🐸🦊`
- `test_rich_member` / `TestMember123!` — member role in test_rich family

**Demo account:**
- `demouser` / `DemoPass123` — full simulation data
  - 19 physical assets + 11 financial assets + 7 liabilities + 9 wishes
  - Children: 小宝 (`xiaobao`, PIN `🐱🌟🎈🐶`) + 大宝 (`dabao`, PIN `🌈🍎🐸🦁`)
  - Blind box gifts, chore templates, child wishes (5 status variants)

If the script fails, check that `jq` is installed (`brew install jq`) and that the API is reachable.

---

## Phase 3 — API Acceptance Tests

Run the API test suite and capture results.

```bash
./tests/e2e/acceptance.sh
```

Parse the output for pass/fail counts. If any tests fail:
- List the failing test names
- Note them in the audit report under a "API Issues" section
- Continue to Phase 4 regardless (UI audit is independent)

Report summary: "✓ X/Y API tests passed."

---

## Phase 4 — Adult Frontend Screenshot Capture

Use Chrome DevTools MCP to capture screenshots of the adult frontend at 375×812 mobile viewport.

Navigate to `http://localhost/` and capture:
- Dashboard (总览) — verify asset totals, net worth, trend chart
- Family page (/family) — verify member list, children cards with balances
- Wishes page — verify wish list with priorities
- Liabilities page — verify liability list
- Settings page

For each page:
1. `navigate_page` to the route
2. `wait_for` key content to appear
3. `take_screenshot` and save to `dogfood-output/`
4. `list_console_messages` — confirm zero errors

**Key assertions for adult frontend:**
- Auth refresh (401 → 200) is expected on first load — not a bug
- Family page should show 小宝 and 大宝 with coin balances
- Tab bar shows: 总览 / 心愿 / AI / 负债 / 宝贝 / 设置

---

## Phase 5 — Child Frontend Health Check

Before testing child flows, verify the child SPA loads correctly.

```bash
# Verify child assets load (not 404)
curl -sf http://localhost/child/ -o /dev/null && echo "child SPA: UP"
# Check nginx strips /child/ prefix correctly
curl -I http://localhost/child/ | grep -i "content-type"
```

**Known issue to check (nginx proxy_pass):**
The `nginx.conf` must have:
```nginx
location /child/ {
    proxy_pass http://frontend-child/;   # ← correct: strips /child/ prefix
}
```
NOT:
```nginx
    proxy_pass http://frontend-child/child/;  # ← wrong: doubles the prefix
```

If child assets return 404, this is the root cause.

---

## Phase 6 — Child Frontend: ChildSelectPage

Navigate to `http://localhost/child/` as an authenticated adult (demouser session must be active).

```
navigate_page → http://localhost/child/
wait_for → ["选择孩子", "小宝", "大宝"]
take_snapshot
```

**Assertions:**
- [ ] Page title: "选择孩子"
- [ ] 2 child cards visible: 小宝 (red avatar) + 大宝 (teal avatar)
- [ ] Avatar shows first character of display_name (小 / 大), NOT `?`
- [ ] Username shows `@xiaobao` / `@dabao`, NOT `@` alone
- [ ] No console errors

**Known bug to check — API response unwrapping:**
`GET /api/v1/family/children` returns `{"code":"OK","data":[...]}`.
`listChildren()` in `frontend/apps/child/src/api/children.ts` must return `res.data.data` (the array), not `res.data` (the envelope object).

If avatars show `?` and names are empty, this is the root cause — `v-for` is iterating over object keys (`code`, `message`, `data`) instead of the children array.

**Fix location:** `frontend/apps/child/src/api/children.ts`
```ts
// Wrong
return res.data
// Correct
return res.data?.data ?? res.data
```

---

## Phase 7 — Child Frontend: Authentication Flow (PIN)

Click a child card to navigate to ChildAuthPage.

```
click → child card (小宝)
wait_for → ["使用图形密码", "🐱", "🐶"]
take_snapshot
```

**Assertions:**
- [ ] Child avatar and name displayed at top
- [ ] 4 PIN slot indicators visible (empty circles)
- [ ] 12 emoji buttons in 4×3 grid
- [ ] 删除 and 清除 buttons visible
- [ ] No console errors

**Test PIN input — 小宝 (PIN: 🐱🌟🎈🐶):**
```
click → 🐱 button
click → 🌟 button
click → 🎈 button
click → 🐶 button
```

Expected: auto-submits on 4th emoji, navigates to `/child/` (home) on success.

**Test wrong PIN:**
```
click → 🐱 🐱 🐱 🐱 (wrong sequence)
```
Expected: shake animation, PIN cleared, error message shown.

**Test null display_name guard:**
If child has `null` display_name, avatar should show `?` (not crash).
Check: `(displayName ?? '?').charAt(0)` in `ChildAuthPage.vue`.

---

## Phase 8 — Child Frontend: Home Page (ChildHomePage)

After successful PIN login as 小宝:

```
wait_for → ["/child/home", "星星币", "小宝"]
take_snapshot
```

**Assertions:**
- [ ] Child name and avatar displayed
- [ ] Coin balance shown (小宝 should have 50+ coins from seed data)
- [ ] Bottom tab bar: 首页 / 任务 / 心愿 / 宝箱 (or similar)
- [ ] No console errors
- [ ] No network 4xx errors (except expected 401 on auth refresh)

---

## Phase 9 — Child Frontend: Tasks/Chores Page (ChildTasksPage)

```
navigate_page → /child/tasks  (or click tasks tab)
wait_for → ["家务", "今日"]
take_snapshot
```

**Assertions:**
- [ ] Today's chore list visible
- [ ] Chore cards show emoji, name, coin reward
- [ ] Completed chores show different state from available
- [ ] "待审批" badge visible if chore completed but not yet approved

**Seed data context:**
- test_rich family has chore template "测试家务" (🧹, 10 coins, daily)
- demouser family has: 整理房间 (🧹, 5 coins), 洗碗 (🍽️, 8 coins), 打扫卫生间 (🚿, 15 coins weekly)

---

## Phase 10 — Child Frontend: Wishes Page (ChildWishesPage)

```
navigate_page → /child/wishes
wait_for → ["心愿"]
take_snapshot
```

**Assertions:**
- [ ] Wish list renders with emoji, name, status badge
- [ ] Status variants visible: pending_review / active / rejected / redemption_requested / realized
- [ ] Coin cost shown for approved wishes
- [ ] "申请兑换" button visible for active wishes with sufficient balance

**Seed data context (demouser children):**
- 小宝: 积木玩具 (pending_review), 昂贵玩具 (rejected), 小背包 (realized)
- 大宝: 新耳机 (active, cost=80), 漫画书 (redemption_requested, cost=30)

---

## Phase 11 — Child Frontend: Blind Box Page (ChildBlindBoxPage)

```
navigate_page → /child/blind-box
wait_for → ["盲盒", "抽奖"]
take_snapshot
```

**Assertions:**
- [ ] Blind box UI renders
- [ ] Available bonus draws shown (小宝 has 2 bonus draws from seed data)
- [ ] Gift pool preview visible
- [ ] Draw history visible if any past draws exist

---

## Phase 12 — Child Frontend: Known Issues Checklist

After completing all child frontend phases, verify these known issues are resolved or still present:

| Check | Expected | Status |
|-------|----------|--------|
| nginx proxy_pass strips `/child/` prefix | Assets load at `/child/assets/`, not 404 | |
| `listChildren()` unwraps `res.data.data` | Child names render correctly, not `?` | |
| `display_name ?? '?'` guard in ChildSelectPage | No crash on null display_name | |
| `displayName ?? '?'` guard in ChildAuthPage | No crash on null displayName query param | |
| `getChildFamilyId()` returns null for adult sessions | Falls back to `listChildren()` correctly | |
| Child SPA has no cross-imports from adult frontend | ESLint boundary check passes | |

---

## Phase 13 — UI/UX Audit

Read each screenshot from `tests/screenshot/screenshots/` using the Read tool (it supports image files). Audit every screenshot against these dimensions:

### Audit Dimensions

**Visual Hierarchy**
- Is the most important information visually prominent?
- Are headings, subheadings, and body text clearly differentiated?
- Does the eye flow naturally through the page?

**Color Consistency**
- Are brand colors (blue gradient primary, white cards) used consistently?
- Are status colors (green=positive, red=negative/debt) semantically correct?
- Is contrast sufficient for readability (WCAG AA minimum)?

**Typography**
- Is font size appropriate for mobile (minimum 14px body, 16px+ for inputs)?
- Are Chinese characters rendering cleanly?
- Is line height comfortable for reading?

**Icon Usage**
- Are emoji icons (🏠🚗📱) used consistently vs SVG icons?
- Do icons have sufficient tap target size (44×44px minimum)?
- Are icons semantically meaningful?

**Spacing & Layout**
- Is padding/margin consistent across cards and list items?
- Are touch targets large enough (44px minimum)?
- Is content clipped or overflowing on 375px width?

**Mobile Layout**
- Does the bottom tab bar have the right number of items (≤5 recommended)?
- Is the safe area (notch/home indicator) respected?
- Are forms usable with a mobile keyboard visible?

**Empty States**
- Do empty states have helpful illustrations or guidance?
- Is the call-to-action clear?

**Loading States**
- Are skeleton loaders or spinners shown during data fetch?
- Is there feedback for async operations?

**Vant 4 Component Usage**
- Are Vant components used correctly (van-cell, van-card, van-button, etc.)?
- Are form fields using `:model-value` (not `:value`) binding?
- Are action sheets and dialogs used appropriately?

For each issue found, record:
- **Page**: which screenshot / route
- **Component**: specific element or component
- **Issue**: what's wrong
- **Severity**: P0 / P1 / P2 / P3 (see below)
- **Fix**: concrete suggestion

---

## Phase 14 — Issue Triage & Graded Fix Plan

### Severity Levels

| Level | Meaning | Examples |
|-------|---------|---------|
| **P0** | Critical / broken | Page doesn't render, data missing, auth broken, layout completely broken |
| **P1** | Major UX problem | Key info hard to find, poor contrast, broken form, confusing navigation |
| **P2** | Minor polish | Inconsistent spacing, slightly off colors, minor alignment issues |
| **P3** | Nice-to-have | Illustrations for empty states, micro-animations, icon upgrades |

### Write the Audit Report

Save to `docs/ui-audit-YYYY-MM-DD.md` (use today's date). Use this structure:

```markdown
# Numina UI Audit — YYYY-MM-DD

## Summary
- Screenshots captured: N
- API tests: X/Y passed
- Issues found: N total (P0: X, P1: X, P2: X, P3: X)

## P0 — Critical Issues
### [Issue Title]
- **Page**: route/screenshot name
- **Component**: specific element
- **Issue**: description
- **Fix**: concrete suggestion
- **Effort**: S / M / L

## P1 — Major UX Issues
[same structure]

## P2 — Minor Polish
[same structure]

## P3 — Nice-to-Have
[same structure]

## API Issues (if any)
[list failing tests]
```

After writing the file, tell the user the path and summarize the issue counts by severity.

---

## Phase 15 — Fix Execution

After presenting the audit report, ask the user:

> "Found X P0 and Y P1 issues. Would you like me to fix them now, starting with the highest severity? I'll re-screenshot after each fix to verify."

If the user says yes, work through P0 then P1 issues in order:

1. **Read the affected component** — use Read to understand the current code before changing anything
2. **Implement the fix** — edit only the specific file/component, minimal change
3. **Re-screenshot** — run `cd tests/screenshot && node capture.js` (or a targeted subset if possible) to verify the fix visually
4. **Read the new screenshot** — confirm the issue is resolved
5. **Move to next issue**

After all P0+P1 fixes:
- Run `npm run build` from `frontend/` to verify no TypeScript errors
- Update the audit report with fix status (mark each fixed issue as ✅)
- Summarize what was fixed and what remains (P2/P3 for future sprints)

### Fix Guidelines

- **Adult frontend**: edit files in `frontend/apps/main/src/`
- **Child frontend**: edit files in `frontend/apps/child/src/` — NOT `frontend-child/` (old path, removed)
- **Shared auth**: edit files in `frontend/packages/auth/src/`
- Follow project conventions: `<script setup lang="ts">`, no `as any`, Chinese UI text
- Vant 4: use `:model-value` not `:value` on `van-field`
- Minimal changes — fix what's asked, don't refactor surrounding code
- After fixing child frontend, rebuild container: `docker-compose build frontend-child && docker-compose up -d frontend-child`

---

## Quick Reference

```bash
# Health check (adult + child + API)
curl -sf http://localhost/ -o /dev/null && echo "adult UP"
curl -sf http://localhost/child/ -o /dev/null && echo "child UP"
curl -sf http://localhost/api/v1/health -o /dev/null && echo "api UP"

# Seed all test data
./tests/data/seed-data.sh

# API acceptance tests
./tests/e2e/acceptance.sh

# Rebuild child frontend after code changes
docker-compose build frontend-child && docker-compose up -d frontend-child

# Child test accounts (from seed-data.sh)
# demouser family:  小宝 (xiaobao / 🐱🌟🎈🐶)  大宝 (dabao / 🌈🍎🐸🦁)
# test_rich family: test_child (testchild / 🐱🐶🐸🦊)
```

### Child Frontend Test Flow (Chrome DevTools MCP)

```
1. Ensure demouser is logged in at http://localhost/
2. navigate_page → http://localhost/child/
3. wait_for → ["选择孩子", "小宝", "大宝"]   ← Phase 6
4. click → 小宝 card
5. wait_for → ["使用图形密码"]               ← Phase 7
6. click → 🐱, 🌟, 🎈, 🐶 (PIN input)
7. wait_for → ["/child/home", "星星币"]      ← Phase 8
8. navigate tabs → tasks, wishes, blind-box  ← Phases 9-11
9. list_console_messages → assert zero errors
```
