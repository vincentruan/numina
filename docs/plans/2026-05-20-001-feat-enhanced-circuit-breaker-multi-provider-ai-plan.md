---
name: feat-enhanced-circuit-breaker-multi-provider-ai
type: feat
status: active
created: 2026-05-20
origin: docs/brainstorms/circuit-breaker-enhancement-requirements.md
---

# Enhanced Circuit Breaker for Multi-Provider AI

**Created:** 2026-05-20
**Status:** Active
**Origin:** `docs/brainstorms/circuit-breaker-enhancement-requirements.md`

---

## Summary

Enhance the AI provider circuit breaker from a simple two-state model to a full three-state circuit breaker with cascade retry, error-type-aware logic, per-provider recovery schedules, and enhanced provider status indicators on existing AIConfigPage.vue.

---

## Problem Frame

Current circuit breaker implementation has three gaps:

1. **No cascade retry** — Provider failure returns error to user immediately, even if secondary providers are healthy
2. **Two-state model** — `circuit_open: bool` jumps directly from open to full traffic, risking re-failure
3. **No error classification** — Auth errors (permanent) treated same as rate limits (transient), wasting retry attempts

User impact: Unnecessary errors when failover would succeed, and permanent-failure providers stay in retry loop.

---

## Scope Boundaries

### In Scope

- Cascade retry loop in agent orchestrator
- Three-state circuit model (`closed | open | half_open`)
- Error-type classification (permanent vs transient)
- Per-provider recovery schedule field
- Provider status display in existing AIConfigPage.vue
- Alembic migration for schema changes

### Deferred for Later

- Cross-family provider load balancing
- Automatic notifications when all providers down
- Provider health monitoring beyond circuit state
- Dynamic priority adjustment based on latency

### Deferred to Follow-Up Work

- Standalone admin dashboard page for provider circuits (enhancement to existing card display is in scope)
- Historical circuit event log for analytics

### Outside This Product's Identity

- Multi-tenant provider pooling
- Provider cost optimization algorithms

---

## Key Technical Decisions

1. **State field type: `String(20)`** — Follow existing pattern from `AIExtractionCircuit`, avoid SQLAlchemy Enum complexity. Valid values: `closed`, `open`, `half_open`.

2. **Half-open routing: Agent-side** — Backend returns `circuit_state` in provider metadata; agent makes probabilistic routing decision (10% chance to use half-open provider). Preserves request context for logging.

3. **Error classification: HTTP status + response body patterns** — 401/403 → `permanent_auth`; 410 or account-deleted message → `permanent_account`; 429/50x/timeout → `transient`.

4. **Recovery schedule format: Comma-separated time patterns** — String field like `":01,:31"` for DashScope quota resets. Backend checks current time against patterns to trigger half-open transition.

5. **Half-open success threshold: 5-minute window with ≥80% success** — Track successes/failures during window, close circuit when threshold met.

---

## System-Wide Impact

| System | Impact |
|--------|--------|
| Backend DB | New columns in `ai_provider_configs`, migration required |
| Backend API | Enhanced `/internal/ai/config` response, new `/circuit-event` schema |
| Agent Orchestrator | Cascade retry loop, half-open routing decision |
| Frontend | Enhanced provider card in AIConfigPage.vue, status badge colors |
| Tests | New unit tests for error classification, cascade retry scenarios |

---

## Implementation Units

### U1. Database Schema and Migration

**Goal:** Extend `AIProviderConfig` model with three-state circuit fields and recovery schedule.

**Requirements:** R-3 (Three-State Circuit Model), R-4 (Per-Provider Recovery Schedule)

**Dependencies:** None

**Files:**
- `server/apps/backend/app/models/ai_provider_config.py`
- `server/apps/backend/alembic/versions/YYYY-MM-DD-NNN_add_circuit_state_fields.py` (new migration)
- `server/apps/backend/app/schemas/ai_config.py`

**Approach:**
- Rename `circuit_open: bool` → `circuit_state: str` with values `closed | open | half_open`
- Add new fields: `circuit_reason`, `recovery_schedule`, `last_failure_type`, `half_open_success_count`, `half_open_failure_count`, `half_open_window_start`
- Migration maps existing `circuit_open=True` → `circuit_state='open'`, `circuit_open=False` → `circuit_state='closed'`
- Follow `String(20)` pattern from `AIExtractionCircuit` — no SQLAlchemy Enum

**Patterns to follow:**
- `server/apps/backend/app/models/ai_extraction_circuit.py` — existing three-state model
- `server/apps/backend/alembic/versions/s0158t32umn8_add_ai_extraction_audit_and_circuit.py` — migration pattern

**Test scenarios:**
- Migration converts existing boolean values correctly
- Model accepts valid state values, rejects invalid
- Default state is `closed`
- New fields nullable or have correct defaults

**Verification:** Run `alembic upgrade head` on test database, verify schema matches model.

---

### U2. Backend Internal API — Circuit Event Handling

**Goal:** Enhance `/internal/ai/config/{config_id}/circuit-event` to accept error type classification and update circuit state accordingly.

**Requirements:** R-2 (Error-Type-Aware Circuit Logic), R-3 (Three-State Circuit Model)

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/routers/ai_internal.py`
- `server/apps/backend/app/schemas/ai_config.py`

**Approach:**
- Extend `CircuitEventRequest` schema: add `error_type` field (`transient_rate_limit`, `transient_server`, `transient_timeout`, `transient_network`, `permanent_auth`, `permanent_account`)
- Modify `internal_circuit_event`:
  - Permanent errors → set `circuit_state='open'`, `circuit_reason='permanent_auth'/'permanent_account'`, no `circuit_open_until` (manual recovery only)
  - Transient errors → increment `failure_count`, set `circuit_state='open'` with `circuit_open_until` aligned to recovery schedule
- Update `internal_circuit_reset` to clear all new fields

**Patterns to follow:**
- Existing `internal_circuit_event` structure at lines 203-233
- `AIExtractionCircuit` service layer validation pattern

**Test scenarios:**
- Permanent auth error (401) → circuit opens immediately, no scheduled recovery
- Transient rate limit (429) → circuit opens with recovery schedule
- Transient failure count threshold → circuit opens with schedule
- Manual reset clears all circuit fields
- Invalid error type rejected

**Verification:** Unit tests pass for all error type classifications.

---

### U3. Backend Internal API — Provider List with Circuit Metadata

**Goal:** Enhance `/internal/ai/config` to return circuit state metadata and handle recovery schedule transitions.

**Requirements:** R-3 (Three-State Circuit Model), R-4 (Per-Provider Recovery Schedule)

**Dependencies:** U1, U2

**Files:**
- `server/apps/backend/app/routers/ai_internal.py`

**Approach:**
- Modify `internal_get_ai_config` (lines 131-187):
  - Check recovery schedule patterns against current time to trigger `open → half_open` transition
  - Return `circuit_state`, `circuit_reason`, `recovery_schedule` in provider response
  - Keep filtering `circuit_state='open'` providers (exclude from list)
  - Include `circuit_state='half_open'` providers — agent decides routing
- Add half-open window tracking: check if 5-minute window expired, calculate success rate, transition to `closed` if ≥80%

**Patterns to follow:**
- Existing half-open check at lines 157-166 (expand for schedule-based transition)

**Test scenarios:**
- Provider with matching recovery schedule time → transitions to half_open
- Provider in half_open for 5+ minutes with ≥80% success → transitions to closed
- Provider in half_open with failure → re-opens
- Provider list includes half_open providers with metadata
- Open providers excluded from list

**Verification:** Integration test with seeded circuit states verifies correct transitions.

---

### U4. Agent Backend Client — Circuit Reporting Methods

**Goal:** Extend `BackendClient` circuit reporting methods to pass error type classification.

**Requirements:** R-2 (Error-Type-Aware Circuit Logic)

**Dependencies:** U2

**Files:**
- `server/apps/agent/core/backend_client.py`

**Approach:**
- Extend `report_circuit_event()` to accept `error_type` and `error_message` parameters
- Add `classify_error_type()` helper: HTTP status → error type classification
- Keep fire-and-forget pattern for async calls
- `reset_circuit_success()` unchanged (only needs config_id)

**Patterns to follow:**
- Existing `_fire_and_forget()` pattern
- Existing `report_circuit_event()` structure

**Test scenarios:**
- 401 error → classified as `permanent_auth`
- 429 error → classified as `transient_rate_limit`
- 500 error → classified as `transient_server`
- Timeout exception → classified as `transient_timeout`
- Connection error → classified as `transient_network`

**Verification:** Unit tests for error classification helper, mocked backend calls verify payload.

---

### U5. Agent Orchestrator — Cascade Retry Loop

**Goal:** Implement cascade retry: on provider failure, try next provider in priority list before returning error to user.

**Requirements:** R-1 (Cascade Retry on Failure), R-2 (Error-Type-Aware Circuit Logic)

**Dependencies:** U3, U4

**Files:**
- `server/apps/agent/services/orchestrator.py`

**Approach:**
- Modify `stream_dispatch_events()`:
  - Receive full provider list from backend (sorted by `display_order`)
  - Try primary provider first
  - On exception, classify error type, report circuit event
  - If transient error → attempt next provider
  - If permanent error → skip cascade (open circuit immediately)
  - Track attempted providers to avoid retry loops
  - All providers exhausted → return error message to user
- Add half-open routing: for `half_open` providers, 10% chance to use (random check)

**Patterns to follow:**
- Existing DeerFlow dispatch at lines 356-418
- `_fire_and_forget()` for circuit event reporting

**Test scenarios:**
- Primary transient failure → secondary provider tried
- Primary permanent auth error → no cascade, circuit opens
- All providers fail → user sees error message
- Half-open provider selected with 10% probability
- Retry loop respects provider order from `display_order`

**Verification:** Integration test with mocked DeerFlow adapter simulates failures and verifies retry behavior.

---

### U6. Agent Orchestrator — Half-Open Success Tracking

**Goal:** Track successes/failures during half-open window and report to backend for circuit state transitions.

**Requirements:** R-3 (Three-State Circuit Model)

**Dependencies:** U3, U5

**Files:**
- `server/apps/agent/services/orchestrator.py`
- `server/apps/agent/core/backend_client.py`

**Approach:**
- On success with half-open provider → call backend to increment success count
- On failure with half-open provider → call backend to increment failure count (backend handles re-open logic)
- Backend calculates success rate at next `/internal/ai/config` call

**Patterns to follow:**
- Existing `reset_circuit_success()` fire-and-forget pattern

**Test scenarios:**
- Success in half-open → backend receives success increment
- Failure in half-open → backend receives failure increment, circuit re-opens
- 5-minute window with 80%+ success → circuit closes (verified at backend)

**Verification:** Integration test simulates half-open window with mixed results.

---

### U7. Backend API — Frontend Provider Status Endpoint

**Goal:** Enhance `/api/v1/ai/config` response to include circuit state details for admin visibility.

**Requirements:** R-5 (Provider Status Dashboard)

**Dependencies:** U1

**Files:**
- `server/apps/backend/app/routers/ai_config.py`
- `server/apps/backend/app/schemas/ai_config.py`

**Approach:**
- Extend `AIConfigResponse` schema with: `circuit_state`, `circuit_reason`, `last_failure_type`, `half_open_window_start`, `recovery_schedule`
- Return all circuit fields in `get_ai_configs` and `update_ai_config` responses
- Keep existing `reset_circuit` endpoint for manual recovery

**Patterns to follow:**
- Existing `_cfg_to_response()` helper at line 60

**Test scenarios:**
- Provider with open circuit → response includes `circuit_state='open'`, `circuit_reason='permanent_auth'`
- Provider with half_open → response includes window start time
- Admin can see all fields for status monitoring

**Verification:** API test verifies enhanced response schema.

---

### U8. Frontend — Provider Status Display

**Goal:** Show circuit state indicator on provider cards in AIConfigPage.vue with color coding and manual reset button for permanent failures.

**Requirements:** R-5 (Provider Status Dashboard)

**Dependencies:** U7

**Files:**
- `frontend/apps/main/src/api/ai.ts`
- `frontend/apps/main/src/pages/AIConfigPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`

**Approach:**
- Extend `ProviderConfig` TypeScript type with new circuit fields
- Add circuit state badge to provider card:
  - `closed` → green (hidden or subtle indicator)
  - `half_open` → yellow warning badge
  - `open` → red error badge with reason
- For `permanent_*` circuits: show warning message and "Reset Circuit" button (existing button, enhanced visibility)
- For `transient` circuits: show expected recovery time based on schedule
- Add i18n keys for circuit state labels

**Patterns to follow:**
- `ExtractionCircuitSection.vue` — existing circuit badge styling with `.state--rate_limited`, `.state--circuit_open`
- Emoji convention in `CLAUDE.md` for status indicators

**Test scenarios:**
- Provider with `circuit_state='closed'` → shows as healthy
- Provider with `circuit_state='half_open'` → yellow badge, shows recovery testing
- Provider with `circuit_state='open'` + `circuit_reason='permanent_auth'` → red badge, reset button visible
- Reset button clears circuit state → provider shows as healthy

**Verification:** Visual check in dev server, typecheck passes.

---

### U9. Integration Tests — Multi-Provider Failover

**Goal:** Verify cascade retry and circuit state transitions work end-to-end.

**Requirements:** Covers AE-1, AE-2, AE-3, AE-4 from origin document

**Dependencies:** U1-U6 complete

**Files:**
- `server/apps/agent/tests/integration/test_cascade_retry.py` (new)
- `server/apps/backend/tests/test_ai_circuit_state.py` (new)

**Approach:**
- Backend tests: circuit event handling, schedule-based transitions, half-open window success rate
- Agent tests: cascade retry loop, error classification, half-open routing probability
- Mock DeerFlow adapter to simulate failures/successes

**Patterns to follow:**
- Existing `test_router_circuit_shortcircuit.py` pattern
- Mock `backend_client` and `deerflow_adapter` fixtures from `conftest.py`

**Test scenarios:**
- Primary fails transiently → secondary succeeds → user sees response
- Primary fails permanently (401) → no cascade → circuit opens → user sees error
- 429 rate limit → circuit opens → recovery schedule triggers half_open → 10% traffic → success closes circuit
- All providers exhausted → user sees "AI 服务暂时不可用"
- Half-open provider with failure → circuit re-opens

**Verification:** All new tests pass, existing tests unchanged.

---

## Test File Inventory

| Unit | Test File |
|------|-----------|
| U1 | `server/apps/backend/tests/test_ai_provider_config_model.py` |
| U2 | `server/apps/backend/tests/test_ai_circuit_state.py` |
| U3 | `server/apps/backend/tests/test_ai_internal_circuit.py` |
| U4 | `server/apps/agent/tests/unit/test_backend_client_circuit.py` |
| U5-U6 | `server/apps/agent/tests/integration/test_cascade_retry.py` |
| U7 | `server/apps/backend/tests/test_ai_config_response.py` |
| U8 | `frontend/apps/main/src/api/ai.test.ts` (type tests) |
| U9 | Integration tests listed above |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Cascade retry increases latency | Cap retry attempts at provider count; fail fast if all exhausted |
| Half-open routing starvation | Ensure 10% probability gives enough traffic for recovery testing |
| Migration fails on existing data | Test migration on staging copy of production data first |
| Error classification misses edge cases | Document known error patterns; add fallback `transient` for unknown HTTP codes |
| Frontend type mismatch | Update TypeScript types before backend changes land |

---

## Verification Strategy

1. **Database migration** — Run on test DB, verify all existing `circuit_open` values converted correctly
2. **Backend circuit events** — Unit tests for each error type classification
3. **Agent cascade retry** — Integration test with mocked adapter, verify retry count and error handling
4. **Half-open probability** — Statistical test: 100 requests should hit half-open provider ~10 times
5. **Frontend display** — Visual verification in dev server, typecheck passes
6. **End-to-end** — Run existing AI chat tests, verify no regression

---

## Dependencies / Prerequisites

- Alembic migration must run before backend/agent code changes
- Frontend type changes can land before or with backend API changes
- No external service dependencies (all internal)

---

## Rollout Notes

1. Deploy migration first (zero downtime if backwards-compatible)
2. Deploy backend changes (enhanced internal API)
3. Deploy agent changes (cascade retry)
4. Deploy frontend changes (status display)
5. Monitor circuit state transitions in logs for first 24 hours
6. Verify recovery schedules align with provider quota resets (DashScope at :01/:31)

---

## Future Considerations

- Historical circuit event log for analytics (deferred to follow-up)
- Provider latency-based priority adjustment (out of scope)
- Cross-family provider pooling for enterprise (outside product identity)