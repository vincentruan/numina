---
title: "refactor: Simplify Caching Strategy — Remove TTL Cache, Keep Bundle Endpoint"
type: refactor
status: completed
date: 2026-04-17
origin: docs/brainstorms/2026-04-17-performance-caching-requirements.md
---

# refactor: Simplify Caching Strategy — Remove TTL Cache, Keep Bundle Endpoint

## Overview

The dashboard caching implementation (PR on `fix/children-system-review`) introduced two distinct improvements bundled together:

1. **Bundle endpoint** (`GET /dashboard/bundle`): collapses 7 parallel HTTP requests into 1 — a real, permanent network win
2. **In-memory TTL cache** (60–90s, keyed by `family_id`): caches the bundle response in process memory, invalidated by 16 write call sites across 3 router files

User feedback: the TTL cache adds complexity that doesn't align with first principles for a self-hosted family app where dashboard data is inherently dynamic. This plan evaluates the tradeoff and proposes a targeted simplification: **keep the bundle endpoint, remove the TTL cache layer and its 16 invalidation call sites**.

Additionally, the research revealed that the core `assets` and `liabilities` tables have no indexes on their most-queried columns (`family_id`, `is_archived`, `is_active`). Adding these indexes is low-risk hygiene that future-proofs the schema.

## Problem Frame

The original performance problem had two distinct root causes:

| Problem | Root Cause | Solution |
|---|---|---|
| 7 HTTP round-trips on dashboard load | Frontend `fetchAll()` fires 7 parallel requests | Bundle endpoint (7→1) — **already implemented, keep** |
| Slow DB queries at scale | No indexes on `family_id`, `is_archived`, `is_active` | Add composite indexes — **new work in this plan** |

The TTL cache was added to address the second problem, but for a self-hosted SQLite deployment with 30–100 assets, the actual DB query time is ~2–6ms for 12–13 queries. The real bottleneck was always the HTTP round-trips, not the DB. The cache adds:

- 16 manual invalidation call sites across `assets.py`, `liabilities.py`, `import_.py` — a maintenance surface that grows with every new write endpoint
- Stale-read risk for date-sensitive data (`get_expiring_soon_assets`, `get_trend`) that changes at midnight without a write operation
- Low cache hit rate in practice: the 60–90s TTL means the cache is cold for any user who doesn't reload the dashboard within 90 seconds of their last visit — which is the common case for a family app
- Complexity that conflicts with the project's simplicity-first guidelines (`CLAUDE.md`: "No abstractions for single-use code", "Ask: would a senior engineer say this is overcomplicated?")

The bundle endpoint's value is independent of the cache. It reduces connection overhead, serialization overhead, and frontend complexity regardless of whether the response is cached.

## Requirements Trace

### Keep
- R-keep-1. The bundle endpoint (`GET /dashboard/bundle`) is preserved — it remains the single entry point for `fetchAll()` in the frontend
- R-keep-2. The frontend `fetchAll()` continues to call `/dashboard/bundle` (no regression to 7 parallel calls)
- R-keep-3. Nginx static asset caching (`immutable` for hashed JS/CSS, `no-cache` for `index.html`) is preserved — unrelated to this refactor
- R-keep-4. HTTP cache headers on stable endpoints (`/categories`, `/family/members`, `/family/info`) are preserved — these are genuinely static data

### Remove
- R-remove-1. The TTL in-memory cache is removed from the bundle endpoint — cache miss on every request, direct DB aggregation
- R-remove-2. All 16 `invalidate_dashboard_bundle()` call sites are removed from `assets.py`, `liabilities.py`, `import_.py`
- R-remove-3. `get_dashboard_cache()`, `reset_dashboard_cache()`, `invalidate_dashboard_bundle()` are removed from `backend/app/services/cache/factory.py`
- R-remove-4. The `_dashboard_cache` global singleton is removed from `backend/app/services/cache/factory.py`

### Add
- R-add-1. Add a composite index on `(family_id, is_archived)` for the `assets` table
- R-add-2. Add a composite index on `(family_id, is_active)` for the `liabilities` table
- R-add-3. Add an index on `(family_id, snapshot_date)` for `asset_snapshots` (the existing UniqueConstraint covers this, verify and document)

## Scope Boundaries

- **Not changing**: The bundle endpoint itself — it stays, just without the cache layer
- **Not changing**: Frontend `fetchAll()` — it already calls the bundle endpoint, no change needed
- **Not changing**: Nginx config, HTTP cache headers on stable endpoints — these are correct and unrelated
- **Not changing**: `get_rate_limit_cache()`, `get_captcha_payload_cache()` — these are correctness-critical caches, not performance caches
- **Not changing**: `ExchangeRateService._cache` — already a process-level dict, not part of this refactor
- **Not adding**: Redis, Service Worker, Pinia persistence — out of scope per original requirements
- **Not adding**: Long-lived dashboard caching (e.g., 5-minute TTL) — the user's feedback is that dynamic data shouldn't be cached; if caching is revisited, it belongs in a separate plan with explicit product decision

## Context & Research

### Relevant Code and Patterns

- `backend/app/services/cache/factory.py` — contains `get_dashboard_cache()`, `reset_dashboard_cache()`, `invalidate_dashboard_bundle()` to remove; `get_rate_limit_cache()` and `get_captcha_payload_cache()` to preserve
- `backend/app/routers/dashboard.py:117–154` — bundle endpoint, remove cache hit/miss logic, keep the 7-service aggregation
- `backend/app/routers/assets.py` — 12 references to remove (1 import + 11 call sites)
- `backend/app/routers/liabilities.py` — 5 references to remove (1 import + 4 call sites)
- `backend/app/routers/import_.py` — 2 references to remove (1 import + 1 call site)
- `backend/app/models/asset.py` — `family_id`, `is_archived`, `status` columns have no `index=True`
- `backend/app/models/liability.py` — `family_id`, `is_active` columns have no `index=True`
- `backend/app/models/snapshot.py` — has `UniqueConstraint("family_id", "user_id", "snapshot_date")` which creates an implicit index in SQLite; confirmed sufficient for `get_trend()` which filters on `family_id + user_id=None + snapshot_date`
- `backend/alembic/versions/` — **pre-existing defect**: three files share revision ID `a1b2c3d4e5f6`; multi-head branch with 3 active heads — must be fixed before Unit 4 can run (see Unit 4a below)
- `backend/tests/conftest.py` — confirmed: no `reset_dashboard_cache` reference exists; no edit needed

### Institutional Learnings

- `docs/solutions/best-practices/redis-fail-fast-strategy.md`: The project's own cache classification puts dashboard data in the "performance-only / cache miss acceptable" bucket. A cache miss means a slightly slower response, not incorrect behavior. This classification supports removing the TTL cache.
- `docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md`: The documented pattern for "too many dashboard requests" in this codebase is a **batch/bundle endpoint**, not an in-memory cache. The bundle endpoint is architecturally consistent with this established pattern.

### Key Findings from Research

- **Real bottleneck**: HTTP round-trips (7 → 1), not DB query time. SQLite with 100 assets takes ~2–6ms for all 12–13 dashboard queries (estimate — not yet profiled; accepted risk, verify post-deploy via P95 latency monitoring).
- **Missing indexes**: `assets.family_id`, `assets.is_archived`, `liabilities.family_id`, `liabilities.is_active` — no B-tree indexes. Full table scans on every dashboard load. Low-risk to add.
- **Cache hit rate in practice**: The 60–90s TTL means the cache is almost always cold for a family app where users don't reload the dashboard every minute. Unverified assumption — accepted risk for a small-scale self-hosted app; simplification hygiene outweighs micro-optimization.
- **Date-sensitive staleness**: `get_expiring_soon_assets` and `get_trend` are date-dependent. Removing the TTL cache eliminates this staleness risk entirely — responses are always computed fresh from DB.
- **19 invalidation references**: 12 in `assets.py` (1 import + 11 calls), 5 in `liabilities.py` (1 import + 4 calls), 2 in `import_.py` (1 import + 1 call). Every future write endpoint must remember to add one. Maintenance liability eliminated by this refactor.
- **Nginx does not cache the bundle endpoint**: Confirmed — `frontend/nginx.conf` only caches static assets (30d); `nginx.production.conf` has no `proxy_cache` on `/api/`. Removing the in-memory cache leaves no Nginx-layer compensation, which is acceptable given the DB query time is negligible.
- **AssetSnapshot UniqueConstraint is sufficient**: `get_trend()` filters on `family_id + user_id=None + snapshot_date`. The `UniqueConstraint("family_id", "user_id", "snapshot_date")` covers this query pattern. No additional index needed for R-add-3.
- **Alembic pre-existing defect (blocks Unit 4)**: Three migration files share revision ID `a1b2c3d4e5f6`; migration chain has 3 active heads. Must be fixed before any new migration can be applied. See Unit 4a.

## Key Technical Decisions

- **Keep bundle endpoint, remove TTL cache**: The bundle endpoint solves the real problem (7 HTTP round-trips → 1). The TTL cache solves a problem that doesn't exist at this scale (DB query time is negligible). Removing the cache eliminates 16 call sites and the stale-read risk with no perceptible performance regression.

- **Add DB indexes as hygiene, not as cache replacement**: Composite indexes on `(family_id, is_archived)` and `(family_id, is_active)` are correct schema hygiene regardless of caching. They don't change perceived performance at 100 rows but future-proof the schema for larger datasets. They belong in a migration, not in model `__table_args__` (Alembic manages schema changes).

- **Remove `invalidate_dashboard_bundle` from `backend/app/services/cache/factory.py` entirely**: The function has no callers after this refactor. Leaving it as dead code would be misleading. Remove it along with the singleton and reset function. Note: `backend/app/db/factory.py` is a separate file (database backend selection) and must not be touched.

- **Do not add a longer TTL as a compromise**: A 5-minute TTL would have the same stale-read problem for date-sensitive data and the same maintenance liability for invalidation. If caching is revisited in the future, it should be a deliberate product decision with explicit staleness acceptance criteria — not a compromise TTL.

- **Verify `reset_dashboard_cache()` in conftest.py**: The test fixture likely calls this. Remove the call and the import when removing the function.

## Open Questions

### Resolved During Planning

- **Should the bundle endpoint be removed too?** No. The 7→1 request consolidation is a real, permanent win independent of caching. The bundle endpoint stays.
- **Should we add a longer TTL instead of removing the cache?** No. The user's feedback is that dynamic data shouldn't be cached. A longer TTL makes the staleness problem worse, not better. Remove the cache entirely.
- **Are the DB indexes a replacement for the cache?** No — they solve different problems. Indexes reduce query time (already fast at this scale). The cache reduced HTTP round-trips (solved by the bundle endpoint). Both are independent improvements; the indexes are hygiene, not a cache substitute.
- **Does `AssetSnapshot` need a new index?** Confirmed no. `get_trend()` filters on `family_id + user_id=None + snapshot_date`. The existing `UniqueConstraint("family_id", "user_id", "snapshot_date")` covers this query pattern in SQLite. R-add-3 is satisfied by the existing constraint — no new migration needed for snapshots.
- **Is the bundle endpoint covered by Nginx caching?** Confirmed no. `frontend/nginx.conf` only caches static assets; `nginx.production.conf` has no `proxy_cache` on `/api/`. Removing the in-memory cache leaves no Nginx-layer compensation — acceptable given DB query time is negligible.
- **Does `get_trend()` filter by `user_id`?** Confirmed yes — filters `user_id=None`. The UniqueConstraint on `(family_id, user_id, snapshot_date)` covers this. No additional index needed.
- **Cache hit rate and DB query time unverified?** Accepted risk. For a self-hosted single-family app, simplification hygiene outweighs micro-optimization. Add dashboard P95 latency monitoring post-deploy to catch any regression.
- **Alembic multi-head and duplicate revision IDs?** Pre-existing defect — must be fixed before Unit 4. See Unit 4a for the fix plan.
- **Exact call-site count in assets.py?** Confirmed 19 total references across 3 files: 12 in `assets.py` (1 import + 11 calls), 5 in `liabilities.py` (1 import + 4 calls), 2 in `import_.py` (1 import + 1 call).
- **`reset_dashboard_cache()` in `conftest.py`?** Confirmed absent — no edit to `conftest.py` needed.

### Deferred to Implementation

- **Whether `DashboardBundleResponse` schema was added**: If a `DashboardBundleResponse` Pydantic schema was added to `backend/app/schemas/dashboard.py`, it can stay (useful for OpenAPI docs) or be removed — implementer's call based on whether it's referenced anywhere.

## Implementation Units

```
Unit 1 (Remove cache from bundle endpoint)
  └── Unit 2 (Remove invalidation call sites — assets, liabilities, import)
        └── Unit 3 (Remove cache functions from factory.py)

Unit 4a (Fix Alembic defect — duplicate revision IDs + merge heads)  ← prerequisite for Unit 4b
  └── Unit 4b (Add DB indexes migration)
```

---

- [ ] **Unit 1: Remove TTL cache logic from bundle endpoint**

**Goal:** The bundle endpoint becomes a pure aggregation endpoint — calls 7 services, returns the combined response. No cache read, no cache write, no TTL.

**Requirements:** R-remove-1, R-keep-1, R-keep-2

**Dependencies:** None

**Files:**
- Modify: `backend/app/routers/dashboard.py`
- Test: `backend/tests/test_dashboard.py`

**Approach:**
- Remove the `cache = get_dashboard_cache()` call and the `cache_key` variable
- Remove the `cached = cache.get(cache_key)` check and early return
- Remove the `cache.set(...)` call at the end
- Remove the `import random` statement (no longer needed)
- Remove the `from app.services.cache.factory import get_dashboard_cache` import
- The bundle dict construction and `return JSONResponse(content=bundle)` stay unchanged
- The 7 service function calls stay unchanged

**Patterns to follow:**
- The other endpoint handlers in `dashboard.py` (e.g., `get_overview`, `get_allocation`) — they call the service and return directly, no cache logic

**Test scenarios:**
- Happy path: `GET /dashboard/bundle` returns 200 with all 7 keys (`overview`, `statesSummary`, `homeAssets`, `allocation`, `trend`, `lowUsageAssets`, `expiringSoon`)
- Happy path: Two consecutive requests both return fresh data (no stale cache)
- Happy path: After creating an asset, the next bundle request reflects the new asset (no invalidation needed — always fresh)
- Error path: Unauthenticated request returns 401
- Integration: `allocation` key contains `items` and `total` sub-fields

**Verification:**
- `uv run pytest tests/test_dashboard.py -v` passes
- No `import random` or `get_dashboard_cache` in `dashboard.py`
- Bundle endpoint returns correct data structure

---

- [ ] **Unit 2: Remove `invalidate_dashboard_bundle()` call sites from write endpoints**

**Goal:** Remove all 19 `invalidate_dashboard_bundle` references (imports + calls) from `assets.py`, `liabilities.py`, and `import_.py`.

**Requirements:** R-remove-2

**Dependencies:** Unit 1 (logically — the cache is already gone, so invalidation calls are now no-ops, but clean them up together)

**Files:**
- Modify: `backend/app/routers/assets.py`
- Modify: `backend/app/routers/liabilities.py`
- Modify: `backend/app/routers/import_.py`
- Test: `backend/tests/test_assets.py`
- Test: `backend/tests/test_liabilities.py`

**Approach:**
- In `assets.py`: remove `from app.services.cache.factory import invalidate_dashboard_bundle` import (1) + all 11 `invalidate_dashboard_bundle(user.family_id)` calls: `create_asset`, `update_asset`, `delete_asset`, `update_value`, `sell_asset`, `retire_asset`, `reactivate_asset`, `batch_archive_assets`, `batch_update_category`, `batch_update_tags`, `batch_update_status` = 12 references total
- In `liabilities.py`: remove import (1) + 4 call sites (`create_liability`, `update_liability`, `delete_liability`, `record_payment`) = 5 references total
- In `import_.py`: remove import (1) + 1 call site (after `db.commit()`) = 2 references total
- Do not touch `backend/app/services/cache/factory.py` yet — that's Unit 3

**Patterns to follow:**
- The existing write handlers in `assets.py` that call `invalidate_dashboard_bundle` — after removal, they should look like the handlers that only call `invalidate_dashboard_bundle` (i.e., just the service call and return)

**Test scenarios:**
- Happy path: `POST /assets/` creates an asset and returns 201 (no regression)
- Happy path: `PUT /assets/{id}` updates an asset and returns 200 (no regression)
- Happy path: `DELETE /assets/{id}` archives an asset and returns 200 (no regression)
- Happy path: `PUT /liabilities/{id}/payment` records payment and returns 200 (no regression)
- Integration: All existing `test_assets.py` and `test_liabilities.py` tests continue to pass

**Verification:**
- `uv run pytest tests/test_assets.py tests/test_liabilities.py -v` passes
- `grep -r "invalidate_dashboard_bundle" backend/app/routers/` returns no results

---

- [ ] **Unit 3: Remove cache functions from `factory.py` and clean up test fixtures**

**Goal:** Remove `_dashboard_cache`, `get_dashboard_cache()`, `reset_dashboard_cache()`, and `invalidate_dashboard_bundle()` from `factory.py`. Remove any `reset_dashboard_cache()` call from `conftest.py`.

**Requirements:** R-remove-3, R-remove-4

**Dependencies:** Unit 1, Unit 2 (no callers remain)

**Files:**
- Modify: `backend/app/services/cache/factory.py`
- Test: `backend/tests/test_dashboard.py`

**Approach:**
- Remove `_dashboard_cache: CacheBackend | None = None` global
- Remove `get_dashboard_cache()` function
- Remove `reset_dashboard_cache()` function
- Remove `invalidate_dashboard_bundle()` function
- The `get_rate_limit_cache()`, `get_captcha_payload_cache()`, `reset_rate_limit_cache()`, `reset_captcha_payload_cache()` functions are untouched
- Note: `conftest.py` does not reference `reset_dashboard_cache` — no edit needed there

**Patterns to follow:**
- The remaining `get_rate_limit_cache()` and `get_captcha_payload_cache()` functions — `factory.py` after this change should look like the file before the dashboard cache was added

**Test scenarios:**
- Happy path: `from app.services.cache.factory import get_rate_limit_cache` still works
- Happy path: `from app.services.cache.factory import get_captcha_payload_cache` still works
- Error path: `from app.services.cache.factory import get_dashboard_cache` raises `ImportError` (the function no longer exists)
- Integration: Full test suite passes — `uv run pytest tests/ -v`

**Verification:**
- `grep -r "dashboard_cache\|invalidate_dashboard_bundle" backend/` returns no results
- `uv run pytest tests/ -v` — all tests pass
- `factory.py` contains only rate limit and captcha cache functions

---

- [ ] **Unit 4a: Fix Alembic pre-existing defect — duplicate revision IDs + merge heads**

**Goal:** Resolve the duplicate `a1b2c3d4e5f6` revision ID collision and merge the 3 active heads into a single linear chain so `alembic upgrade head` works without error. This is a prerequisite for Unit 4b.

**Requirements:** prerequisite for R-add-1, R-add-2

**Dependencies:** None (independent of Units 1–3, but must complete before Unit 4b)

**Files:**
- Modify: `backend/alembic/versions/a1b2c3d4e5f6_add_performance_indexes.py` → rename revision to `perf_idx_001`
- Modify: `backend/alembic/versions/a1b2c3d4e5f6_expand_icon_field_length.py` → rename revision to `icon_len_001`
- Modify: `backend/alembic/versions/a1b2c3d4e5f6_add_security_audit_logs_table.py` → rename revision to `audit_log_001`
- Modify: downstream migration with `down_revision = 'a1b2c3d4e5f6'` pointing to the performance indexes chain → update to `perf_idx_001` (identified as `b2c3d4e5f6a7`)
- Modify: downstream migration with `down_revision` pointing to the audit logs chain → update to `audit_log_001` (identified as `c21c36dc5fbf`)
- Create: `backend/alembic/versions/<timestamp>_merge_heads.py` — merge migration unifying heads `f6a7b8c9d0e1` and `g7h8i9j0k1l2`

**Approach:**
- In each of the three colliding files, change only the `revision: str = 'a1b2c3d4e5f6'` line to its new unique ID; leave `down_revision`, `upgrade()`, and `downgrade()` untouched
- Update `b2c3d4e5f6a7`: change `down_revision = 'a1b2c3d4e5f6'` → `down_revision = 'perf_idx_001'`
- Update `c21c36dc5fbf`: change `down_revision = 'a1b2c3d4e5f6'` → `down_revision = 'audit_log_001'`
- Create merge migration: `down_revision = ('f6a7b8c9d0e1', 'g7h8i9j0k1l2')`, empty `upgrade()` and `downgrade()` bodies
- After edits, run `uv run alembic heads` — should show a single head

**Test scenarios:**
- `uv run alembic heads` returns exactly 1 head after the merge migration
- `uv run alembic upgrade head` completes without error on a fresh DB
- `uv run alembic downgrade -1` reverses cleanly
- `uv run alembic history --verbose` shows a linear chain with no duplicate revision IDs

**Verification:**
- `uv run alembic heads` → 1 result
- `uv run alembic upgrade head` → no errors
- `uv run pytest tests/ -v` — all tests pass (schema changes are additive)

---

- [ ] **Unit 4b: Add composite indexes on assets and liabilities tables**

**Goal:** Add missing B-tree indexes on the most-queried columns of `assets` and `liabilities` to future-proof the schema. Schema hygiene independent of the cache removal.

**Requirements:** R-add-1, R-add-2, R-add-3

**Dependencies:** Unit 4a (Alembic chain must be clean before adding a new migration)

**Files:**
- Create: `backend/alembic/versions/<timestamp>_add_asset_liability_indexes.py`
- Test: `backend/tests/test_assets.py` (existing tests verify queries still work after index addition)

**Approach:**
- Write the migration manually (autogenerate won't detect index additions on existing columns)
- `upgrade()`: add two indexes:
  - `ix_assets_family_id_is_archived` on `assets(family_id, is_archived)` — covers the most common dashboard filter
  - `ix_liabilities_family_id_is_active` on `liabilities(family_id, is_active)` — covers liability aggregation
  - `ix_assets_family_id_status` on `assets(family_id, status)` — covers `get_home_assets` and `get_states_summary` GROUP BY queries
- `downgrade()`: drop the three indexes
- Do NOT add `index=True` to the model columns — Alembic manages schema; adding `index=True` to the model without a migration creates the index on fresh installs but not on existing databases
- `AssetSnapshot`: the existing `UniqueConstraint("family_id", "user_id", "snapshot_date")` is confirmed sufficient for `get_trend()` — no new index needed

**Patterns to follow:**
- The renamed `perf_idx_001` migration (formerly `a1b2c3d4e5f6_add_performance_indexes.py`) — follow the same `op.create_index` / `op.drop_index` pattern

**Test scenarios:**
- Happy path: `uv run alembic upgrade head` applies the migration without error on a fresh DB
- Happy path: `uv run alembic downgrade -1` removes the indexes without error
- Integration: All existing `test_assets.py` and `test_dashboard.py` tests pass after migration (indexes are transparent to queries)
- No new behavioral tests needed — indexes are transparent to the ORM

**Verification:**
- Migration file exists in `backend/alembic/versions/`
- `uv run alembic upgrade head` succeeds
- `uv run pytest tests/ -v` — all tests pass

## System-Wide Impact

- **Interaction graph:** Removing `invalidate_dashboard_bundle` from write endpoints means those endpoints no longer touch the cache layer at all. The only remaining cache interactions are rate limiting (via `RateLimitMiddleware`) and captcha payload storage — both unaffected.
- **Error propagation:** No change. The bundle endpoint already propagates service errors as 500 (fail-fast, no partial caching). This behavior is preserved.
- **State lifecycle risks:** Removing the cache eliminates the stale-read risk for date-sensitive data (`get_expiring_soon_assets`, `get_trend`). Every request now reflects current DB state.
- **API surface parity:** No change to the API contract. The bundle endpoint URL, request format, and response structure are unchanged. Callers cannot observe the removal of the cache layer.
- **Integration coverage:** The bundle endpoint's correctness is now fully covered by the existing `test_dashboard.py` tests — no mock-based cache hit/miss tests needed.
- **Unchanged invariants:** The 7 individual dashboard endpoints (`/overview`, `/allocation`, etc.) remain unchanged. The frontend's individual `fetchOverview()`, `fetchAllocation()` etc. methods continue to work. The bundle endpoint response structure is unchanged.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Performance regression on dashboard load | Real bottleneck was HTTP round-trips (solved by bundle endpoint, unchanged). DB query time ~2–6ms is an estimate — accepted risk; add P95 latency monitoring post-deploy. Indexes in Unit 4b further reduce query time. |
| Missing an `invalidate_dashboard_bundle` reference | After Unit 2, verify with `grep -r "invalidate_dashboard_bundle" backend/` — confirmed 19 total references; should return zero after removal. |
| Alembic duplicate revision IDs block Unit 4b | Unit 4a fixes this first. After Unit 4a, `uv run alembic heads` must show exactly 1 head before proceeding. |
| Future write endpoints forgetting cache invalidation | Risk eliminated by removing the cache. No future endpoint needs to call `invalidate_dashboard_bundle`. |
| Alembic migration conflicts with existing schema | Indexes are additive — no column type or constraint changes. Low risk. Test with `alembic upgrade head` + `alembic downgrade -1`. |

## Documentation / Operational Notes

- The `docs/brainstorms/2026-04-17-performance-caching-requirements.md` requirements document described the full caching strategy. After this refactor, R1–R4 (in-memory cache) and R8 (bundle uses cache) are superseded. R5–R7 (bundle endpoint structure), R9–R10 (frontend), R11–R16 (HTTP cache headers) remain valid.
- No user-visible behavior changes. The dashboard loads the same data, just without the 60–90s staleness window.
- The bundle endpoint is now a pure aggregation endpoint. If future performance profiling shows DB query time is a bottleneck (e.g., at 10,000+ assets), caching can be revisited as a deliberate decision with explicit staleness acceptance criteria.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-17-performance-caching-requirements.md](docs/brainstorms/2026-04-17-performance-caching-requirements.md)
- **Previous plan:** [docs/plans/2026-04-17-003-feat-performance-caching-plan.md](docs/plans/2026-04-17-003-feat-performance-caching-plan.md)
- **Cache classification:** [docs/solutions/best-practices/redis-fail-fast-strategy.md](docs/solutions/best-practices/redis-fail-fast-strategy.md) — dashboard data is "performance-only / cache miss acceptable"
- **Batch endpoint pattern:** [docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md](docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md) — documented precedent for bundle/batch over cache
- Related code: `backend/app/routers/dashboard.py`, `backend/app/services/cache/factory.py`, `backend/app/routers/assets.py`, `backend/app/routers/liabilities.py`
