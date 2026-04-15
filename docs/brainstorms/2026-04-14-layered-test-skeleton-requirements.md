---
date: 2026-04-14
topic: layered-test-skeleton
---

# Layered Test Skeleton

## Problem Frame

Numina has 36 backend unit tests and curl-based shell E2E scripts, but zero browser-level assertions. The Puppeteer screenshot script visits pages and saves PNGs with no assertions. There is no CI gate. Any Vue component bug, Vant interaction failure, router guard regression, or ECharts rendering error is invisible until a human clicks through the app manually.

The goal is a foundational test skeleton that makes every future regression test trivial to add: a Playwright suite wired to Docker, composable data fixtures, a shared auth helper, and route guard coverage as the first concrete test layer.

```
┌─────────────────────────────────────────────────────┐
│              Single-command harness                  │
│         ./tests/run-regression.sh                    │
├─────────────────────────────────────────────────────┤
│         Playwright E2E suite (Chromium)              │
│   tests/e2e/*.spec.ts  ←  tests/lib/auth.ts         │
├──────────────────┬──────────────────────────────────┤
│  Fixture library │  Route guard tests               │
│  empty-family    │  31 routes × auth redirect       │
│  rich-family     │  assertions                      │
│  single-asset    │                                  │
├──────────────────┴──────────────────────────────────┤
│   Docker Compose (test profile) — port 80           │
│   backend + agent + frontend + nginx                │
└─────────────────────────────────────────────────────┘
```

---

## Requirements

**Playwright Suite & Docker Integration**

- R1. A `playwright` service is added to `docker-compose.yml` under a `test` profile. It runs `npx playwright test` against the full stack (nginx on port 80) and exits with the test result code.
- R2. The Playwright suite targets `http://localhost` (nginx, port 80) — the same URL the existing shell scripts and `capture.js` use. No Vite dev server involvement.
- R3. Playwright is configured with Chromium only (no Firefox/WebKit) at 390×844 viewport (iPhone 14), matching the mobile-first design intent. The existing `capture.js` uses 375×812 — align to 390×844 as the canonical test viewport. `workers: 1` is set in `playwright.config.ts` to avoid SQLite write contention under parallel fixture calls; this can be increased when the project moves to PostgreSQL for tests.
- R4. The `tests/` directory gets a `package.json` and `playwright.config.ts`. The existing root-level `package.json` (which contains only puppeteer as a devDependency) is deleted and puppeteer is moved into `tests/package.json` alongside Playwright. No root-level `package.json` remains after this change.

**Single-Command Harness**

- R5. `./tests/run-regression.sh` orchestrates the full sequence: `docker compose --profile test up -d` → wait for all health checks to pass → seed fixture data → run Playwright → print pass/fail summary → `docker compose --profile test down -v`. Exits non-zero on any failure. The script sets `trap 'docker compose --profile test down -v' EXIT` at the top so teardown runs even on crash or signal (SIGKILL excepted).
- R6. The harness accepts an optional `--keep-up` flag to skip teardown, useful for local debugging after a failure.
- R7. The harness prints elapsed time and a final `PASSED` / `FAILED` line suitable for CI log scanning.

**Fixture Library**

- R8. Three named fixtures are implemented as TypeScript functions in `tests/lib/fixtures.ts`, callable from Playwright `beforeEach` hooks:
  - `fixture:empty-family` — registers a fresh user + family, no assets/liabilities/wishes
  - `fixture:rich-family` — registers a user + family, then seeds the full dataset (equivalent to `tests/seed-complete-data.sh`: 19 physical + 11 financial assets, 3 liabilities, 5 wishes)
  - `fixture:single-asset` — registers a user + family, creates one physical asset (房产 category, ¥1,000,000)
- R8a. A basic smoke test `tests/e2e/smoke.spec.ts` uses `fixture:single-asset` to verify the asset detail page renders without JS errors. This gives `fixture:single-asset` a concrete consumer in this initiative.
- R9. Each fixture function returns credentials (`{ username, password, familyId }`) so the calling test can log in immediately after setup.
- R10. Fixtures call the backend API directly (not via browser UI) to keep setup fast and deterministic. Each fixture creates a unique username using a random UUID suffix (e.g. `user_${crypto.randomUUID()}`) so parallel test runs and parallel Playwright workers never collide.
- R11. No test reset API endpoint is added to the backend. Isolation is achieved by each fixture creating a fresh user+family, not by wiping the database.

**Auth Helper**

- R12. `tests/lib/auth.ts` exports `loginAs(page, username, password)` — uses `page.request.post('/api/v1/auth/login')` so the browser context receives the httpOnly auth cookie from the server response. After the POST, writes the user object to `localStorage['numina_user']` (the key `getUser()` reads in `@/utils/storage`) so the Vue router guard's `isLoggedIn` check passes. The httpOnly cookie is then automatically sent on all subsequent requests in that browser context.
- R13. The helper handles the case where login fails (wrong credentials) by throwing a descriptive error, not silently returning null.

**Route Guard Coverage Tests**

- R15. A spec file `tests/e2e/auth-guards.spec.ts` covers all 31 navigable routes in two data-driven loops:
  - Protected routes (28 routes — children of the MainLayout): unauthenticated navigation redirects to `/login`
  - Guest-only routes (`/login`, `/register`, `/join-family`): authenticated navigation redirects to `/`
- R16. The route list in the spec is derived from a shared constant in `tests/lib/routes.ts` that mirrors `frontend/src/router/index.ts`. A sync-check test in `auth-guards.spec.ts` imports the Vue router config and asserts that every route name in the router is present in `routes.ts` — the test fails if they diverge. This makes coverage automatic: a new route added to the router without a matching entry in `routes.ts` causes an immediate test failure.
- R17. Route guard tests use `fixture:empty-family` for the authenticated cases (minimal setup, no asset data needed).

---

## Success Criteria

- `./tests/run-regression.sh` completes end-to-end without manual steps on a machine with Docker installed
- All 31 navigable routes are covered by auth redirect assertions in `auth-guards.spec.ts`
- A new test file can be added that calls `loginAs()` + a fixture in `beforeEach` with no boilerplate beyond those two lines
- The suite exits non-zero when a deliberate regression is introduced (e.g., removing the `requireAuth` guard from a protected route)

---

## Scope Boundaries

- No CI pipeline (GitHub Actions) in this initiative — that is a separate follow-on
- No visual regression / pixel diffing
- No API contract snapshot test
- No cross-family isolation browser test
- No empty-state gauntlet tests — those are the *next* layer built on top of this skeleton
- No Firefox or WebKit test runs — Chromium only
- No Page Object Model — write tests directly, extract POMs only when duplication demands it
- The existing shell-based E2E scripts (`acceptance.sh`, `extended.sh`, `wishes-liabilities.sh`) are not deleted — they remain as API-layer smoke tests

---

## Key Decisions

- **`loginAs` is the only auth path:** All tests establish sessions via `loginAs()`. No test duplicates the login sequence inline. This is a convention enforced by code review, not a CI check.
- **Playwright over Cypress:** Playwright's multi-context support (needed for future cross-family isolation tests), built-in Chromium, and TypeScript-first API make it the better long-term foundation. Cypress would require a separate runner process and has weaker multi-context support.
- **Fixtures via API, not UI:** Seeding through the browser UI is slow and fragile. Direct API calls in `beforeEach` are fast, deterministic, and don't depend on form UI being correct.
- **Fresh user per fixture, not DB reset:** Avoids adding a destructive test endpoint to the backend. Each fixture creates an isolated namespace (unique family) so tests never share state.
- **`tests/package.json`, not root:** Keeps Playwright dependencies scoped to the test layer. The frontend already has its own `package.json`; a root one would create confusion.
- **`workers: 1` for SQLite safety:** Playwright is configured with a single worker to avoid concurrent SQLite writes causing `SQLITE_BUSY` errors during fixture setup. Can be increased when tests move to PostgreSQL.

---

## Dependencies / Assumptions

- Docker and Docker Compose are available on the developer's machine
- The backend `/api/v1/auth/register` and `/api/v1/auth/login` endpoints are stable (they are — 10 passing unit tests)
- The nginx service on port 80 is the correct test target (confirmed from `acceptance.sh` and `capture.js`)
- `tests/seed-complete-data.sh` is the reference implementation for the `rich-family` fixture data shape

---

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Technical] Does the `playwright` Docker service need a custom image (e.g. `mcr.microsoft.com/playwright`) or can it run `npx playwright test` from a Node image with browsers installed at build time? Evaluate image size vs. build time tradeoff.
- [Affects R5][Technical] What is the correct health-check polling strategy in `run-regression.sh`? The backend already has a `/api/health` endpoint — confirm the agent service also exposes one before depending on it.

---

## Next Steps

→ `/ce:plan` for structured implementation planning
