# Enhanced Circuit Breaker for Multi-Provider AI

**Created:** 2026-05-20
**Status:** Draft
**Scope:** Standard — bounded enhancement to existing circuit breaker logic

---

## Problem Statement

Current AI provider selection has a basic circuit breaker:
- Opens after 5 failures, stays open 1 hour
- "Half-open" is implicit — when timeout expires, provider receives full traffic immediately
- No retry cascade to secondary providers on failure
- No distinction between permanent failures (auth errors) vs transient (rate limits)

This causes:
1. User sees errors when primary provider fails, even if secondary is healthy
2. Recovered providers get slammed with full traffic, risking immediate re-failure
3. Auth errors trigger retry that will never succeed

---

## Requirements

### 1. Cascade Retry on Failure

When a provider call fails, the agent must attempt the next provider in the family's priority list before returning an error to the user.

**Behavior:**
- Agent receives provider list sorted by `display_order` from `/internal/ai/config`
- Try primary provider first
- On failure, immediately try next provider (no same-provider retry)
- Continue until success or all providers exhausted
- All exhausted → return "AI 服务暂时不可用，请稍后重试" to user

**Constraints:**
- Only cascade on transient errors (429, 50x, timeout, network)
- Permanent errors (401/403) skip cascade and open circuit immediately

### 2. Error-Type-Aware Circuit Logic

Circuit breaker must distinguish between error types and apply appropriate recovery strategy.

**Error Classification:**

| Error Type | HTTP Codes | Circuit Action | Recovery |
|------------|-----------|----------------|----------|
| Permanent auth | 401, 403 | Open immediately, `permanent_auth` | Manual only |
| Permanent account | 410 (deleted), special response body patterns | Open immediately, `permanent_account` | Manual only |
| Transient rate limit | 429 | Open with schedule, `transient` | Half-open at scheduled times |
| Transient server | 500, 502, 503, 504 | Open with schedule, `transient` | Half-open at scheduled times |
| Transient timeout | timeout exception | Open with schedule, `transient` | Half-open at scheduled times |
| Transient network | connection errors | Open with schedule, `transient` | Half-open at scheduled times |

**Implementation note:** Error type must be passed from agent to backend when reporting circuit event. Current `report_circuit_event` only sends an error code; extend to include error type classification.

### 3. Three-State Circuit Model

Replace boolean `circuit_open` with explicit state enum.

**States:**
- `closed` — Provider healthy, accepts all traffic
- `open` — Provider blocked, no traffic allowed
- `half_open` — Provider testing recovery, accepts 10% of traffic

**Transitions:**
- `closed → open`: On failure (immediate for permanent, after threshold for transient)
- `open → half_open`: At scheduled recovery time OR after configurable timeout
- `half_open → closed`: After 5-minute window with ≥80% success rate
- `half_open → open`: On any failure during half-open

### 4. Per-Provider Recovery Schedule

Each provider can have a custom recovery schedule aligned with their quota reset times.

**Example:**
- DashScope: resets at :00 and :30 → schedule `":01,:31"` (try 1 minute after reset)
- Claude: no fixed schedule → schedule `null` (use default timeout)

**Implementation:**
- Add `recovery_schedule` field to `AIProviderConfig` (string, comma-separated time patterns)
- Backend checks current time against schedule to determine if provider should enter half-open
- If no schedule, use default behavior (open for 1 hour, then half-open)

### 5. Provider Status Dashboard

Family admins need visibility into provider circuit state and ability to manually reset.

**Visible in `/ai/config` response (enhanced):**
- `circuit_state`: `closed | open | half_open`
- `circuit_reason`: `null | transient | permanent_auth | permanent_account`
- `failure_count`: integer
- `last_failure_at`: datetime
- `last_failure_type`: string (e.g., `"429_rate_limit"`, `"401_invalid_key"`)
- `recovery_schedule`: string

**UI Requirements (frontend):**
- Show circuit state indicator on each provider card (green/yellow/red)
- For `permanent_*` circuits, show warning and "Reset Circuit" button
- For `transient` circuits, show expected recovery time

---

## Data Model Changes

### `AIProviderConfig` Model Extensions

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `circuit_state` | Enum | `closed` | Current circuit breaker state |
| `circuit_reason` | Enum/String | `null` | Why circuit opened |
| `recovery_schedule` | String | `null` | Time patterns for half-open transition (e.g., `":01,:31"`) |
| `last_failure_type` | String | `null` | Classified error type from last failure |
| `half_open_success_count` | Integer | `0` | Successes during half-open window |
| `half_open_failure_count` | Integer | `0` | Failures during half-open window |
| `half_open_window_start` | DateTime | `null` | When half-open window began |

**Migration note:** Replace `circuit_open` (boolean) with `circuit_state` (enum). Map existing `circuit_open=True` → `state=open`, `circuit_open=False` → `state=closed`.

---

## API Changes

### `/internal/ai/config` (Backend → Agent)

Enhanced provider response includes circuit metadata:

```json
{
  "providers": [
    {
      "config_id": "...",
      "circuit_state": "half_open",
      "circuit_reason": "transient",
      "recovery_schedule": ":01,:31",
      ...
    }
  ]
}
```

### `/internal/ai/config/{config_id}/circuit-event` (Agent → Backend)

Enhanced request body includes error type:

```json
{
  "error_code": 429,
  "error_type": "transient_rate_limit",
  "error_message": "Rate limit exceeded"
}
```

### `/api/v1/ai/config` (Frontend → Backend)

Enhanced response includes circuit state details for admin visibility.

---

## Success Criteria

1. Primary provider fails → secondary provider is tried within 100ms
2. Permanent auth error → circuit opens immediately, no cascade retry
3. 429 rate limit → circuit opens, enters half-open at scheduled time (:01 or :31)
4. Half-open provider with 80% success over 5 minutes → circuit closes
5. Admin can view circuit state and manually reset permanent failures
6. Existing tests pass after migration

---

## Dependencies

- Backend migration to convert `circuit_open` → `circuit_state`
- Agent orchestrator refactor to support cascade retry loop
- Frontend UI update for provider status display (minimal — existing card enhancement)

---

## Assumptions

1. Provider quota resets are predictable (DashScope at half-hour marks)
2. 10% traffic in half-open is sufficient to test recovery without risking re-failure
3. 5-minute window with 80% threshold balances recovery speed vs stability
4. Admins will check dashboard periodically; no automatic notifications needed

---

## Out of Scope

- Cross-family provider load balancing
- Automatic email/push notifications when all providers down
- Provider health monitoring beyond circuit breaker state
- Dynamic provider priority adjustment based on latency