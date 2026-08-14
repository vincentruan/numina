---
date: 2026-04-14
topic: regression-testing
focus: 完整回归测试能力 — Docker + Chrome仿真，覆盖所有前端操作链接
---

# Ideation: 完整回归测试能力

## Codebase Context

**Project shape:** Vue 3 + FastAPI monorepo. Mobile-first (Vant 4 + ECharts). Docker Compose + Nginx on port 8080. SQLite default, MySQL/PostgreSQL optional.

**Current test state:**
- Backend: 36 pytest unit tests (in-memory SQLite), all passing
- E2E: Shell scripts (`tests/e2e/scripts/acceptance.sh`, `extended.sh`, `wishes-liabilities.sh`) — curl-only, no browser assertions
- Screenshots: `tests/tools/screenshot/capture.js` (Puppeteer) — visits pages, saves PNGs, zero assertions
- No CI pipeline (no `.github/` directory)
- Seed script: `tests/seed-complete-data.sh` — 19 physical + 11 financial assets, 3 liabilities, 5 wishes

**Frontend routes:** 35 total across auth, assets, liabilities, wishes, family, settings, AI hub, stats.

**Key gaps:** No browser-level assertions anywhere. No test isolation (monolithic seed). No CI gate. Auth redirect behavior untested. Empty-state paths untested. Family data isolation untested at browser level.

---

## Ranked Ideas

### 1. Playwright E2E Suite with Docker Test Profile
**Description:** Replace the curl-based shell scripts with a Playwright test suite that drives real Chromium against the full stack (Nginx → FastAPI → SQLite). Add a `test` profile to `docker-compose.yml` that starts the stack with `TESTING=true`. Tests cover all 35 routes with actual UI interactions — form submissions, navigation, data rendering — not just API calls.

**Rationale:** The entire regression capability depends on this existing. Curl scripts cannot catch Vue component bugs, Vant interaction failures, router guard regressions, or ECharts rendering errors. The Puppeteer screenshot script already proves the navigation pattern works — Playwright is the natural upgrade with assertions.

**Downsides:** Initial setup cost (~1-2 days). Playwright tests are slower than unit tests. Requires Docker running for E2E runs.

**Confidence:** 95%
**Complexity:** Medium
**Status:** Unexplored

---

### 2. Single-Command Docker Test Harness
**Description:** A `make test-regression` (or `./tests/run-regression.sh`) that orchestrates the full sequence: `docker-compose --profile test up -d`, wait for health checks, seed data, run Playwright suite, capture results, `docker-compose down`. Exits with pass/fail code. No manual steps.

**Rationale:** A suite no one runs is not a regression suite. The current multi-step manual process (start Docker, wait, seed, run scripts, clean up) is why tests get skipped. One command removes all friction and makes CI trivial to add.

**Downsides:** Requires Docker on the machine. Full suite run time will be minutes, not seconds.

**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

---

### 3. GitHub Actions CI Matrix
**Description:** `.github/workflows/ci.yml` with parallel jobs: (1) backend pytest, (2) frontend `vue-tsc --noEmit` + `npm run build`, (3) Playwright E2E against Docker stack. Cache `uv` and `npm` dependencies. Fail the PR if any layer fails.

**Rationale:** Without CI, the entire suite is opt-in and will be bypassed under deadline pressure. CI converts the regression suite from a local suggestion into an enforced gate. No `.github/` directory currently exists — this is a complete gap.

**Downsides:** GitHub Actions minutes cost (minimal for this scale). Docker-in-Docker for E2E job requires `services` or `docker-compose` setup in the workflow.

**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

---

### 4. Seed-State Fixture Library (Named Scenarios)
**Description:** Break `tests/seed-complete-data.sh` into composable named fixtures: `fixture:empty-family` (user + family, no assets), `fixture:rich-family` (current full seed), `fixture:paid-off-liability` (liability at remaining=0), `fixture:single-asset` (minimal data for detail page tests). Each fixture is an idempotent script or Playwright `beforeEach` hook. Tests declare which fixture they need.

**Rationale:** The monolithic seed script makes it impossible to test empty-state UI, boundary conditions, or isolated scenarios. Named fixtures are the prerequisite for meaningful test isolation — without them, every test depends on the same global state and failures cascade.

**Downsides:** Requires porting seed logic from shell to Python/JS fixtures. Initial investment before tests can use them.

**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

---

### 5. Route Guard Coverage Tests
**Description:** Data-driven Playwright tests that verify: (a) every protected route (`requireAuth`) redirects unauthenticated users to `/login`, (b) every guest route (`requireGuest`: `/login`, `/register`, `/join-family`) redirects authenticated users to `/`. Two assertions per route, driven by the route manifest.

**Rationale:** Auth redirect behavior is the highest-value, lowest-effort addition. It's completely untested today. A refactor of the auth store or a route rename can silently break redirects — this catches it in seconds.

**Downsides:** Tests are shallow (redirect only, not full page functionality). Must be updated when new routes are added.

**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

---

### 6. Empty-State Gauntlet
**Description:** Using the `fixture:empty-family` scenario, visit every list and dashboard page with zero data: Dashboard (ECharts with empty arrays), `/assets` (empty list), `/liabilities`, `/wishes`, `/stats`, `/family`. Assert no JS console errors, no blank screens, and that empty-state UI components render correctly.

**Rationale:** Every new user's first session is the empty-state experience. Dashboard aggregation endpoints return `{ items: [], total: 0 }` and `{ points: [] }` for empty families — whether ECharts handles these gracefully is completely unknown. This is the most common source of silent first-run breakage.

**Downsides:** Depends on fixture library (#4) being built first. ECharts empty-state behavior may require chart-specific assertions.

**Confidence:** 90%
**Complexity:** Low (once fixtures exist)
**Status:** Unexplored

---

### 7. API Contract Snapshot (OpenAPI JSON diff)
**Description:** At CI time, fetch `GET /openapi.json` from the running backend and diff it against a committed `tests/fixtures/openapi.snapshot.json`. Any field added, removed, renamed, or type-changed fails the check with a clear diff. Updating the snapshot is a deliberate, reviewable `git add`.

**Rationale:** FastAPI auto-generates `/openapi.json` — this is nearly free to implement. The `CLAUDE.md` "Common Pitfalls" section documents at least 3 historical schema mismatches that were caught manually. A snapshot diff catches them automatically at the moment of change, before the frontend notices.

**Downsides:** Snapshot must be updated intentionally on every intentional API change (minor friction). Does not validate frontend TypeScript types directly.

**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

---

### 8. Cross-Family Data Isolation (Browser-Level)
**Description:** A Playwright test that opens two browser contexts simultaneously — one authenticated as Family A, one as Family B. Family A creates an asset. Family B attempts to navigate directly to `/assets/{id}` with Family A's asset ID. Assert: 404 response, error page rendered, no data leakage.

**Rationale:** Family scoping is the core privacy invariant of this app. Backend unit tests cover it at the API layer (`second_user_headers` fixture in `conftest.py`), but no test exercises the full browser flow where a user manually types a URL. A frontend bug (wrong family_id in a Pinia store, cached response) would not be caught by backend tests.

**Downsides:** Requires two simultaneous authenticated sessions — slightly more complex Playwright setup. Only covers one isolation scenario (direct URL navigation).

**Confidence:** 85%
**Complexity:** Low-Medium
**Status:** Unexplored

---

### 9. Auth Helper Library
**Description:** A shared `tests/lib/auth.ts` (Playwright) that exports `loginAs(page, username, password)` — handles POST to `/auth/login`, stores token, sets up the browser session. All E2E tests call this in one line. Replaces the copy-pasted login curl sequences in `acceptance.sh`, `extended.sh`, `wishes-liabilities.sh`.

**Rationale:** Every approved test above requires an authenticated session. Without a shared helper, auth boilerplate will be copy-pasted into every test file. When the auth API changes (it already has — refresh token endpoint, bcrypt rounds), one fix propagates everywhere instead of requiring edits across every test file.

**Downsides:** Not glamorous. Must be kept in sync with auth API changes.

**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

---

### Cross-Cutting Synthesis: Layered Test Foundation

Ideas #1 (Playwright suite) + #4 (fixture library) + #9 (auth helper) + #5 (route guard tests) form a natural **layered test skeleton**:

- Playwright suite = the shell (test runner, browser, Docker integration)
- Fixture library = data isolation (each test gets the state it needs)
- Auth helper = session management (every test starts authenticated in one line)
- Route guard tests = first concrete coverage layer (35 routes × 2 assertions = immediate value)

Building these four together as a single initiative produces a foundation where every subsequent test (empty-state, isolation, contract) is trivial to add. Building them separately risks the suite existing but being unusable due to missing primitives.

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 4 | Stateful Flow Recorder (Playwright codegen) | Codegen output is brittle and selector-fragile; write flows by hand |
| 5 | Page Object Model tied to Vue Router | Premature abstraction; build tests first, extract POMs when duplication demands it |
| 7 | Pydantic-to-TypeScript Contract Check | Duplicates API Contract Snapshot (#7) at higher implementation cost |
| 8 | Visual Regression with Pixelmatch | High false-positive rate from font rendering/antialiasing; maintenance cost exceeds value |
| 10 | Test Reset API Endpoint | Exposes destructive endpoint with production risk; fixture library achieves same isolation |
| 12 | Token Refresh Race Condition Test | Deep network interception for one rarely-regressing scenario; not regression-critical |
| 13 | Liability Full-Payoff Boundary Test | Backend unit test, not a regression suite gap; add to `test_liabilities.py` directly |
| 16 | Mobile Viewport Regression (375px) | A config flag in Playwright, not a separate initiative; fold into base config |
| 17 | Asset Type Discrimination Mid-Form | Niche single-form interaction; not regression-critical at suite level |
| 18 | Family Invite Code Concurrent Join | Race condition testing is flaky in CI; backend unit tests are the right place |
| 19 | SQLite Snapshot for Fast Test Isolation | Over-engineered; re-seeding via fixture library is fast enough at this scale |
| 21 | Backend Mutation Testing (mutmut) | Premature; close coverage gaps by writing targeted tests, not running a mutation framework |
| 22 | Coverage Matrix (Route × Operation) | Documentation overhead masquerading as testing; the Playwright suite is the living matrix |
| 23 | Named Journey Tests as Living Documentation | Naming convention, not a capability; fold into Playwright suite directly |
| 25 | Cross-Family Isolation (Two Browser Contexts) | Exact duplicate of #8 |

---

## Session Log
- 2026-04-14: Initial ideation — 25 candidates generated across 4 frames, 9 survivors + 1 cross-cutting synthesis
