---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
product_contract_source: ce-brainstorm
execution: code
title: "Learning Source Taxonomy Fallback - Plan"
date: 2026-10-21
type: fix
topic: learning-source-taxonomy-fallback
---

## Goal Capsule

**Objective:** Add transparent fallback logic so children whose locale maps to a source taxonomy with no seeded data (e.g., zh-CN → `beijing`) automatically see `os-taxonomy` clusters and topics instead of an empty knowledge map — across all three learning routers (child, public, family).

**Product authority:** Backend learning service layer (`server/apps/backend/app/services/learning/topic_service.py`) and all three learning routers (`learning_child.py`, `learning.py`, `learning_family.py`). No frontend changes.

**Open blockers:** None.

---

## Product Contract

### Summary

Introduce a `get_effective_source_taxonomy(db, language)` helper that resolves the child's locale to a taxonomy, then checks whether that taxonomy has seeded data. If not, it falls back to `os-taxonomy`. All endpoints that currently call `locale_to_source_taxonomy()` directly switch to `get_effective_source_taxonomy(db, language)`. The fallback is transparent — when beijing data is eventually seeded, zh-CN children switch to it automatically with no code change.

### Problem Frame

`locale_to_source_taxonomy()` maps `zh-CN` → `'beijing'`, but the beijing taxonomy data files (`clusters.zh.json` etc.) are not yet available in the repo. The seed script supports `--source beijing`, but running it would fail with `FileNotFoundError`. As a result, zh-CN children see empty cluster maps and empty topic lists — every query filters on `source_taxonomy='beijing'` and finds zero rows.

en-US children are unaffected because their taxonomy (`os-taxonomy`) is fully seeded.

The problem spans three routers — child (`learning_child.py`), public (`learning.py`), and family (`learning_family.py`) — with 24 call sites total.

### Requirements

- R1. A new helper `get_effective_source_taxonomy(db, language) -> str` returns the taxonomy to actually use for a child's queries. It calls `locale_to_source_taxonomy(language)` first, then checks whether any `LearningTopic` rows exist for the mapped taxonomy. If none exist and the mapped taxonomy is not `os-taxonomy`, it returns `SOURCE_TAXONOMY_OS` (the constant `"os-taxonomy"` defined in `topic_service.py`) as fallback. Topics and clusters are always seeded together in the same transaction, so topic existence is a sufficient proxy for "this taxonomy has been seeded."
- R2. All endpoints in `learning_child.py`, `learning.py`, and `learning_family.py` that currently call `locale_to_source_taxonomy(child.language)` or `locale_to_source_taxonomy(user.language)` switch to `get_effective_source_taxonomy(db, language)`. The change is a drop-in replacement at each call site. The `db` session is already available at every call site via `Depends(get_db)`.
- R3. The fallback check is a single fast `EXISTS` or `LIMIT 1` query. No caching is needed at this scale — the query is sub-millisecond on any reasonable dataset.
- R4. `locale_to_source_taxonomy()` itself is unchanged. It remains the canonical locale-to-taxonomy mapping, used as the first step inside the new helper.
- R5. Tests cover three paths: (a) zh-CN with no beijing data → falls back to os-taxonomy, (b) zh-CN with beijing data present → uses beijing, (c) en-US → always uses os-taxonomy.

**Product Contract preservation:** R1, R3, R4, R5 unchanged. R2 expanded from `learning_child.py`-only to all three routers — the fallback logic applies to any endpoint that resolves taxonomy from locale, and the original scope was an under-scope of the same intent.

### Key Decisions

- KTD1. **Fallback at the service layer, not the data layer.** The fallback lives in a helper that wraps `locale_to_source_taxonomy()`, not in the query functions themselves. This keeps the fallback decision in one place and makes it testable in isolation. It also means the query functions (`list_clusters`, `list_topics`, etc.) remain taxonomy-agnostic — they filter on whatever taxonomy they receive.

- KTD2. **Fallback over remap.** Remapping `zh-CN` → `os-taxonomy` in `locale_to_source_taxonomy()` was considered and rejected. That approach loses the intent of locale-specific taxonomies and would need to be undone when beijing data arrives. The fallback approach preserves the mapping and activates/deactivates automatically based on data availability.

- KTD3. **No caching for the existence check.** A per-request `EXISTS` query is fast enough (sub-ms on indexed data). Caching introduces invalidation complexity (when beijing data is seeded, the cache must flip) that is not justified at this scale.

### Acceptance Examples

- AE1. zh-CN child, no beijing data seeded.
  - **Given:** `LearningTopic` rows exist only for `source_taxonomy='os-taxonomy'`
  - **When:** A zh-CN child calls `GET /child/learning/clusters`
  - **Then:** The response returns os-taxonomy clusters (not empty). The helper resolved to `os-taxonomy` via fallback.

- AE2. zh-CN child, beijing data seeded.
  - **Given:** `LearningTopic` rows exist for both `source_taxonomy='os-taxonomy'` and `source_taxonomy='beijing'`
  - **When:** A zh-CN child calls `GET /child/learning/clusters`
  - **Then:** The response returns beijing clusters. The helper resolved to `beijing` (no fallback needed).

- AE3. en-US child, any data state.
  - **Given:** Any combination of seeded data
  - **When:** An en-US child calls any learning endpoint
  - **Then:** The helper always returns `os-taxonomy` (the direct mapping, no fallback triggered).

### Scope Boundaries

- No seed script changes — the beijing seed path (`--source beijing`) is already correct and will work when data files become available.
- No frontend changes — the API contract is identical; the fallback is invisible to the client.
- No migration — this is a runtime logic change, not a schema change.
- No changes to `locale_to_source_taxonomy()` — it remains the canonical mapping.

### Sources

- Issue: `#138` — fix(learning): 知识地图 source_taxonomy 集群种子数据对齐
- Plan reference: `docs/plans/2026-10-20-001-feat-duolingo-cluster-knowledge-map-plan.md` — Risk 4 (BLOCKER)
- Seed script: `server/scripts/seed_learning_topics.py`
- Topic service: `server/apps/backend/app/services/learning/topic_service.py` — `locale_to_source_taxonomy()` at line 17
- Routers: `server/apps/backend/app/routers/learning_child.py` (8 call sites), `server/apps/backend/app/routers/learning.py` (7 call sites), `server/apps/backend/app/routers/learning_family.py` (8+ call sites)

---

## Implementation Units

### U1. Add `get_effective_source_taxonomy` helper

**Goal:** Create the fallback helper in `topic_service.py` that wraps `locale_to_source_taxonomy()` with a data-availability check.

**Requirements:** R1, R3, R4

**Dependencies:** None

**Files:**
- Modify: `server/apps/backend/app/services/learning/topic_service.py`
- Test: `server/tests/backend/test_learning_topic_service.py`

**Approach:**
1. Add `get_effective_source_taxonomy(db: Session, language: str | None) -> str` below `locale_to_source_taxonomy()` (around line 22)
2. Call `locale_to_source_taxonomy(language)` to get the mapped taxonomy
3. If mapped taxonomy equals `SOURCE_TAXONOMY_OS`, return it immediately (no check needed — os-taxonomy is the universal fallback)
4. Otherwise, run a single `db.query(LearningTopic.id).filter(LearningTopic.source_taxonomy == mapped).limit(1).first()` existence check
5. If a row exists, return the mapped taxonomy; otherwise return `SOURCE_TAXONOMY_OS`
6. Export `get_effective_source_taxonomy` for use by the routers

**Patterns to follow:** The `locale_to_source_taxonomy()` function pattern already in the same file. The `LearningTopic` model import already at the top of the file.

**Test scenarios:**
- zh-CN with no beijing LearningTopic rows → returns `"os-taxonomy"` (fallback triggered)
- zh-CN with at least one beijing LearningTopic row → returns `"beijing"` (no fallback)
- en-US with any data state → returns `"os-taxonomy"` (direct mapping, no check)
- None/unknown language → returns `"os-taxonomy"` (direct mapping)
- Existence check uses LIMIT 1 — verify only the helper function logic, not the query plan

**Verification:** Unit tests pass. `uv run pytest server/tests/backend/test_learning_topic_service.py -v`

---

### U2. Replace `locale_to_source_taxonomy` call sites in all three routers

**Goal:** Swap `locale_to_source_taxonomy(child.language)` / `locale_to_source_taxonomy(user.language)` for `get_effective_source_taxonomy(db, ...)` at all 24 call sites.

**Requirements:** R2

**Dependencies:** U1

**Files:**
- Modify: `server/apps/backend/app/routers/learning_child.py` (8 call sites)
- Modify: `server/apps/backend/app/routers/learning.py` (7 call sites)
- Modify: `server/apps/backend/app/routers/learning_family.py` (8+ call sites)

**Approach:**
1. In each router file, update the import from `topic_service` to include `get_effective_source_taxonomy` alongside `locale_to_source_taxonomy`
2. At each call site, replace:
   - `taxonomy = locale_to_source_taxonomy(child.language)` → `taxonomy = get_effective_source_taxonomy(db, child.language)`
   - `taxonomy = locale_to_source_taxonomy(user.language)` → `taxonomy = get_effective_source_taxonomy(db, user.language)`
   - `source_taxonomy = locale_to_source_taxonomy(user.language)` → `source_taxonomy = get_effective_source_taxonomy(db, user.language)`
3. The `db` parameter is already available at every call site via `Depends(get_db)` — no signature changes needed
4. In `learning.py`, some endpoints have an explicit `source_taxonomy` query param and only fall back to locale mapping when it is None. Replace only the fallback line: `source_taxonomy = locale_to_source_taxonomy(user.language)` → `source_taxonomy = get_effective_source_taxonomy(db, user.language)`

**Patterns to follow:** Existing `Depends(get_db)` injection pattern already in every endpoint. The import style already used in each file.

**Test expectation:** covered by U3 — API-level tests verify the behavior end-to-end.

**Verification:** Existing test suite passes (no behavior change when taxonomy data exists). `uv run pytest server/tests/backend/test_learning_locale_filter.py server/tests/backend/test_learning_cluster_api.py server/tests/backend/test_learning_topic_service.py -v`

---

### U3. Add fallback-specific tests

**Goal:** Verify the fallback behavior at both the unit and API levels.

**Requirements:** R5

**Dependencies:** U1, U2

**Files:**
- Test: `server/tests/backend/test_learning_topic_service.py` (unit tests for the helper — may overlap with U1's test scenarios)
- Test: `server/tests/backend/test_learning_locale_filter.py` (API-level fallback tests)

**Approach:**
1. **Unit tests** in `test_learning_topic_service.py`:
   - Import `get_effective_source_taxonomy`
   - Test the three paths from R5 with focused db fixtures (create or don't create beijing topics, assert the return value)
2. **API-level tests** in `test_learning_locale_filter.py`:
   - Add a test: zh-CN child, only os-taxonomy topics exist → clusters/map/today endpoints return os-taxonomy data (fallback triggered at API level). Covers AE1.
   - Verify existing tests still pass: they create beijing topics in fixtures, so the fallback is not triggered and behavior is unchanged. Covers AE2.
   - Verify en-US tests still pass: en-US maps directly to os-taxonomy, fallback never needed. Covers AE3.

**Test scenarios:**
- **Covers AE1.** zh-CN child, no beijing data. `GET /child/learning/clusters` returns os-taxonomy clusters. `GET /child/learning/map/index` returns os-taxonomy progress.
- **Covers AE2.** zh-CN child, beijing data present (existing fixture). `GET /child/learning/clusters` returns beijing clusters — unchanged behavior.
- **Covers AE3.** en-US child. `GET /child/learning/clusters` returns os-taxonomy regardless of beijing data presence.
- `get_effective_source_taxonomy(db, "zh-CN")` with empty beijing → returns `"os-taxonomy"`
- `get_effective_source_taxonomy(db, "zh-CN")` with beijing rows → returns `"beijing"`
- `get_effective_source_taxonomy(db, "en-US")` → always returns `"os-taxonomy"`

**Verification:** All new and existing tests pass. `uv run pytest server/tests/backend/test_learning_topic_service.py server/tests/backend/test_learning_locale_filter.py -v`

---

## Verification Contract

- **Unit tests:** `get_effective_source_taxonomy` returns correct taxonomy for all three paths (R5)
- **Existing tests pass:** The full `test_learning_*.py` suite passes without modification — existing tests create beijing data in fixtures, so the fallback is not triggered
- **Lint + typecheck:** `uv run ruff check` and `uv run mypy` clean on changed files
- **No behavior change when data exists:** The fallback only activates when the mapped taxonomy has zero `LearningTopic` rows

---

## Definition of Done

1. `get_effective_source_taxonomy(db, language)` exists in `topic_service.py` and is exported
2. All 24 call sites across 3 routers use `get_effective_source_taxonomy(db, ...)` instead of `locale_to_source_taxonomy(...)`
3. Unit tests cover the three fallback paths (R5)
4. API tests verify fallback at the endpoint level (AE1)
5. All existing learning tests pass unchanged
6. `ruff check` and `mypy` clean on changed files
7. `locale_to_source_taxonomy()` is unchanged
