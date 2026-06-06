---
title: "fix: Tech Debt Phase 1+2 — Security Hardening + Quick Fixes"
status: active
origin: docs/reviews/2026-06-06-TECH_DEBT_AUDIT.md
created: 2026-06-06
plan_depth: standard
---

# fix: Tech Debt Phase 1+2 — Security Hardening + Quick Fixes

## Problem Frame

The 2026-06-06 tech debt audit identified 3 CRITICAL and 22 HIGH severity items. This plan addresses the **security-critical subset** (Phase 1) and the **highest-ROI quick fixes** (Phase 2) — items that can be completed in ~13h with measurable risk reduction and no architectural rework.

Key risks addressed:
- JWT forgery via weak SECRET_KEY defaults in Docker Compose
- Internal API endpoint exposure in production nginx
- Missing HSTS/CSP security headers
- Unmaintained `python-jose` dependency with known CVEs
- WebSocket memory leaks on navigation
- Non-reproducible builds from unpinned git dependency
- i18n violations breaking localization compliance

---

## Scope Boundaries

### In Scope
- TD-001: Docker Compose SECRET_KEY weak defaults + startup validation
- TD-004: python-jose → PyJWT migration
- TD-005: nginx production internal API block
- TD-006: HSTS + SPA CSP headers
- TD-003: DataStatsPage i18n completion
- TD-017: Magic agent ID constants extraction
- TD-019: LoginPage/RegisterPage i18n completion
- TD-021: useAIReportWS WebSocket leak fix
- TD-023: Alembic migration filename correction
- TD-031: Pin nginx Docker image version
- TD-039: Pin deerflow-harness git commit

### Out of Scope (Deferred to Phase 3+ plan)
- God component splitting (AIChatPage, BabyPage, InsightsTab)
- Shared frontend API package extraction
- db_migrate.py removal
- bare `except Exception` remediation
- httpx client singleton
- CSS hex color tokenization

### Deferred to Follow-Up Work
- Comprehensive `logging.getLogger` → `get_logger` migration (TD-010, 48 files — merits its own PR)
- Rate limiter testing in production mode (TD-026)
- Docker resource limits (TD-007, needs performance profiling)

---

## Key Technical Decisions

1. **PyJWT over authlib** — PyJWT is the most actively maintained JWT library, drop-in compatible with python-jose's `jwt.encode`/`jwt.decode` API shape. authlib is heavier and bundles OAuth flows we don't need.

2. **SECRET_KEY validation at settings layer, not compose** — The compose file should have NO default. The `CoreSettings` validator in `server/packages/core/settings.py` already has a sentinel check but uses `"CHANGE_ME_IN_PRODUCTION"` (uppercase) while compose uses a different lowercase string. Align the sentinel and remove compose defaults entirely.

3. **CSP via nginx, not backend middleware** — The backend already sets a narrow CSP for `/api/` routes. The SPA CSP belongs in nginx where it covers all static asset responses without touching Python code.

4. **Agent ID constants in a dedicated module** — Rather than scattering constants further, create `server/apps/backend/app/constants/system_ids.py` as the single source of truth. Migration files keep their literals (they're historical snapshots), but all runtime code imports from this module.

---

## Implementation Units

### U1. Remove Docker Compose SECRET_KEY Defaults + Harden Startup Validation

**Goal:** Eliminate the path where production starts with a known/weak SECRET_KEY.

**Requirements:** TD-001

**Dependencies:** None

**Files:**
- `docker-compose.yml` (modify)
- `docker-compose.dev.yml` (modify)
- `docker-compose.production.yml` (modify)
- `server/packages/core/settings.py` (modify)
- `server/tests/backend/test_auth_security.py` (modify — add startup validation test)

**Approach:**
- Remove `:-change-me-in-production-use-a-long-random-string` fallback from all compose files. Use `${SECRET_KEY:?SECRET_KEY must be set}` shell parameter expansion which hard-fails if unset.
- Remove empty-string fallbacks for `STORAGE_ENCRYPTION_KEY` and `AI_ENCRYPTION_KEY` (use `:-` → `:?`).
- In `server/packages/core/settings.py`, update the `_DEFAULT_SECRET` sentinel to match what `scripts/deploy-docker.sh` generates, and ensure the production guard fires on any value containing "change-me" or "CHANGE_ME" (case-insensitive).
- Keep `docker-compose.dev.yml` functional by documenting that `.env` is required (the deploy script already generates it).

**Patterns to follow:** Existing `_validate_secret_key()` in `settings.py` line 146.

**Test scenarios:**
- Settings init with SECRET_KEY="change-me-anything" in ENVIRONMENT=production raises RuntimeError
- Settings init with SECRET_KEY="" in ENVIRONMENT=production raises RuntimeError
- Settings init with valid SECRET_KEY in ENVIRONMENT=production succeeds
- Settings init with empty SECRET_KEY in ENVIRONMENT=development auto-generates (existing behavior preserved)

**Verification:** `uv run pytest server/tests/backend/test_auth_security.py -v` passes. Docker compose file syntax validates with `docker compose config`.

---

### U2. Pin nginx Docker Image + Add /api/v1/internal Block to Production

**Goal:** Prevent internal API exposure in production and ensure reproducible nginx builds.

**Requirements:** TD-005, TD-031

**Dependencies:** None

**Files:**
- `nginx.production.conf` (modify)
- `docker-compose.yml` (modify)
- `docker-compose.production.yml` (modify)

**Approach:**
- Add `location ^~ /api/v1/internal { return 403; }` to `nginx.production.conf`, matching the existing block in `nginx.conf`.
- Replace `nginx:alpine` with `nginx:1.27-alpine` in both compose files.

**Patterns to follow:** The existing `/api/v1/internal` block in `nginx.conf` line 24–26.

**Test scenarios:**
- `curl -s -o /dev/null -w "%{http_code}" http://localhost/api/v1/internal/anything` returns 403 against production config
- Regular `/api/v1/` routes still proxy correctly (200)

**Verification:** `docker compose -f docker-compose.production.yml config` validates. Manual nginx config test: `docker run --rm -v $(pwd)/nginx.production.conf:/etc/nginx/conf.d/default.conf nginx:1.27-alpine nginx -t`.

---

### U3. Add HSTS + SPA Content-Security-Policy to Production Nginx

**Goal:** Add defense-in-depth security headers for the frontend SPA.

**Requirements:** TD-006

**Dependencies:** U2 (changes same file)

**Files:**
- `nginx.production.conf` (modify)

**Approach:**
- Add `add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;` to the `server` block's existing security headers section.
- Add a CSP header to the `location /` block (SPA): `add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self' wss:; frame-ancestors 'none';" always;`
- Note: `'unsafe-inline'` is required for Vite's runtime styles and inline event handlers in Vue. `wss:` covers WebSocket connections. `blob:` covers ECharts canvas export.

**Patterns to follow:** Existing `add_header` block in `nginx.production.conf` lines 19–25.

**Test scenarios:**
- Response to `GET /` includes `Strict-Transport-Security` header
- Response to `GET /` includes `Content-Security-Policy` header
- SPA still loads correctly (no CSP violations in console for core flows: login, dashboard, AI chat)

**Verification:** `nginx -t` passes. Manual browser check after docker-compose up for CSP violation console errors.

---

### U4. Migrate python-jose to PyJWT

**Goal:** Replace unmaintained JWT library with actively maintained alternative.

**Requirements:** TD-004

**Dependencies:** None

**Files:**
- `server/pyproject.toml` (modify — swap dependency)
- `server/apps/backend/app/auth/deps.py` (modify)
- `server/apps/backend/app/auth/ai_deps.py` (modify)
- `server/apps/backend/app/routers/device.py` (modify)
- `server/apps/backend/app/services/auth.py` (modify)
- `server/packages/security/service_auth/agent_jwt.py` (modify)
- `server/tests/backend/test_auth.py` (modify if needed)
- `server/tests/backend/test_auth_security.py` (modify if needed)
- `server/tests/backend/test_family.py` (modify if needed)

**Approach:**
- Replace `python-jose[cryptography]>=3.3.0` with `PyJWT[crypto]>=2.8.0` in pyproject.toml.
- API migration pattern:
  - `from jose import jwt, JWTError` → `import jwt; from jwt.exceptions import PyJWTError`
  - `jwt.encode(payload, key, algorithm="HS256")` → same (compatible)
  - `jwt.decode(token, key, algorithms=["HS256"])` → same (compatible)
  - `except JWTError` → `except (jwt.InvalidTokenError, jwt.ExpiredSignatureError)`
  - python-jose uses `exp` claim validation automatically; PyJWT also validates `exp` by default
- Run `uv lock` after dependency swap to update lockfile.

**Patterns to follow:** PyJWT's `jwt.decode(..., algorithms=["HS256"])` requires explicit algorithm list (already the pattern in existing code).

**Test scenarios:**
- Login flow produces valid JWT that can be decoded
- Expired token returns 401
- Token with invalid signature returns 401
- Token with wrong algorithm returns 401
- Agent JWT (service_auth) encode/decode round-trip works
- All existing auth tests pass unchanged (behavioral compatibility)

**Verification:** `uv run pytest server/tests/backend/test_auth.py server/tests/backend/test_auth_security.py server/tests/backend/test_family.py -v` all pass. `uv run ruff check server/apps/backend/app/auth/` clean.

---

### U5. Fix useAIReportWS WebSocket Leak

**Goal:** Prevent WebSocket connections from persisting after component unmount.

**Requirements:** TD-021

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/composables/useAIReportWS.ts` (modify)
- `frontend/apps/main/tests/unit/composables/useAIReportWS.test.ts` (create)

**Approach:**
- Import `onUnmounted` from Vue.
- Add `onUnmounted(() => disconnect())` inside the composable's setup scope.
- This ensures automatic cleanup regardless of whether callers remember to disconnect.

**Patterns to follow:** Other composables in the project (e.g., `useNetwork.ts`) that use lifecycle hooks.

**Test scenarios:**
- Composable auto-disconnects WebSocket when component unmounts
- Manual `disconnect()` still works before unmount
- No error if `disconnect()` called when already disconnected

**Verification:** `pnpm --filter @numina/main test:run -- --grep "useAIReportWS"` passes.

---

### U6. Pin deerflow-harness Git Dependency to Commit SHA

**Goal:** Make Python builds reproducible regardless of upstream changes.

**Requirements:** TD-039

**Dependencies:** None

**Files:**
- `server/pyproject.toml` (modify)

**Approach:**
- Determine the current resolved commit from `uv.lock` or `git ls-remote`.
- Add `rev = "<current-commit-sha>"` to the `[tool.uv.sources]` entry for `deerflow-harness`.
- Run `uv lock` to confirm the lockfile is consistent.

**Patterns to follow:** Standard uv source pinning pattern.

**Test scenarios:**
- `uv lock --check` passes (lockfile consistent with pyproject.toml)
- `uv sync` resolves the same commit on a clean environment

**Verification:** `uv lock --check` exits 0.

---

### U7. Extract Magic Agent ID Constants

**Goal:** Single source of truth for system agent/skill IDs used at runtime.

**Requirements:** TD-017

**Dependencies:** None

**Files:**
- `server/apps/backend/app/constants/__init__.py` (create if not exists)
- `server/apps/backend/app/constants/system_ids.py` (create)
- `server/apps/backend/app/routers/_ai_events_helper.py` (modify)
- `server/apps/backend/app/bootstrap/agents.py` (modify)
- `server/apps/backend/app/bootstrap/skills.py` (modify)
- `server/apps/backend/app/reconcile/registry.py` (modify)
- `server/apps/backend/app/services/agent_dispatch.py` (modify)

**Approach:**
- Create `constants/system_ids.py` with named constants:
  ```
  NUMINA_AGENT_ID = 100000000000005
  ASSET_REPORT_AGENT_ID = 100000000000006
  SKILL_ID_BASE = 100000000000010  # through 100000000000014
  ```
- Replace all runtime references to these literals with imports from the constants module.
- Leave Alembic migration files unchanged (they are historical snapshots).

**Patterns to follow:** Existing `server/apps/backend/app/core/` module organization.

**Test scenarios:**
- All existing tests pass (no behavioral change)
- `grep -rn "100000000000" server/apps/backend/app/ --include="*.py" | grep -v constants/ | grep -v alembic/` returns zero matches in non-migration, non-constants files

**Verification:** `uv run pytest server/tests/backend/ -v --timeout=60` passes. Grep confirms no stray literals.

---

### U8. Fix Alembic Migration Filename Mismatch

**Goal:** Align filename with actual revision ID for searchability.

**Requirements:** TD-023

**Dependencies:** None

**Files:**
- `server/apps/backend/alembic/versions/s0158t32u999_add_total_approved_count_to_users.py` (rename to `s0158t32umn8_add_total_approved_count_to_users.py`)

**Approach:**
- `git mv` the file to use the correct revision ID from its content.
- Verify the Alembic chain is still intact with `alembic history`.

**Test scenarios:**
- `alembic history` shows unbroken chain
- `alembic check` reports no pending migrations

**Verification:** `cd server/apps/backend && uv run alembic history | head -20` shows correct chain. `uv run alembic check` exits cleanly.

---

### U9. DataStatsPage i18n Completion

**Goal:** All user-visible strings use `t()` per project convention.

**Requirements:** TD-003

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/pages/DataStatsPage.vue` (modify)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — if exists)

**Approach:**
- Add `const { t } = useI18n()` to the script setup.
- Add keys under a `dataStats` namespace: `dataStats.title`, `dataStats.totalAssets`, `dataStats.totalLiabilities`, `dataStats.netWorth`, `dataStats.assetTrend`, `dataStats.assetDistribution`, `dataStats.noData`, `dataStats.quickStats`, `dataStats.assetCount`, `dataStats.monthlyNewAssets`, `dataStats.dailyCostTotal`.
- Replace all hardcoded Chinese strings with `t('dataStats.xxx')`.

**Patterns to follow:** Other pages that use `useI18n()` (e.g., `AssetListPage.vue`).

**Test scenarios:**
- Page renders correctly with zh-CN locale (visual regression — same as before)
- All strings appear in locale files
- `grep -n "[一-鿿]" DataStatsPage.vue` returns zero matches in template section (no remaining hardcoded Chinese)

**Verification:** `pnpm --filter @numina/main typecheck` passes. Manual grep confirms no remaining hardcoded strings.

---

### U10. LoginPage + RegisterPage i18n Completion

**Goal:** Complete i18n coverage for auth form labels/placeholders.

**Requirements:** TD-019

**Dependencies:** None

**Files:**
- `frontend/apps/main/src/pages/LoginPage.vue` (modify)
- `frontend/apps/main/src/pages/RegisterPage.vue` (modify)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (modify)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (modify — if exists)

**Approach:**
- LoginPage step 1: replace `label="用户名"`, `placeholder="请输入用户名"`, `label="密码"`, `placeholder="请输入密码"` with `t('login.username')`, `t('login.usernamePlaceholder')`, `t('login.password')`, `t('login.passwordPlaceholder')`.
- RegisterPage: replace all 6 field `label`/`placeholder` pairs with `t('register.xxx')` keys.
- Add corresponding keys to zh-CN locale file.

**Patterns to follow:** LoginPage step 0 and step 2 already use `t()` throughout — match that pattern.

**Test scenarios:**
- Login form renders with correct labels in zh-CN
- Register form renders with correct labels in zh-CN
- `grep -n "label=\"[\\u4e00-\\u9fff]" LoginPage.vue RegisterPage.vue` returns zero matches

**Verification:** `pnpm --filter @numina/main typecheck` passes.

---

## System-Wide Impact

- **Auth flow** (U4): JWT library change affects all authenticated endpoints. Behavioral compatibility is critical — the same tokens must continue to work. No token format change, no forced re-login.
- **Docker deployments** (U1, U2): Existing deployments with properly configured `.env` files are unaffected. Deployments relying on compose-default SECRET_KEY will now fail loudly at startup (intentional).
- **nginx** (U2, U3): Production deployments need updated nginx config. The internal API block (U2) is a security fix — it only restricts access that was already intended to be restricted.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|-----------|
| PyJWT behavioral difference in edge cases | Run full auth test suite; verify token round-trip in integration test |
| CSP too restrictive, breaks SPA features | Start with permissive policy (`'unsafe-inline'` for scripts/styles); tighten in follow-up |
| Existing deploys break on SECRET_KEY validation | Deploy script already generates proper SECRET_KEY; only unmanaged installs affected |
| Alembic rename breaks git blame | Use `git mv` to preserve history tracking |

---

## Sequencing

Units U1–U10 are mostly independent and can be landed in any order. Recommended sequence for minimal conflict:

1. **U2 → U3** (nginx changes in same file, sequential)
2. **U1** (compose + settings, independent)
3. **U4** (python-jose migration, highest-risk, land separately for easy revert)
4. **U5, U6, U7, U8, U9, U10** (all independent, can be parallelized)
