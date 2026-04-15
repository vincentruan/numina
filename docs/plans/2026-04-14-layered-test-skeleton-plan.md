---
date: 2026-04-14
status: active
origin: docs/brainstorms/2026-04-14-layered-test-skeleton-requirements.md
---

# Plan: Layered Test Skeleton

## Problem Frame

Zero browser-level assertions exist. Curl-based shell E2E scripts test the API layer only. The Puppeteer screenshot script has no assertions. No CI gate. This plan builds the foundational skeleton: Playwright wired to Docker, fixed test accounts seeded at startup, a shared auth helper, and route guard coverage as the first concrete test layer.

(see origin: docs/brainstorms/2026-04-14-layered-test-skeleton-requirements.md)

---

## Key Technical Decisions

**Auth strategy — fixed test accounts, not per-test registration**
The backend rate-limits registration to 5/hour/IP. UUID-per-fixture registration in `beforeEach` would hit this limit immediately (auth-guards.spec.ts alone runs 31 tests). Instead: three fixed test accounts (`test_empty`, `test_rich`, `test_asset`) are created once at harness startup via `tests/seed-accounts.sh`. Each fixture logs in as its dedicated account. Accounts are recreated if the Docker volume is wiped (`down -v`).

**Playwright location — `tests/package.json` (TypeScript)**
Although `playwright >=1.58.0` is already declared in `backend/pyproject.toml` as a dev dep, the E2E suite lives in `tests/package.json` with TypeScript. This keeps test tooling separate from the Python backend, uses standard Playwright TypeScript patterns, and avoids mixing `uv run` with `npx` invocations.

**Auth flow — `page.request.post()` + `localStorage['numina_user']`**
The app uses httpOnly cookies (Phase 2 security model). `storage.ts` stubs `getToken()` to return null — JS cannot read the auth token. `loginAs` must:
1. Call `page.request.post('/api/v1/auth/login')` — browser context receives the httpOnly cookie from the server `Set-Cookie` header
2. Call `page.request.get('/api/v1/auth/me')` — get the user object
3. Inject `localStorage['numina_user']` with the user object — satisfies the Vue router guard's `getUser()` check
4. Navigate to the target page — Axios sends the cookie automatically via `withCredentials: true`

**Base URL — `http://localhost` (nginx port 80)**
Nginx serves the frontend at `/` with no sub-path prefix. The old Puppeteer script's `http://localhost/numina/` URL is stale. All Playwright tests target `http://localhost`.

**`workers: 1` — SQLite write safety**
Prevents `SQLITE_BUSY` errors from concurrent fixture API calls. Revisit when the project moves to PostgreSQL.

**Docker volume teardown — `down -v`**
The harness uses `docker compose --profile test down -v` to destroy the SQLite volume on teardown. This ensures a clean DB on every run and prevents unbounded DB growth across runs. `trap EXIT` guarantees teardown even on crash.

---

## File Layout

```
tests/
├── package.json                  # Playwright + TypeScript deps (new)
├── tsconfig.json                 # TypeScript config for tests (new)
├── playwright.config.ts          # Playwright config: baseURL, viewport, workers (new)
├── run-regression.sh             # Single-command harness (new)
├── seed-accounts.sh              # Creates fixed test accounts at startup (new)
├── lib/
│   ├── auth.ts                   # loginAs() helper (new)
│   ├── fixtures.ts               # emptyFamily(), richFamily(), singleAsset() (new)
│   └── routes.ts                 # Route manifest constant (new)
├── e2e/
│   ├── auth-guards.spec.ts       # Route guard coverage + sync-check (new)
│   └── smoke.spec.ts             # Asset detail page smoke test (new)
├── data/
│   └── seed-data.sh              # Existing — reference for richFamily fixture data shape
├── screenshot/
│   └── capture.js                # Existing — not modified
└── e2e/ (existing shell scripts)
    ├── acceptance.sh             # Existing — not modified
    ├── extended.sh               # Existing — not modified
    └── wishes-liabilities.sh     # Existing — not modified

# Root cleanup:
# package.json (root)             # DELETE — move puppeteer to tests/package.json
```

---

## Implementation Units

### Unit 1: `tests/package.json` + `tests/tsconfig.json` + `tests/playwright.config.ts`

**What:** Bootstrap the Playwright TypeScript project in `tests/`.

**`package.json` deps:**
- `@playwright/test` (latest stable, ~1.52)
- `puppeteer` (moved from root)
- `typescript`, `@types/node`

**`playwright.config.ts` settings:**
- `baseURL: 'http://localhost'`
- `use.viewport: { width: 390, height: 844 }` (iPhone 14)
- `workers: 1`
- `projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }]` — override viewport to mobile
- `testDir: './e2e'`
- `reporter: [['list'], ['html', { open: 'never' }]]`
- `timeout: 30_000` per test
- `retries: 0` (no retries — failures should be deterministic)

**Root cleanup:** Delete root `package.json`, move `puppeteer` devDep to `tests/package.json`.

**Test scenarios:** None — this unit has no test file. Verified by `npx playwright --version` succeeding.

---

### Unit 2: `tests/seed-accounts.sh`

**What:** Creates three fixed test accounts via the backend API. Called by `run-regression.sh` after Docker health checks pass. Idempotent — if an account already exists (409 on register), it logs a warning and continues.

**Accounts:**

| Account | Password | Purpose |
|---|---|---|
| `test_empty` | `TestEmpty123!` | `emptyFamily()` fixture — no assets |
| `test_rich` | `TestRich123!` | `richFamily()` fixture — full seed data |
| `test_asset` | `TestAsset123!` | `singleAsset()` fixture — one physical asset |

**Sequence per account:**
1. `POST /api/v1/auth/register` with `{ username, display_name, password, family_name }`
2. If 409 (already exists): log "account exists, skipping" and continue
3. If `test_rich`: call `POST /api/v1/assets` × 30, `POST /api/v1/liabilities` × 3, `POST /api/v1/wishes` × 5 using the token from step 1 — mirror `tests/data/seed-data.sh` data shape
4. If `test_asset`: call `POST /api/v1/assets` × 1 (physical, 房产 category, ¥1,000,000)

**Note:** `test_rich` seeding is the most expensive step (~35 API calls). This runs once per harness invocation, not per test.

**Test scenarios:** None — verified by `run-regression.sh` completing without error.

---

### Unit 3: `tests/lib/auth.ts`

**What:** Shared `loginAs(page, username, password)` helper. All tests call this; no test duplicates the login sequence.

**Implementation approach:**
```
// Directional sketch — not implementation spec
async function loginAs(page, username, password) {
  // 1. POST login — browser context receives httpOnly Set-Cookie
  const loginResp = await page.request.post('/api/v1/auth/login', {
    data: { username, password }
  })
  if (!loginResp.ok()) throw new Error(`loginAs failed: ${loginResp.status()} for ${username}`)

  // 2. GET /auth/me — fetch user object (TokenResponse does not include user)
  const meResp = await page.request.get('/api/v1/auth/me')
  const user = await meResp.json()

  // 3. Inject numina_user into localStorage — satisfies router guard getUser() check
  // Must navigate to a page first so localStorage is accessible
  await page.goto('/')
  await page.evaluate((u) => localStorage.setItem('numina_user', JSON.stringify(u)), user)
}
```

**Test scenarios for `auth.ts`:**
- `loginAs` with valid credentials → subsequent `page.goto('/assets')` does NOT redirect to `/login`
- `loginAs` with wrong password → throws an error containing the status code
- After `loginAs`, `page.evaluate(() => localStorage.getItem('numina_user'))` returns a non-null JSON string

---

### Unit 4: `tests/lib/fixtures.ts`

**What:** Three fixture functions that log in as the appropriate fixed account and return credentials.

**Implementation approach:**
```
// Directional sketch
export async function emptyFamily(page): Promise<Credentials> {
  await loginAs(page, 'test_empty', 'TestEmpty123!')
  return { username: 'test_empty', password: 'TestEmpty123!' }
}

export async function richFamily(page): Promise<Credentials> {
  await loginAs(page, 'test_rich', 'TestRich123!')
  return { username: 'test_rich', password: 'TestRich123!' }
}

export async function singleAsset(page): Promise<Credentials> {
  await loginAs(page, 'test_asset', 'TestAsset123!')
  return { username: 'test_asset', password: 'TestAsset123!' }
}
```

**Important:** Because fixtures share fixed accounts (not isolated per-test), tests must not mutate shared state (e.g., delete assets, change settings). Tests in this skeleton are read-only or navigation-only. Write-path tests in future layers should use a different isolation strategy.

**Test scenarios for `fixtures.ts`:**
- `emptyFamily(page)` → `page.goto('/assets')` renders the assets page (no redirect to `/login`)
- `richFamily(page)` → `page.goto('/')` renders the dashboard with non-zero net worth
- `singleAsset(page)` → `page.goto('/assets')` renders at least one asset in the list

---

### Unit 5: `tests/lib/routes.ts`

**What:** Typed constant listing all 31 navigable routes, used by `auth-guards.spec.ts`.

**Structure:**
```typescript
// Directional sketch
export const PROTECTED_ROUTES = [
  { name: 'Dashboard', path: '/' },
  { name: 'AssetList', path: '/assets' },
  { name: 'AssetCreate', path: '/assets/new' },
  { name: 'AssetDetail', path: '/assets/1' },      // sentinel ID
  { name: 'AssetEdit', path: '/assets/1/edit' },
  { name: 'AssetSell', path: '/assets/1/sell' },
  // ... all 28 protected routes
] as const

export const GUEST_ROUTES = [
  { name: 'Login', path: '/login' },
  { name: 'Register', path: '/register' },
  { name: 'JoinFamily', path: '/join-family' },
] as const
```

**Parameterized routes** (`/assets/:id`, `/liabilities/:id`, etc.) use sentinel value `1` — the guard test only needs to confirm redirect to `/login`, not that the resource exists.

**Sync-check:** `auth-guards.spec.ts` imports the Vue router config (via a relative import of `../../frontend/src/router/index.ts`) and asserts that every route `name` in the router appears in `PROTECTED_ROUTES` or `GUEST_ROUTES`. Fails if a route is added to the router without updating `routes.ts`.

**Note on importing Vue router in Node/Playwright context:** The router file imports Vue and vue-router. Playwright tests run in Node, not a browser. The sync-check test must either: (a) use a lightweight parse of `router/index.ts` as text (regex extract route names), or (b) configure `tsconfig.json` to resolve Vue imports. Option (a) is simpler and avoids a Vue dependency in the test layer. The plan defers the exact approach to implementation — both are valid.

---

### Unit 6: `tests/e2e/auth-guards.spec.ts`

**What:** Data-driven route guard coverage. Two loops over `routes.ts`.

**Test scenarios:**

*Unauthenticated → protected routes (28 tests):*
- For each route in `PROTECTED_ROUTES`: navigate without calling `loginAs`, assert `page.url()` ends with `/login`
- Parameterized routes use sentinel ID `1`

*Authenticated → guest routes (3 tests):*
- Call `emptyFamily(page)` in `beforeAll` (one login for all 3 guest-route tests)
- For each route in `GUEST_ROUTES`: navigate, assert `page.url()` ends with `/` (redirected to dashboard)

*Sync-check (1 test):*
- Parse route names from `frontend/src/router/index.ts`
- Assert every name appears in `PROTECTED_ROUTES` or `GUEST_ROUTES`
- Fails with a diff listing missing routes

**Total: 32 test cases in this file.**

---

### Unit 7: `tests/e2e/smoke.spec.ts`

**What:** Basic smoke test using `singleAsset()` fixture. Gives `fixture:single-asset` a concrete consumer.

**Test scenarios:**
- `singleAsset(page)` → `page.goto('/assets')` → assert page contains at least one asset card (check for a Vant `van-cell` or asset name text)
- Navigate to the asset detail page → assert no JS console errors → assert page title or asset name is visible
- Navigate to `/` (Dashboard) → assert no JS console errors → assert the page renders (net worth element visible)

---

### Unit 8: `tests/run-regression.sh`

**What:** Single-command harness. Orchestrates the full sequence.

**Sequence:**
1. Parse `--keep-up` flag
2. Set `trap 'docker compose --profile test down -v' EXIT` (skipped if `--keep-up`)
3. `docker compose --profile test up -d`
4. Poll `GET http://localhost/api/health` until 200 (max 60s, 2s interval) — backend ready
5. Poll `GET http://localhost:8001/health` until 200 (max 60s) — agent ready (if endpoint exists; skip if 404)
6. Run `tests/seed-accounts.sh`
7. `cd tests && npm ci && npx playwright test`
8. Capture exit code
9. Print elapsed time + `PASSED` / `FAILED`
10. Exit with captured code (trap fires teardown)

**`--keep-up` behavior:** Overrides the trap — teardown is not registered. Docker stays up after the run for debugging.

**Agent health check:** The plan defers confirmation of whether `GET http://localhost:8001/health` exists to implementation. If it returns 404, the harness skips the agent health poll and proceeds. The backend health check is sufficient to confirm the stack is ready for most tests.

---

### Unit 9: `docker-compose.yml` — `test` profile service

**What:** Add a `playwright` service under `profiles: [test]`.

**Service definition approach:**
```yaml
# Directional sketch
playwright:
  image: mcr.microsoft.com/playwright:v1.52.0-noble
  container_name: numina-playwright
  working_dir: /tests
  volumes:
    - ./tests:/tests
  command: npx playwright test
  depends_on:
    backend:
      condition: service_healthy
    agent:
      condition: service_healthy
  network_mode: host   # OR use service name 'nginx' as baseURL
  profiles:
    - test
```

**Image decision:** Use `mcr.microsoft.com/playwright` (official image with browsers pre-installed) rather than a plain Node image. Avoids `npx playwright install` at runtime (slow, ~300MB download). The image is ~1.5GB but cached after first pull.

**Network:** The playwright container needs to reach nginx on port 80. Two options:
- `network_mode: host` — simplest, `http://localhost` works directly
- Docker bridge network with `baseURL: http://nginx` — requires changing `playwright.config.ts` baseURL

The harness script runs Playwright from the host (`cd tests && npx playwright test`), not from inside the Docker container. The `playwright` Docker service is optional — it exists for CI environments where running Playwright on the host is not possible. The harness script is the primary execution path for local development.

**Revised harness approach:** `run-regression.sh` runs `npx playwright test` on the host (after `npm ci`), not inside Docker. The Docker `playwright` service is a CI convenience, not required for local runs.

---

## Sequencing

```
1. Unit 1  — tests/package.json + playwright.config.ts  (no deps)
2. Unit 9  — docker-compose.yml test profile            (no deps)
3. Unit 2  — seed-accounts.sh                           (needs docker-compose test profile)
4. Unit 8  — run-regression.sh                          (needs Units 1, 2, 9)
5. Unit 3  — tests/lib/auth.ts                          (needs Unit 1)
6. Unit 4  — tests/lib/fixtures.ts                      (needs Unit 3)
7. Unit 5  — tests/lib/routes.ts                        (needs Unit 1)
8. Unit 6  — auth-guards.spec.ts                        (needs Units 4, 5)
9. Unit 7  — smoke.spec.ts                              (needs Units 4)
```

Units 1 and 9 can be done in parallel. Units 3–5 can be done in parallel after Unit 1.

---

## Test Scenarios Summary

| File | Scenarios | Fixture used |
|---|---|---|
| `auth.ts` (inline verification) | 3 | — |
| `fixtures.ts` (inline verification) | 3 | fixed accounts |
| `auth-guards.spec.ts` | 32 (28 unauth + 3 auth + 1 sync-check) | `emptyFamily` |
| `smoke.spec.ts` | 3 | `singleAsset` |
| **Total** | **41** | |

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Agent service has no `/health` endpoint | Harness skips agent health poll if endpoint returns 404; backend health check is sufficient |
| `mcr.microsoft.com/playwright` image unavailable (China network) | Use `X_DOCKER_MIRROR` prefix (already used in docker-compose.yml for mysql/postgres images) |
| Vue router import fails in Node/Playwright context for sync-check | Use regex text parse of router/index.ts instead of ES module import |
| Fixed test accounts accumulate mutations across test runs | This skeleton's tests are navigation/read-only; document this constraint in `tests/README.md` |
| `test_rich` seeding takes >30s on first run | Acceptable — runs once per harness invocation, not per test |
| `capture.js` stale base URL (`/numina/`) | Out of scope — not modified in this initiative; noted in scope boundaries |

---

## Scope Boundaries (carried from origin)

- No CI pipeline (GitHub Actions) — follow-on
- No visual regression / pixel diffing
- No API contract snapshot test
- No cross-family isolation browser test
- No empty-state gauntlet tests
- No Firefox or WebKit
- No Page Object Model
- Existing shell E2E scripts not deleted

---

## Dependencies / Assumptions

- Docker and Docker Compose available on developer machine
- `mcr.microsoft.com/playwright` image accessible (or mirror configured via `X_DOCKER_MIRROR`)
- Backend `/api/v1/auth/register` and `/api/v1/auth/login` stable
- Nginx serves at `http://localhost` (port 80) with no sub-path prefix — confirmed from `nginx.conf`
- `tests/data/seed-data.sh` is the reference for `test_rich` account seed data shape
- Vue router file at `frontend/src/router/index.ts` is the source of truth for route names

---

## Outstanding Questions (deferred to implementation)

- **Agent health endpoint:** Does `GET http://localhost:8001/health` return 200? If not, harness skips the poll.
- **Sync-check import strategy:** Regex parse vs. ES module import of `router/index.ts` — decide at implementation time based on whether Vue/vue-router can be resolved in the Playwright Node context.
- **`X_DOCKER_MIRROR` for Playwright image:** Confirm whether `mcr.microsoft.com` needs mirroring in the target environment.
