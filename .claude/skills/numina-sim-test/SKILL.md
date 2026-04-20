---
name: numina-sim-test
description: >
  Full simulation test pipeline for the Numina project. Use this skill whenever
  the user wants to run UI tests, simulate user flows, audit the interface,
  capture screenshots, check visual quality, or fix UI/UX issues found during
  testing. Triggers on: "run sim test", "ui audit", "截图测试", "仿真测试",
  "ui检查", "界面审查", "run numina tests", "check the UI", "take screenshots",
  "test the app visually", or any request to verify the deployed Docker app looks correct.
---

# Numina Simulation Test Pipeline

End-to-end pipeline: Docker health → seed data → API tests → Chrome screenshots → UI/UX audit → graded fix plan → fix execution.

## Project Context

- **Base URL**: `http://localhost/numina/` (nginx proxy) or `http://localhost:8080/`
- **API**: `http://localhost/numina/api/v1`
- **Demo account**: username `demouser`, password `DemoPass123`
- **Frontend**: Vue 3 + TypeScript + Vant 4 + ECharts, mobile-first (375×812)
- **UI language**: 简体中文
- **Test scripts**: `tests/data/seed-data.sh`, `tests/e2e/acceptance.sh`, `tests/screenshot/capture.js`
- **Screenshots output**: `tests/screenshot/screenshots/`
- **Audit report output**: `docs/ui-audit-YYYY-MM-DD.md`

---

## Phase 1 — Docker Health Check

Check that the Docker services are running before doing anything else.

```bash
curl -sf http://localhost/numina/ -o /dev/null && echo "UP" || echo "DOWN"
```

If the response is DOWN, tell the user:
> Services are not running. Please start them with:
> ```bash
> docker-compose up -d
> ```
> Then re-run this skill once the services are up.

Stop here if services are down — the remaining phases all depend on a live app.

If UP, confirm to the user: "✓ Docker services are running."

---

## Phase 2 — Seed Test Data

Run the seed script to ensure `demouser` exists and test data is populated.

```bash
./tests/data/seed-data.sh
```

This creates (idempotently):
- User: `demouser` / `DemoPass123` in family `Demo Family`
- 19 physical assets (all 13 categories covered)
- 11 financial assets (all 8 categories covered)
- 3 liabilities
- 5 wishes
- Total assets ~¥50,792,000 / net worth ~¥45,312,000

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

## Phase 4 — Chrome Screenshot Capture

Capture screenshots of all pages using Puppeteer at 375×812 mobile viewport.

```bash
cd tests/screenshot && node capture.js
```

This script:
- Authenticates as `demouser` via localStorage token injection
- Captures 17 screenshots covering: login, register, join-family, dashboard, dashboard-charts, assets-list, assets-filter, asset-detail, asset-create-form, liabilities-list, liability-detail, wishes-list, stats, family, settings, category-manage, tag-manage

Screenshots are saved to `tests/screenshot/screenshots/`.

If `puppeteer` is not installed:
```bash
cd tests/screenshot && npm install puppeteer && node capture.js
```

After capture, list the screenshots found and confirm count to the user.

---

## Phase 5 — UI/UX Audit

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

## Phase 6 — Issue Triage & Graded Fix Plan

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

## Phase 7 — Fix Execution

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

- Edit only files in `frontend/src/` — do not touch backend or test scripts
- Follow project conventions: `<script setup lang="ts">`, no `as any`, Chinese UI text
- Vant 4: use `:model-value` not `:value` on `van-field`
- Minimal changes — fix what's asked, don't refactor surrounding code
- Run `npm run build` from `frontend/` after all fixes to catch type errors

---

## Quick Reference

```bash
# Full pipeline (run from project root)
curl -sf http://localhost/numina/ -o /dev/null && echo "UP"
./tests/data/seed-data.sh
./tests/e2e/acceptance.sh
cd tests/screenshot && node capture.js
# Then: read screenshots, write audit, fix issues
```
