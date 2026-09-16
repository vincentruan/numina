---
artifact_contract: ce-unified-plan/v1
artifact_readiness: implementation-ready
execution: code
created: 2026-09-15
plan_type: refactor
product_contract_source: ce-plan-bootstrap
---

# refactor: Backend Domain Model Consolidation

## Summary

Six targeted refactoring items that emerged from domain modeling analysis. Each addresses a specific modeling weakness: duplicated circuit breaker fields (9 columns × 3 models), inconsistent soft-delete patterns (4 different approaches), misplaced child economy models causing domain-layer invariant violations, infrastructure leaks in the exchange rate service, JSON-in-Text columns without model-level serialization, and terminology ambiguities that create confusion for contributors.

## Problem Frame

The Numina backend has grown organically to 64+ ORM models, ~70 services, and 67 routers. Two distinct categories of modeling debt have accumulated:

**(A) Layering violations** — The `packages/domain/` layer has been forced to violate its own import rules because key models (ChoreInstance, CoinTransaction) live in the app layer. Meanwhile, infrastructure concerns (HTTP clients, mutable caches) leak into domain services.

**(B) Duplicated column patterns** — Cross-cutting modeling patterns (circuit breaker FSM fields, archive/soft-delete flags, JSON-in-Text serialization) were duplicated ad-hoc across models rather than extracted into reusable abstractions.

Additionally, terminology ambiguities (overloaded boolean fields, implicit polymorphic references, undocumented free-form strings) create confusion for contributors.

## Scope

### In Scope

1. Extract `CircuitBreakerMixin` for FSM-capable provider models
2. Extract `ArchivableMixin` and clean up soft-delete inconsistencies
3. Move child economy models to `packages/db/models/` and fix domain import violations
4. Split `exchange_rate` service into infrastructure adapter + pure domain service
5. Migrate JSON-in-Text columns to use model-level JSON serialization helpers
6. Resolve terminology ambiguities (Liability status, CoinTransaction ref_id, AIChatSession source)

### Out of Scope

- Merging the 6 per-family 1:1 config tables into a unified `FamilyConfig` (separate effort)
- Adding FK constraints to Activity/AssetLifecycleEvent/ChildWishCostHistory (P1-5, deferred per user request)
- Renaming Wish/ChildWish (documentation-only, no code change needed — the class names are already distinct)

---

## Key Technical Decisions

### KTD-1: Mixin placement in `packages/db/mixins/`

Both `CircuitBreakerMixin` and `ArchivableMixin` are ORM mixins that provide column definitions. They belong in `packages/db/` — the shared model package — not in `packages/domain/` (which is for services) or `apps/backend/` (which is app-specific). The existing `packages/db/CLAUDE.md` rule ("Base is the only approved ORM base class") is not violated because mixins compose into models via Python MRO, not inheritance from `DeclarativeBase`.

### KTD-2: Circuit breaker mixin targets 2 models + ASR upgrade, not AIExtractionCircuit

Research revealed that AIExtractionCircuit uses a completely different state vocabulary (`ok`/`rate_limited`/`circuit_open` vs `closed`/`open`/`half_open`), different column names (`state` vs `circuit_state`), and a different semantic model (audit-table-driven vs event-driven). Forcing it into the same mixin would create a leaky abstraction. ASR currently has a minimal 3-field subset and bypasses the FSM — we'll upgrade it to use the full mixin for consistency.

### KTD-3: ArchivableMixin uses `is_archived` (Boolean), parameterized server_default

The codebase already uses `is_archived` on Asset and Liability. `deleted_at` on CachedFile has tombstone/GC semantics different from archiving. `is_revoked` on DeviceSession is session lifecycle, not archiving. The mixin captures the `is_archived` pattern only. `server_default` is parameterized because Asset lacks it while Liability has it — the mixin uses Python-side `default=False` and individual models can override with `server_default` as needed.

### KTD-4: JSON-in-Text stays as Text columns, but gains model-level accessors

The project deliberately chose Text for SQLite+PG portability. SQLAlchemy's `JSON` type works on both dialects, but SQLite's JSON support is limited (no JSONB indexing, no `jsonb_set`). Rather than migrate column types (risky, requires `batch_alter_table`), we'll add `@hybrid_property` accessors that auto-serialize/deserialize, following the pattern already established by `DraftImport`. This gives us model-level encapsulation without changing the database schema.

### KTD-5: Liability gets a computed `status` property, not a new column

Adding a new `status` column requires a migration to backfill 100% of rows. Instead, we add a `@hybrid_property` that derives status from `is_active` + `is_archived`, and clean up the dead `is_archived` code path. This resolves the terminology ambiguity at the API/schema level without a data migration.

---

## Implementation Units

### U1. Extract CircuitBreakerMixin

**Goal:** Eliminate 7 duplicated FSM column definitions across AIProviderConfig and FamilyWebSearchProvider, and upgrade ASRProviderConfig to use the full FSM field set.

**Dependencies:** None

**Files:**
- `server/packages/db/mixins/__init__.py` (create)
- `server/packages/db/mixins/circuit_breaker.py` (create)
- `server/apps/backend/app/models/ai_provider_config.py` (modify — replace 7 inline columns with mixin)
- `server/apps/backend/app/models/family_web_search_provider.py` (modify — replace 7 inline columns with mixin)
- `server/apps/backend/app/models/asr_provider_config.py` (modify — replace 3 columns with mixin, add missing 4)
- `server/apps/backend/alembic/versions/<new>_add_asr_cb_fsm_fields.py` (create — adds 6 missing columns to ASR)
- `tests/packages/db/test_circuit_breaker_mixin.py` (create)

**Approach:**
1. Create `server/packages/db/mixins/` directory with `__init__.py`
2. Define `CircuitBreakerMixin` with 7 FSM columns + 2 tracking columns (`failure_count`, `last_failure_at`):
   - `circuit_state`: String(20), default="closed"
   - `circuit_reason`: String(30), nullable
   - `recovery_schedule`: String(100), nullable
   - `last_failure_type`: String(30), nullable
   - `half_open_success_count`: Integer, default=0
   - `half_open_failure_count`: Integer, default=0
   - `half_open_window_start`: UTCDateTime, nullable
   - `failure_count`: Integer, default=0
   - `last_failure_at`: UTCDateTime, nullable
3. Apply mixin to `AIProviderConfig` — remove 7 inline FSM column definitions, keep legacy fields (`circuit_open`, `circuit_open_until`) inline (they are AIProviderConfig-specific legacy, not part of the standard)
4. Apply mixin to `FamilyWebSearchProvider` — remove 9 inline CB column definitions
5. Apply mixin to `ASRProviderConfig` — remove 3 inline CB columns, mixin adds the 6 missing FSM fields
6. Write alembic migration: `ALTER TABLE asr_provider_configs ADD COLUMN` for 6 columns: `circuit_reason`, `recovery_schedule`, `last_failure_type`, `half_open_success_count`, `half_open_failure_count`, `half_open_window_start`
7. Verify `CircuitBreakerFSM` in `services/circuit_breaker/fsm.py` still works (it uses structural typing — mixin provides the same field names, so no change needed)

**Patterns to follow:**
- The existing CB field definitions in `ai_provider_config.py` and `family_web_search_provider.py` (copy exact types/defaults)
- `CircuitBreakerFSM` in `services/circuit_breaker/fsm.py` already uses structural typing — it accesses fields by name, so the mixin is drop-in compatible

**Test scenarios:**
- AIProviderConfig instance has all 9 mixin columns with correct defaults
- FamilyWebSearchProvider instance has all 9 mixin columns
- ASRProviderConfig instance has all 9 mixin columns (4 new via migration)
- `CircuitBreakerFSM.record_failure()` works on a model using the mixin
- `CircuitBreakerFSM.record_success()` transitions from half_open correctly
- Alembic migration applies and rolls back cleanly
- Existing CB adapter tests (64 tests) still pass without modification

**Verification:** Run `pytest tests/packages/db/test_circuit_breaker_mixin.py tests/backend/test_circuit_breaker_three_state.py` — new mixin tests pass AND all 20+ existing CB tests pass unchanged.

---

### U2. Extract ArchivableMixin

**Goal:** Unify the `is_archived` pattern under a single mixin with parameterized `server_default`, establishing a canonical soft-delete pattern for future models.

**Dependencies:** None (independent of U1)

**Files:**
- `server/packages/db/mixins/archivable.py` (create)
- `server/packages/db/mixins/__init__.py` (modify — export ArchivableMixin)
- `server/packages/db/models/asset.py` (modify — use mixin)
- `server/packages/db/models/liability.py` (modify — use mixin for `is_archived`)
- `tests/packages/db/test_archivable_mixin.py` (create)

**Approach:**
1. Define `ArchivableMixin` in `packages/db/mixins/archivable.py`:
   - `is_archived: Mapped[bool]` with `Boolean, default=False`
   - `server_default` is **parameterized** (not hardcoded) because Asset's existing column lacks `server_default` while Liability's has `server_default=text("false")`. The mixin accepts an optional class-level override or simply uses Python-side `default=False` only. Models that need `server_default` can add it explicitly after the mixin.
2. Apply to `Asset` — replace inline `is_archived` column definition with mixin. No schema change (Asset had no `server_default`, mixin doesn't force one).
3. Apply to `Liability` — replace inline `is_archived` column definition with mixin. Keep existing `server_default=text("false")` on Liability's class (overrides mixin default). Liability's `is_archived` is actively used in import rollback (`import_report.py:837,854`) — this is preserved, not removed.
4. No alembic migration needed — column definitions remain compatible.

**Test scenarios:**
- Asset model still has `is_archived` column via mixin with correct default (`False`)
- Liability model still has `is_archived` column via mixin with `server_default=text("false")`
- All 9+ `Asset.is_archived.is_(False)` query filters in dashboard service still work
- Liability queries filtering `is_active` still work
- `import_report.py` rollback logic using `Liability.is_archived` still works unchanged
- `test_draft_import.py:122-153` tests still pass

**Verification:** Run `pytest tests/backend/test_asset.py tests/backend/test_liability.py tests/backend/test_import_report.py tests/backend/test_draft_import.py` — all pass.

---

### U3. Move Child Economy Models to packages/db

**Goal:** Fix the `packages/domain/literacy/service.py` import violation by moving `ChoreInstance` and `CoinTransaction` (at minimum) to `packages/db/models/child_economy/`. Establish backward-compatible re-export shims.

**Dependencies:** None (independent of U1, U2)

**Files:**
- `server/packages/db/models/child_economy/__init__.py` (create)
- `server/packages/db/models/child_economy/chore.py` (create — move from apps)
- `server/packages/db/models/child_economy/coin_transaction.py` (create — move from apps)
- `server/packages/db/models/__init__.py` (modify — re-export new models)
- `server/apps/backend/app/models/chore.py` (modify — convert to re-export shim)
- `server/apps/backend/app/models/coin_transaction.py` (modify — convert to re-export shim)
- `server/packages/domain/literacy/service.py` (modify — fix imports to use packages.db path)
- `server/apps/backend/app/main.py` (verify — model registration still works)
- `tests/packages/db/models/test_child_economy_models.py` (create)

**Approach:**
1. Create `packages/db/models/child_economy/` directory structure (directory already exists as empty placeholder; add `__init__.py` and model files)
2. Move `chore.py` content (ChoreTemplate, ChoreInstance, M2M assignees table) to `packages/db/models/child_economy/chore.py`
3. Move `coin_transaction.py` content (CoinTransaction) to `packages/db/models/child_economy/coin_transaction.py`
4. Update imports in the moved files:
   - `from packages.db.session import Base` (already available)
   - `from packages.core.snowflake import next_id` (already available)
   - Any references to other backend models (User FK, etc.) need to use `packages.db.models` imports
5. Convert `apps/backend/app/models/chore.py` to a re-export shim: `from packages.db.models.child_economy.chore import *`
6. Convert `apps/backend/app/models/coin_transaction.py` to a re-export shim
7. Add re-exports to `packages/db/models/__init__.py`
8. Fix `packages/domain/literacy/service.py` lines 78, 106: change to `from packages.db.models.child_economy.chore import ChoreInstance` and `from packages.db.models.child_economy.coin_transaction import CoinTransaction`
9. Verify `alembic/env.py` picks up the models (it imports from `packages.db.models.__init__`)

**Patterns to follow:**
- Existing re-export shim pattern: `apps/backend/app/models/asset.py` → `packages/db/models/asset.py`
- Existing model registration in `packages/db/models/__init__.py`

**Test scenarios:**
- `from packages.db.models.child_economy import ChoreTemplate, ChoreInstance, CoinTransaction` works
- `from apps.backend.app.models.chore import ChoreTemplate, ChoreInstance` still works (backward compat via shim)
- `from packages.domain.literacy.service import LiteracyService` no longer triggers illegal import
- All existing backend tests that import from `apps.backend.app.models.chore` still pass
- `alembic check` shows no new pending migrations (tables haven't changed)
- `ChoreInstance` table name is still `chore_instances` (no rename)
- M2M `chore_template_assignees` association table still works

**Verification:** Run `pytest tests/packages/domain/test_literacy_service.py tests/backend/test_chores.py tests/backend/test_coins.py` — all pass.

**Scope note:** Only ChoreInstance and CoinTransaction move in this unit. The other 9 child economy models (ChildWish, BonusDraw, BlindBoxDraw, etc.) stay in `apps/backend/app/models/` — they have no domain-layer consumers and moving them is scope creep. A future consolidation can move them if needed.

---

### U4. Split Exchange Rate Service

**Goal:** Separate the HTTP client concern (infrastructure) from the rate conversion logic (domain). Remove the mutable class-level cache from the domain layer.

**Dependencies:** None

**Files:**
- `server/packages/core/exchange_rate_adapter.py` (create — HTTP fetching + caching)
- `server/packages/domain/exchange_rate/service.py` (modify — remove HTTP + cache, accept rates as parameters or use a protocol)
- `server/apps/backend/app/services/exchange_rate.py` (modify — wire adapter into service)
- `server/apps/scheduler_worker/jobs/__init__.py` (modify — use adapter for scheduled fetch)
- `tests/packages/domain/test_exchange_rate_service.py` (modify — test domain service without HTTP)
- `tests/packages/core/test_exchange_rate_adapter.py` (create)

**Approach:**
1. Create `ExchangeRateAdapter` in `packages/core/exchange_rate_adapter.py`:
   - `fetch_rates() -> dict[str, float]` — encapsulates the `httpx.get()` call to `api.exchangerate-api.com`
   - `_cache: dict` — in-memory 4-hour TTL cache (this is the right layer for caching)
   - `get_cached_rate(currency) -> Optional[float]` — read from cache without triggering HTTP fetch
   - `auto_create_missing_currencies(db, codes)` — side effect of creating Currency rows for unknown codes
   - Thread-safe: use a threading.Lock for cache access (current code has a race condition)
2. Modify `ExchangeRateService` in `packages/domain/exchange_rate/service.py`:
   - `get_rate(target_currency, db, adapter=None)` — reads from DB. When `adapter` is provided, delegates to `adapter.get_cached_rate()` first, falling back to DB on cache miss. This preserves the read-cache performance benefit while keeping HTTP concerns out of the domain layer.
   - `convert(amount, from_currency, to_currency, db, adapter=None)` — passes adapter through to `get_rate()`
   - Remove `fetch_and_store_rates()` from the domain service — this moves to the adapter
   - Remove `_cache` class variable from the domain service
3. Keep backward compatibility: `ExchangeRateService.fetch_and_store_rates(db)` remains as a thin wrapper that delegates to `adapter.fetch_and_store_rates(db)`. Mark as deprecated. Callers are not forced to change immediately.
4. New callers (e.g., `scheduler_worker`) use the adapter directly. Existing callers continue working through the wrapper until migrated.

**Patterns to follow:**
- The existing `packages/core/snowflake.py` pattern — infrastructure utility in core package
- The existing adapter pattern in `packages/domain/exchange_rate/` — just split the concerns

**Test scenarios:**
- `ExchangeRateAdapter.fetch_rates()` returns a dict of currency→rate (mock httpx)
- `ExchangeRateAdapter` cache returns cached rates within 4-hour TTL
- `ExchangeRateAdapter` cache refreshes after TTL expires
- `ExchangeRateService.convert()` works with adapter (cache hit → no DB query)
- `ExchangeRateService.convert()` works without adapter (DB-only fallback)
- `ExchangeRateService.get_rate()` returns (None, None) for unknown currency (no HTTP fallback)
- `ExchangeRateService.fetch_and_store_rates()` (deprecated wrapper) delegates to adapter correctly
- Existing backend tests still pass with updated import paths

**Verification:** Run `pytest tests/packages/domain/test_exchange_rate_service.py tests/backend/test_exchange_rate.py` — all pass.

---

### U5. JSON-in-Text: Add Model-Level Serialization Helpers

**Goal:** Eliminate scattered `json.loads`/`json.dumps` calls by adding `@hybrid_property` accessors that auto-serialize/deserialize JSON data stored in Text columns. No database schema changes.

**Dependencies:** None

**Files:**
- `server/packages/db/mixins/json_text.py` (create — reusable JSON-in-Text helper)
- `server/packages/db/mixins/__init__.py` (modify — export)
- `server/packages/db/models/asset.py` (modify — add `properties_json` accessor for `properties`)
- `server/packages/db/models/asset_snapshot.py` (modify — add `breakdown_json` accessor)
- `server/packages/db/models/user.py` (modify — add `webauthn_credentials_json` and `username_change_history_json` accessors)
- `server/packages/db/models/literacy_report.py` (modify — add `report_data` accessor for `report_json`)
- `server/packages/db/models/literacy_scenario.py` (modify — add accessors for `choices_json`, `content_json`, `feedback_json`)
- `server/packages/db/models/storage_backend.py` (modify — add `config_data` accessor)
- `server/apps/backend/app/models/draft_import.py` (modify — align existing helpers with mixin pattern)
- `server/apps/backend/app/models/sync_event.py` (modify — add `detail_data` accessor)
- Various service files (modify — replace `json.loads(model.field)` with `model.field_data`)
- `server/apps/backend/app/routers/auth.py` (modify — replace 6 `json.loads`/`json.dumps` on `webauthn_credentials` with accessor)
- `server/apps/backend/app/routers/literacy_child.py` (modify — replace `json.loads`/`json.dumps` on `content_json`/`feedback_json` with accessors)
- `tests/packages/db/test_json_text_mixin.py` (create)

**Approach:**
1. Create `JSONTextAccessor` utility in `packages/db/mixins/json_text.py`:
   - Not a mixin (since each model has different JSON fields), but a descriptor/hybrid_property factory
   - `json_field(column_name, property_name=None)` — returns a `@hybrid_property` that:
     - On read: `json.loads(getattr(self, column_name) or "null")`
     - On write: `setattr(self, column_name, json.dumps(value))`
     - Handles None/empty gracefully
2. Apply to each model:
   - `Asset.properties` → `Asset.properties_data` (returns dict/None)
   - `AssetSnapshot.breakdown` → `AssetSnapshot.breakdown_data`
   - `User.webauthn_credentials` → `User.webauthn_credentials_data`
   - `User.username_change_history` → `User.username_change_history_data`
   - `LiteracyWeeklyReport.report_json` → `LiteracyWeeklyReport.report_data`
   - `LiteracyScenarioTemplate.choices_json` → `LiteracyScenarioTemplate.choices_data`
   - `LiteracyScenario.content_json` → `LiteracyScenario.content_data`
   - `LiteracyScenario.feedback_json` → `LiteracyScenario.feedback_data`
   - `StorageBackend.config` → `StorageBackend.config_data`
   - `SyncEvent.detail` → `SyncEvent.detail_data`
3. Update service code to use the new accessors instead of manual `json.loads`/`json.dumps`
4. Keep the raw Text column accessible for backward compat — the accessor is additive, not replacing

**Patterns to follow:**
- `DraftImport.get_parsed_items()` / `set_parsed_items()` — the existing model-level JSON helper pattern
- SQLAlchemy `@hybrid_property` for transparent serialization

**Test scenarios:**
- `json_field("properties")` returns `None` when column is NULL
- `json_field("properties")` returns parsed dict when column has JSON string
- Setting `model.properties_data = {"key": "value"}` stores valid JSON in the Text column
- Setting `model.properties_data = None` stores NULL
- Empty string `""` is handled gracefully (returns None, not json error)
- Roundtrip: `obj.field_data = complex_dict; assert obj.field_data == complex_dict`
- `DraftImport` existing helpers still work unchanged

**Verification:** Run `pytest tests/packages/db/test_json_text_mixin.py` — all pass. Spot-check 2-3 service/router tests that use the new accessors. Confirm that the 10 identified model-column `json.loads`/`json.dumps` call sites now use accessors instead.

---

### U6. Resolve Terminology Ambiguities

**Goal:** Add explicit constraints and documentation for overloaded terms that confuse contributors. Three sub-items.

**Dependencies:** U2 (ArchivableMixin must be applied to Liability before status property is added)

**Files:**
- `server/packages/db/models/liability.py` (modify — add `@hybrid_property` for `status`)
- `server/packages/db/models/coin_transaction.py` (modify — add `ref_type` column or hybrid property)
- `server/apps/backend/app/models/ai_chat_session.py` (modify — add CheckConstraint or constants for `source`)
- `server/apps/backend/app/schemas/liability.py` (modify — add `status` to response)
- `server/apps/backend/alembic/versions/<new>_add_liability_status_and_coin_ref_type.py` (create)
- `tests/packages/db/test_liability_status.py` (create)
- `tests/packages/db/test_coin_transaction_ref_type.py` (create)

**Approach:**

**Sub-item 6a: Liability.status hybrid property**
1. Add a `@hybrid_property` `status` to Liability that derives from `is_active` + `is_archived`:
   - `is_active=True` → `"active"`
   - `is_active=False, is_archived=False` → `"paid_off"`
   - (If U2 removes `is_archived`): `is_active=False` → `"paid_off"`
2. Add `status` to `LiabilityResponse` schema (read-only, computed)
3. Optionally add a `status` expression for SQL-level filtering: `Liability.status == "active"` translates to `Liability.is_active == True`

**Sub-item 6b: CoinTransaction.ref_type**
1. Add a `@hybrid_property` `ref_type` that derives from `transaction_type`:
   - `chore_earn` → `"chore_instance"`
   - `wish_spend` → `"child_wish"`
   - `parent_grant`, `gift_sent`, `gift_received` → `None`
2. This is a read-only convenience accessor — no new column needed
3. Document the mapping in a comment on the model

**Sub-item 6c: AIChatSession.source constants**
1. Add a class-level constants block:
   ```python
   class SessionSource:
       SYSTEM_DEFAULT = "system_default"
       CHAT = "chat"
       REPORT = "report"
       COACH = "finance_coach"
   ```
2. Replace the magic string `"system_default"` in `ai_chat.py:438` with `SessionSource.SYSTEM_DEFAULT`
3. Add a comment documenting known values and their semantics

**Test scenarios:**
- `Liability(is_active=True).status == "active"`
- `Liability(is_active=False).status == "paid_off"`
- SQL filter: `query.filter(Liability.status == "active")` produces correct SQL
- `CoinTransaction(transaction_type="chore_earn", ref_id=123).ref_type == "chore_instance"`
- `CoinTransaction(transaction_type="parent_grant").ref_type is None`
- `SessionSource.SYSTEM_DEFAULT == "system_default"`
- No existing tests break from adding computed properties

**Verification:** Run `pytest tests/backend/test_liability.py tests/backend/test_coins.py tests/backend/test_ai_chat.py` — all pass.

---

## High-Level Technical Design

### Model Layer After Refactoring

```
packages/db/
├── session.py              # Base, UTCDateTime, SessionLocal
├── mixins/                 # NEW
│   ├── __init__.py         # exports all mixins
│   ├── circuit_breaker.py  # CircuitBreakerMixin (9 columns)
│   ├── archivable.py       # ArchivableMixin (is_archived)
│   └── json_text.py        # json_field() descriptor factory
├── models/
│   ├── __init__.py         # re-exports all models
│   ├── asset.py            # uses ArchivableMixin + json_field("properties")
│   ├── liability.py        # uses ArchivableMixin, status hybrid_property
│   ├── user.py             # json_field for webauthn_credentials, history
│   └── child_economy/      # NEW sub-package
│       ├── __init__.py
│       ├── chore.py        # MOVED from apps/backend
│       └── coin_transaction.py  # MOVED from apps/backend
│
packages/core/
├── exchange_rate_adapter.py  # NEW: HTTP + cache (infrastructure)
│
packages/domain/
├── exchange_rate/
│   └── service.py          # CLEANED: no HTTP; read-cache via adapter delegation
├── literacy/
│   └── service.py          # FIXED: imports from packages.db, not apps/
```

### Migration Dependency Graph

```
U1 (CB Mixin)  ──────────────────┐
U2 (Archive)   ──────────────────┤──→ U6 (Terminology, depends on U2)
U3 (Child Econ) ─────────────────┤
U4 (Exchange Rate) ──────────────┤  (no migration needed — pure code split)
U5 (JSON helpers) ───────────────┤  (no migration needed — no schema change)
                                  │
                                  ▼
                              Alembic migrations
                              (U1: ASR +6 CB columns, U2: add server_default to assets.is_archived)
```

---

## Verification Contract

### Pre-Implementation Baseline
- `pytest tests/` — all existing tests pass
- `alembic check` — no pending migrations

### Post-Implementation Gates
- `pytest tests/packages/db/` — new mixin tests pass
- `pytest tests/packages/domain/` — domain service tests pass (especially literacy import fix)
- `pytest tests/backend/` — all backend tests pass
- `alembic upgrade head` — new migrations apply cleanly
- `alembic downgrade -1` then `upgrade head` — roundtrip clean
- `grep -r "from apps.backend.app.models.chore" server/packages/` — returns no results (domain import violation fixed)
- `grep -r "json.loads" server/apps/backend/app/services/ server/apps/backend/app/routers/` — the ~10 model-column access sites now use model accessors instead of manual json calls

---

## Definition of Done

1. All 6 implementation units complete with tests
2. Alembic migrations created and verified (U1: ASR +6 CB columns)
3. No domain-layer import violations (`packages/domain/` does not import from `apps/`)
4. CircuitBreakerMixin applied to 3 models (AIProviderConfig, WebSearchProvider, ASRProviderConfig)
5. ArchivableMixin applied to Asset and Liability (parameterized server_default)
6. ChoreInstance + CoinTransaction in `packages/db/models/child_economy/`
7. ExchangeRateService has no HTTP concerns; read-cache preserved via adapter delegation
8. JSON-in-Text accessors on all 10 identified columns
9. Liability.status, CoinTransaction.ref_type, AIChatSession.source all have explicit semantics
10. All existing tests pass; new tests cover all new abstractions

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| ASR adapter doesn't actually use FSM fields after upgrade | Dead columns in ASR table | Keep fields nullable with defaults; they're unused until ASR adapter is upgraded to use FSM |
| Removing Liability.is_archived breaks import rollback | Import rollback can't mark liabilities as deleted | **Resolved:** Liability.is_archived is kept (Option B). ArchivableMixin applied to both Asset and Liability. |
| Moving models breaks alembic autogenerate | Missing table detections | Verify `alembic/env.py` imports from `packages/db/models/__init__.py` which re-exports all models |
| JSON accessor naming conflicts with existing properties | AttributeError on models | Use `_data` suffix consistently; check for name collisions before applying |
| Exchange rate adapter split changes call signatures | Callers break | Keep the old `ExchangeRateService.fetch_and_store_rates()` as a thin wrapper that delegates to the adapter, deprecate in next release |

---

## Sources & Research

- Domain modeling analysis (this session) — 3 explore agents + 4 research agents
- `docs/solutions/architecture-patterns/three-state-circuit-breaker-with-cascade-retry-2026-05-20.md` — existing CB pattern documentation
- `docs/solutions/best-practices/money-decimal-compute-str-wire-serialization.md` — migration pattern reference
- `server/packages/db/CLAUDE.md` — model conventions
- `server/apps/backend/CLAUDE.md` — backend conventions
