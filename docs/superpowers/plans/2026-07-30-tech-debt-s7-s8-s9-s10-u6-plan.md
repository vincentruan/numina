---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
product_contract_source: ce-plan-bootstrap
type: refactor
depth: standard
date: 2026-07-30
---

# refactor: Backend Tech Debt Cleanup (S7/S8/S9/S10 + U6)

## Summary

Five tech debt items from the UI/UX audit, ordered by cost/benefit ratio. Four backend refactor/security improvements and one documentation task. Total scope: ~60 file touches across server packages, ~10 lines of net new logic, zero new features.

## Problem Frame

The UI/UX audit (2026-07-29) surfaced five medium-term tech debt items spanning architecture violations, incomplete auth migration, security gaps, type safety, and cross-app design consistency. Each is low-risk individually but collectively represents architectural drift.

## Requirements

1. **S9 — Role Enum**: Replace 40+ role string literals (`"owner"`, `"member"`, `"child"`) with a typed `UserRole` enum across backend auth, routers, and services. No DB migration.
2. **S10 — JWT Token Completion**: Wire `AgentClient` to use `create_agent_token()` (JWT) instead of static `AGENT_INTERNAL_TOKEN` (HMAC). Remove legacy HMAC fallback branch.
3. **S7 — Cross-App Import**: Move `generate_weekly_report` from `apps/backend/app/services/` to `packages/domain/literacy/`. Scheduler worker imports from packages, not sibling apps.
4. **S8 — CSP Nonce**: Replace `'unsafe-inline'` in CSP `script-src` with per-request nonce. Backend generates nonce; nginx injects into Vite SPA `<script>` tags.
5. **U6 — Design Token Docs**: Document token mapping between main app and child app CSS variable systems. Documentation only.

## Key Technical Decisions

### KTD-1: UserRole enum location — `packages/core/`

**Decision**: Define `UserRole(str, Enum)` in `server/packages/core/roles.py`.

**Rationale**: `packages/core` is imported by all apps and all other packages. The enum is a pure type with no DB or ORM dependency. `packages/domain` would also work but `core` is lighter — no SQLAlchemy coupling. Since the DB column stays `String(10)` (no migration), the enum is purely a Python-layer type safety tool.

### KTD-2: Agent token — per-call JWT, drop HMAC entirely

**Decision**: `AgentClient.__init__` calls `create_agent_token(family_id)` per instance. Remove `AGENT_INTERNAL_TOKEN` setting and the legacy HMAC branch in `verify_agent_token()`.

**Rationale**: The JWT format is already supported on the verification side. The static HMAC token is a single shared secret — any agent can impersonate any family. JWT binds `family_id` cryptographically per call. Since both backend and agent already support JWT, the HMAC path is dead weight.

### KTD-3: Literacy service — extract to `packages/domain/literacy/`

**Decision**: Create `server/packages/domain/literacy/service.py` with `generate_weekly_report()`. Both `scheduler_worker` and `apps/backend` import from this shared location.

**Rationale**: Follows the established pattern (audit, exchange_rate, snapshot, notification all live in `packages/domain/`). The literacy service has no backend-specific dependencies — it uses `packages/core` settings, `packages/db` models, and `packages/security` for agent JWT.

### KTD-4: CSP nonce — backend middleware + nginx sub_filter

**Decision**: Generate nonce in the existing security headers middleware in `main.py`. Use nginx `sub_filter` to inject `nonce` attribute into `<script>` tags in the Vite-built `index.html`. Two-phase rollout: backend nonce + report-only CSP first, then enforce.

**Rationale**: Vite SPA produces static HTML at build time — there's no server-side template to inject nonce into. nginx `sub_filter` is the standard pattern for adding nonce to static SPAs. Report-only mode allows measuring impact before enforcing.

---

## Implementation Units

### U1. Define UserRole Enum (S9)

**Goal**: Create the `UserRole` enum and make it importable by all backend code.

**Dependencies**: None

**Files**:
- `server/packages/core/roles.py` (create)
- `server/packages/core/__init__.py` (modify — export UserRole)

**Approach**:
1. Create `server/packages/core/roles.py` with:
   - `class UserRole(str, Enum): OWNER = "owner"; MEMBER = "member"; CHILD = "child"`
   - Helper: `is_child(role: str | UserRole) -> bool`, `is_owner(role: str | UserRole) -> bool`
2. Export from `packages/core/__init__.py`

**Patterns to follow**: `packages/core/settings.py` — simple module with constants/types.

**Test scenarios**:
- `UserRole.OWNER == "owner"` (str enum compatibility with DB queries)
- `UserRole.CHILD == "child"` and `UserRole("child") is UserRole.CHILD`
- `is_child("child")` and `is_child(UserRole.CHILD)` both return True

**Verification**: `uv run pytest packages/core/ -v` passes; `uv run mypy packages/core/ --explicit-package-bases` passes.

---

### U2. Replace Role String Literals — Auth Layer (S9)

**Goal**: Replace role string literals in `auth/deps.py` and `auth/ai_deps.py` with `UserRole` enum.

**Dependencies**: U1

**Files**:
- `server/apps/backend/app/auth/deps.py` (modify — ~10 replacements)
- `server/apps/backend/app/auth/ai_deps.py` (modify — if any role literals present)

**Approach**:
1. Add `from packages.core.roles import UserRole` import
2. Replace all `== "child"` → `== UserRole.CHILD`, `== "owner"` → `== UserRole.OWNER`, `!= "owner"` → `!= UserRole.OWNER`
3. Replace `payload.get("role", "member")` default → `payload.get("role", UserRole.MEMBER)`
4. Replace `role="child"` in User creation → `role=UserRole.CHILD`

**Patterns to follow**: `str` Enum comparisons work transparently with SQLAlchemy ORM queries since `UserRole.CHILD == "child"` is True.

**Test scenarios**:
- All existing auth tests pass unchanged (enum values are string-equal to literals)
- `get_current_child()` rejects a user with `role=UserRole.MEMBER`
- `require_owner()` accepts `UserRole.OWNER`, rejects `UserRole.MEMBER`

**Verification**: `uv run pytest tests/backend/ -v -k "auth or deps"` passes; `uv run ruff check apps/backend/` clean.

---

### U3. Replace Role String Literals — Routers (S9)

**Goal**: Replace role string literals across all router files with `UserRole` enum.

**Dependencies**: U1

**Files**:
- `server/apps/backend/app/routers/auth.py` (~10 replacements)
- `server/apps/backend/app/routers/device.py` (~8 replacements)
- `server/apps/backend/app/routers/ai_internal.py` (~4 replacements)
- `server/apps/backend/app/routers/children.py` (1 replacement)
- `server/apps/backend/app/routers/family.py` (1+ replacements)
- `server/apps/backend/app/routers/family_config.py` (1 replacement)
- `server/apps/backend/app/routers/milestones.py` (1 replacement)
- `server/apps/backend/app/routers/coins.py` (1 replacement)
- `server/apps/backend/app/routers/ai_literacy_report.py` (1 replacement)
- `server/apps/backend/app/routers/literacy_parent.py` (2 replacements)
- `server/apps/backend/app/routers/mcp_internal.py` (1 replacement)
- `server/apps/backend/app/routers/ai_mcp.py` (1 replacement)

**Approach**:
1. In each file: add `from packages.core.roles import UserRole` import
2. Replace `User.role == "child"` → `User.role == UserRole.CHILD`
3. Replace `user.role == "owner"` → `user.role == UserRole.OWNER`
4. Replace `role == "child"` → `role == UserRole.CHILD` (local variable comparisons)
5. Replace `role != "owner"` → `role != UserRole.OWNER`

**Test scenarios**:
- `uv run pytest tests/backend/ -v` — full backend suite passes (enum values are string-equal)
- Grep verification: `grep -rn '"owner"\|"member"\|"child"' server/apps/backend/app/routers/` returns 0 hits in role comparisons (may still appear in docstrings/comments)

**Verification**: `uv run ruff check apps/backend/` clean; `uv run mypy apps/backend/` clean; full `uv run pytest tests/backend/ -v` passes.

---

### U4. Complete JWT Agent Token Migration (S10)

**Goal**: Wire `AgentClient` to use per-call JWT tokens; remove legacy HMAC path.

**Dependencies**: None (independent of S9)

**Files**:
- `server/apps/backend/app/services/agent_client.py` (modify — line 28)
- `server/apps/backend/app/auth/ai_deps.py` (modify — remove lines 92-108 HMAC fallback)
- `server/apps/backend/app/config.py` (modify — deprecate/remove `AGENT_INTERNAL_TOKEN`)
- `server/packages/core/settings.py` (modify — remove `AGENT_INTERNAL_TOKEN` from settings if defined there)
- `server/tests/backend/test_agent_client.py` or similar (modify — update test expectations)

**Approach**:
1. In `agent_client.py`: replace `"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN` with `"X-Agent-Token": create_agent_token(self.family_id)`. Add import for `create_agent_token` from `packages.security.service_auth.agent_jwt`.
2. In `ai_deps.py`: remove the entire `# Legacy: static HMAC token` block (lines 92-108). Remove `import hmac`. Keep only the JWT verification path. If JWT verification fails, raise 401 directly instead of falling through.
3. In `config.py`: remove `AGENT_INTERNAL_TOKEN` field (or keep with `deprecated` marker for one release cycle if env vars reference it).
4. Update agent-side token verification if needed — verify agent app's incoming token validation is already using `verify_agent_token` from `ai_deps.py`.

**Patterns to follow**: `packages/security/service_auth/agent_jwt.py` — the `create_agent_token()` function is already production-tested for the backend→agent direction.

**Test scenarios**:
- `AgentClient` sends `X-Agent-Token` header containing a valid JWT (decode and verify `fid` claim matches the family_id passed to constructor)
- `verify_agent_token()` rejects a static HMAC token (no longer accepted)
- `verify_agent_token()` rejects a JWT with mismatched `fid` vs `X-Family-Id` header
- `verify_agent_token()` rejects an expired JWT (TTL = 300s)
- Agent service can still authenticate to backend using JWT token

**Verification**: `uv run pytest tests/backend/ -v -k "agent"` passes; manual test: backend→agent API call succeeds with JWT token.

---

### U5. Extract Literacy Report Service to packages/domain (S7)

**Goal**: Move literacy report generation logic out of `apps/backend` into `packages/domain/literacy/` so scheduler_worker can import it without cross-app violation.

**Dependencies**: None (independent of S9, S10)

**Files**:
- `server/packages/domain/literacy/__init__.py` (create)
- `server/packages/domain/literacy/service.py` (create — extract from `apps/backend/app/services/literacy_report.py`)
- `server/apps/backend/app/services/literacy_report.py` (modify — thin wrapper or delete if fully moved)
- `server/apps/backend/app/routers/ai_literacy_report.py` (modify — import from packages/domain)
- `server/apps/backend/app/routers/literacy_parent.py` (modify — import from packages/domain)
- `server/apps/scheduler_worker/jobs/__init__.py` (modify — change import on line 301)

**Approach**:
1. Create `packages/domain/literacy/` package
2. Move the core `generate_weekly_report()` function and its helpers from `apps/backend/app/services/literacy_report.py` to `packages/domain/literacy/service.py`
3. Replace any backend-specific imports in the moved code with package-level equivalents:
   - `apps.backend.app.database` → use `packages.db.session.SessionLocal`
   - `apps.backend.app.config.settings` → `packages.core.settings.settings`
   - ORM models: use `packages.db.models.*` where available; keep backend model imports if the model is backend-specific
4. In backend routers: update imports to `from packages.domain.literacy.service import generate_weekly_report`
5. In scheduler_worker: change line 301 from `from apps.backend.app.services.literacy_report import generate_weekly_report` to `from packages.domain.literacy.service import generate_weekly_report`

**Patterns to follow**: `packages/domain/audit/service.py`, `packages/domain/snapshot/` — existing domain services that are consumed by both backend and scheduler_worker.

**Test scenarios**:
- `scheduler_worker` startup: no `apps.backend` import error (verify `grep -rn "from apps.backend" server/apps/scheduler_worker/` returns 0)
- `generate_weekly_report()` called from scheduler_worker context works (unit test with mock DB)
- Backend literacy endpoints still work (existing tests pass)
- `uv run ruff check apps/scheduler_worker/` clean; `uv run mypy apps/scheduler_worker/ --explicit-package-bases` clean

**Verification**: Zero cross-app imports in scheduler_worker; `uv run pytest tests/backend/ -v -k "literacy"` passes; `uv run pytest apps/scheduler_worker/ -v` passes.

---

### U6. CSP Nonce — Backend (S8 Phase 1)

**Goal**: Generate per-request CSP nonce in the security headers middleware; output CSP with `'nonce-<value>'` instead of `'unsafe-inline'`.

**Dependencies**: None (independent of all other units)

**Files**:
- `server/apps/backend/app/main.py` (modify — lines 359-376, security headers section)

**Approach**:
1. In the security headers middleware section of `main.py`:
   - Generate nonce: `nonce = secrets.token_urlsafe(16)`
   - Store on request state: `request.state.csp_nonce = nonce`
   - Replace `script-src 'self' 'unsafe-inline'` with `script-src 'self' 'nonce-{nonce}'`
   - Keep `style-src 'self' 'unsafe-inline'` for now (Vant component library needs inline styles; separate follow-up)
2. Add `secrets` import at top of `main.py`
3. Consider adding nonce to `connect-src` for development WebSocket connections if needed

**Patterns to follow**: The existing middleware pattern in `main.py:330-376` already handles per-request security headers (X-Content-Type-Options, X-Frame-Options, etc.). Nonce generation follows the same per-request pattern.

**Test scenarios**:
- Every API response includes `Content-Security-Policy` header with `script-src 'self' 'nonce-<base64-value>'`
- Nonce value is different per request (not static)
- Nonce is accessible via `request.state.csp_nonce` for downstream handlers
- Development mode: CSP includes localhost connect-src entries alongside nonce

**Verification**: Manual test: `curl -I http://localhost:8000/api/v1/auth/me` shows CSP header with nonce; `uv run pytest tests/backend/ -v` passes.

---

### U7. CSP Nonce — Frontend Nginx Injection (S8 Phase 2)

**Goal**: Inject CSP nonce into Vite SPA `<script>` tags via nginx `sub_filter`.

**Dependencies**: U6

**Files**:
- `docker/nginx.conf` or `docker/nginx/` config (modify — add `sub_filter` rules)
- `frontend/apps/main/vite.config.ts` (modify — add `build.rollupOptions.output` to ensure script tags are present in built HTML)

**Approach**:
1. In nginx config, after serving `index.html`:
   - Use `sub_filter` to replace `<script` with `<script nonce="$csp_nonce"` where `$csp_nonce` comes from the backend response header
   - Alternative: since nginx doesn't easily read backend response headers for sub_filter, use a simpler approach — have nginx generate its own nonce and pass it to backend via a header, or use `add_header` with a static nonce rotated on deploy
   - Simplest viable: add `sub_filter '<script ' '<script nonce="deploy-rotate-nonce" ';` with nonce rotated per deploy
2. Document the two-phase rollout: start with `Content-Security-Policy-Report-Only` header (non-blocking), monitor violations, then switch to enforcing `Content-Security-Policy`

**Patterns to follow**: Standard nginx SPA serving pattern already in use.

**Test scenarios**:
- Nginx serves `index.html` with `<script nonce="...">` injected
- Browser console shows no CSP violations in report-only mode
- After switching to enforce mode: app loads and functions normally

**Verification**: `docker-compose up -d --build`; browser loads app; no CSP violations in console.

---

### U8. Cross-App Design Token Documentation (U6)

**Goal**: Document the token mapping between main app and child app CSS variable systems for future consistency.

**Dependencies**: None

**Files**:
- `docs/design-tokens.md` (create)

**Approach**:
1. Create `docs/design-tokens.md` with:
   - Overview of the two design systems (Together AI for main, Clay for child)
   - Token mapping table: semantic tokens that overlap (`--color-success`, `--color-error`, `--color-canvas`, `--color-ink`, `--color-on-primary`, `--color-on-dark`, `--color-muted`)
   - Brand palette reference: main app brand colors vs child app brand colors (side by side)
   - Naming conventions: `--color-*` prefix patterns in each app
   - A11y contrast requirements: WCAG AA minimum for text/background pairs
   - Guidance: when to share tokens vs when to keep app-specific
2. Do NOT merge CSS or create shared packages — the two apps serve different audiences

**Test expectation: none — documentation only.

**Verification**: Document is accurate against current `frontend/apps/main/src/style.css` and `frontend/apps/child/src/assets/clay.css` token values.

---

## Scope Boundaries

### Non-Goals
- Database migration for role column (stays `String(10)` — enum is Python-layer only)
- CSS variable merging between main and child apps (different brand identities)
- Agent-side token verification changes (already JWT-compatible)
- `style-src` nonce migration (Vant needs `'unsafe-inline'` for styles — separate effort)
- Adding `Role` CHECK constraint to database

### Deferred to Follow-Up Work
- Migrate `style-src 'unsafe-inline'` to nonce-based CSP (requires auditing Vant inline styles)
- Add `UserRole` type annotation to `User.role` Mapped column (requires SQLAlchemy enum integration)
- Create `frontend/packages/design-tokens/` shared npm package (if apps converge further)
- Per-family agent token scoping (JWT already binds family_id; further scoping is unnecessary)

---

## Risks & Dependencies

| Risk | Mitigation |
|------|-----------|
| S9: `str` Enum comparison with SQLAlchemy may behave differently in some query contexts | `UserRole(str, Enum)` ensures `UserRole.CHILD == "child"` is True; SQLAlchemy filters pass string value to DB. Test with actual queries in U2/U3. |
| S10: Removing HMAC may break if any caller still uses `AGENT_INTERNAL_TOKEN` | Grep all references to `AGENT_INTERNAL_TOKEN` before removing. The only consumer is `AgentClient.__init__` (line 28). |
| S7: Moving literacy service may miss a backend-specific import | Audit all imports in `literacy_report.py` before moving. Replace with package equivalents. |
| S8: nginx `sub_filter` may not work with gzipped responses | Add `gunzip on;` or disable gzip for `index.html`; test with `curl --compressed`. |
| S8: CSP nonce breaks Vant or third-party scripts that use inline `<script>` | Use report-only mode first; audit violations before enforcing. |

---

## Verification Contract

1. `uv run pytest tests/backend/ -v` — 0 failures
2. `uv run ruff check apps/backend/ apps/scheduler_worker/ packages/` — 0 violations
3. `uv run mypy apps/backend/ --explicit-package-bases` — 0 errors
4. `uv run mypy apps/scheduler_worker/ --explicit-package-bases` — 0 errors
5. `grep -rn "from apps.backend" server/apps/scheduler_worker/` — 0 results
6. `grep -rn '"owner"\|"member"\|"child"' server/apps/backend/app/routers/ server/apps/backend/app/auth/` — 0 results in code (docstrings/comments excluded)
7. `curl -I localhost:8000/api/v1/auth/me` — CSP header contains `nonce-`
8. `cd frontend/apps/main && pnpm typecheck` — 0 errors
9. `cd frontend/apps/child && pnpm typecheck` — 0 errors

---

## Definition of Done

- All 8 implementation units complete and verified
- All verification contract gates pass
- Each unit committed separately (one commit per U-ID) in dependency order: U1→U2→U3 (S9 chain), U4 (S10), U5 (S7), U6→U7 (S8 chain), U8 (U6 doc)
- No regressions in existing test suites
