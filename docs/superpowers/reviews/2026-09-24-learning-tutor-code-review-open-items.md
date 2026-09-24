---
date: 2026-09-24
module: agent, backend, frontend
problem_type: code-review-open-items
tags: [code-review, learning-tutor, deerflow, open-items]
---

# Code Review Open Items — feat/learning-tutor-deerflow-sse

Generated from multi-agent code review (2026-09-24). Items already fixed are not listed here.

## Structural / Open-Ended Issues (need discussion)

### #9 — worker.py at 2116 lines, 8 app runners with identical signatures

**Severity:** P1 (maintainability)
**File:** `server/apps/agent/services/runtime/worker.py`

**Problem:** Each new app (`numina`, `asset-report`, `import-parse`, `finance-coach`, `wish-advice`, `learning-tutor`) adds ~100 lines of identical boilerplate to worker.py. The file is now 2116 lines.

**Proposed resolution (for discussion):**
- Option A: Extract a `_run_app()` generic runner with a per-app config dict (skill_name, allowed-tools, result_event_type, etc.)
- Option B: Move each runner to its own module (`runners/asset_report.py`, etc.) with a registry pattern
- Option C: Keep current structure but extract common setup/teardown into a context manager

**Impact:** Reduces worker.py by ~400-600 lines. Makes adding new apps trivial. No behavioral change.

**Recommendation:** Defer to a dedicated refactor PR. Current structure works; the duplication is contained and each runner has slight variations.

---

### #10 — Duplicated trigger/heartbeat/lifecycle boilerplate across 4 routers

**Severity:** P1 (maintainability)
**Files:** `ai_report.py`, `ai_finance_coach.py`, `ai_literacy_report.py`, `learning_child.py`

**Problem:** Each router copy-pastes ~30-40 lines of `trigger_agent_run → lease_heartbeat → lifecycle_consumer → stream_with_cleanup` setup.

**Proposed resolution:**
- Extract a `trigger_and_stream()` helper in `bridge_consumer.py` that encapsulates the full lifecycle: trigger agent, start heartbeat, spawn lifecycle consumer, return SSE StreamingResponse.
- Each router calls `return await trigger_and_stream(task_id, family_id, agent_url, json_body, ...)`

**Impact:** Eliminates ~120 lines of duplication. Single point of change for lifecycle behavior.

**Recommendation:** Do in same PR as #9 or as a separate small refactor. Low risk, high maintainability payoff.

---

### #11 — ErrorCode learning values changed from snake_case to UPPER_SNAKE_CASE

**Severity:** P1 (breaking change)
**File:** `server/apps/backend/app/errors/codes.py:195`
**Status:** ✅ **Resolved (verified safe)** — Frontend uses `resolveErrorMsg(code)` which maps `errors.${code}` → i18n; both `zh-CN.json` and `en-US.json` locale files already use UPPER_SNAKE_CASE keys. Frontend TypeScript i18n does not contain separate learning error keys (it falls back to backend message). No external clients match raw strings. Change is safe.

---

### #15 — get_session_status O(n) scan

**Severity:** P2
**File:** `server/apps/backend/app/routers/learning_child.py:380`
**Status:** ✅ **Resolved** — Replaced O(n) Python scan with DB-level JSON path filter. Uses dialect-aware query: `json_extract` for SQLite, `->>` for PostgreSQL. Returns `.first()` instead of `.all()` + Python loop.

---

### #17 — event_persistence errors at DEBUG level

**Severity:** P2
**File:** `server/apps/backend/app/services/event_persistence.py:135`
**Status:** ✅ **Resolved** — Rate-limited logging: first 10 failures log at `logger.warning`, subsequent at `logger.debug`. Adds `_failure_count` module counter.

---

### #18 — run_id resolution polls 30s with no circuit breaker

**Severity:** P2
**File:** `server/apps/backend/app/services/bridge_consumer.py:212`
**Status:** ✅ **Resolved** — Reduced poll interval from 2s→1s and max attempts from 15→10. Total blocking time reduced from ~48s to ~15s. Frontend reconnection handles the shorter timeout gracefully.

---

### #28 — event_persistence init failure not in health checks

**Severity:** P2
**File:** `server/apps/backend/app/main.py:389`
**Status:** ✅ **Resolved** — Added `is_healthy()` and `health_detail()` to `event_persistence.py`. Health endpoint now includes `event_persistence` key in response when status is not ok (status + reason).

---

## Deferred (Low Priority)

| # | File | Issue | Notes |
|---|------|-------|-------|
| 29 | `bridge_consumer.py:30` | `trigger_agent_run` uses `agent_client: Any` | Type improvement, not urgent |
| 30-31 | `mcp_session.py`, `gateway.py` | Unrelated reformatting | Minor cleanup |
| 32 | `ai_chat.py:370` | SSE error payloads inconsistent | Cosmetic, low impact |

## Agent-Native Gaps (Future Work)

1. **record_learning_result is a workflow tool** — 180 lines, 7 state mutations. Consider splitting into primitives.
2. **Agent receives no child context** — inject child_name, topic_name, etc. in the synthetic trigger message.
3. **No get_today_assignments / get_learning_progress MCP tool** — add for action parity.
4. **No frontend resume button for failed sessions** — checkpoint infra is ready, UX is missing.
5. **Backend passes rich context but agent re-fetches via MCP** — optimize by injecting context in trigger.
