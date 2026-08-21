---
title: Three-State Circuit Breaker with Cascade Retry for Multi-Provider AI
date: 2026-05-20
last_updated: 2026-08-19
category: architecture-patterns
module: ai-provider
problem_type: architecture_pattern
component: service_object
severity: high
applies_when:
  - Integrating with multiple external AI providers (OpenAI, Anthropic, DashScope)
  - Provider failures should cascade to secondary providers instead of returning errors
  - Rate-limited providers need gradual recovery instead of full-traffic slam
  - Permanent auth errors (401/403) and billing exhaustion (402) must be distinguished from transient failures (429/5xx)
  - Provider quota resets follow predictable time patterns (e.g., DashScope at :01/:31)
tags: [circuit-breaker, multi-provider, cascade-retry, half-open, rate-limiting, failover, resilience]
related_files:
  - server/apps/backend/app/routers/ai_internal.py
  - server/apps/backend/app/models/ai_provider_config.py
  - server/apps/agent/services/orchestrator.py
  - server/apps/agent/core/backend_client.py
  - server/apps/backend/app/routers/ai_config.py
references:
  - docs/brainstorms/circuit-breaker-enhancement-requirements.md
  - docs/plans/2026-05-20-001-feat-enhanced-circuit-breaker-multi-provider-ai-plan.md
  - docs/solutions/best-practices/redis-fail-fast-strategy.md
---

# Three-State Circuit Breaker with Cascade Retry for Multi-Provider AI

## Context

When a family configures multiple AI providers (e.g., primary DashScope + secondary OpenAI), the system needs to handle provider failures gracefully. The original two-state circuit breaker (`circuit_open: bool`) had three gaps:

1. **No cascade retry** — Provider failure returned error to user immediately, even if secondary providers were healthy
2. **Binary state model** — Circuit jumped directly from open to full traffic, risking immediate re-failure
3. **No error classification** — Auth errors (permanent) treated same as rate limits (transient), wasting retry attempts

## Guidance

### Three-State Model

Replace boolean `circuit_open` with a string `circuit_state` field using three states:

```
closed ──[5 transient failures]──> open ──[recovery schedule match]──> half_open ──[80% success in 5min]──> closed
                                     ^                                      │
                                     └──────[failure during half_open]───────┘
```

| State | Meaning | Traffic | Recovery |
|-------|---------|---------|----------|
| `closed` | Healthy | Full traffic | N/A |
| `open` | Failed | Zero traffic (excluded from provider list) | Automatic via recovery schedule |
| `half_open` | Testing recovery | 10% traffic (agent-side probabilistic routing) | 5-minute window, >=80% success rate closes circuit |

### Error Type Classification

Classify errors at the agent layer before reporting to backend:

```python
def classify_error_type(error_code: int, error_message: str | None = None) -> str:
    if error_code in (401, 403):
        return "permanent_auth"
    if error_code == 402:
        # Payment Required — provider account has no credit / quota exhausted.
        # Treat as permanent_account so the circuit opens immediately and
        # cascade retry moves to the next provider.
        return "permanent_account"
    if error_code == 410:
        return "permanent_account"
    if error_message and any(kw in error_message.lower() for kw in (
        "invalid key", "insufficient funds", "no credits",
        "payment required", "subscription expired",
    )):
        return "permanent_account"
    if error_code == 429:
        return "transient_rate_limit"
    if error_code in (500, 502, 503, 504):
        return "transient_server"
    if error_code == 0:
        return "transient_timeout"
    return "transient_network"
```

**Key rule:** Permanent errors open circuit immediately with no automatic recovery. Transient errors accumulate (threshold: 5) before opening.

### Cascade Retry Pattern

The agent orchestrator maintains a retry loop over the sorted provider list:

```python
attempted_config_ids: set[str] = set()
while attempt_count < max_attempts:
    attempted_config_ids.add(config_id)
    try:
        # dispatch to current provider
        async for chunk in adapter.stream_dispatch(...):
            yield chunk
        break  # success
    except Exception as e:
        error_type = classify_error_type(status_code, str(e))
        report_circuit_event(config_id, error_type=error_type)
        if error_type.startswith("permanent_"):
            break  # no cascade for permanent errors
        next_provider = select_next_provider(providers, attempted_config_ids)
        if next_provider:
            continue  # cascade to next
        else:
            yield "AI 服务暂时不可用，请稍后重试。"
            break
```

**Constraints:**
- Only cascade on transient errors (429, 5xx, timeout, network)
- Permanent errors (401/403) skip cascade and open circuit immediately
- Half-open providers get 10% traffic via probabilistic routing at the agent layer

### Recovery Schedule

Per-provider configurable time patterns aligned with provider quota resets:

```python
# Format: comma-separated minute patterns
recovery_schedule = ":01,:31"  # DashScope resets at :01 and :31

def _check_recovery_schedule_match(recovery_schedule: str, now: datetime) -> bool:
    current_minute = now.strftime("%M")
    for pattern in recovery_schedule.split(","):
        pattern = pattern.strip()
        if pattern.startswith(":") and current_minute == pattern[1:].zfill(2):
            return True
    return False
```

When the backend serves the provider list (`GET /internal/ai/config`), it checks if any open provider's recovery schedule matches the current time. If so, it transitions to `half_open` and includes the provider in the response.

### Half-Open Success Tracking

During the half-open window (5 minutes):
- Agent reports each call result via `POST /internal/ai/config/{id}/half-open-result`
- Backend tracks `half_open_success_count` and `half_open_failure_count`
- **Immediate re-open on failure** — any failure during half-open immediately re-opens the circuit
- At next `/ai/config` request after 5 minutes, backend calculates success rate:
  - >= 80% success → close circuit (full recovery)
  - < 80% success → re-open circuit

### Architecture Boundaries

```
┌─────────────────────────────────────────────────────────────────┐
│ Agent Microservice                                               │
│  ┌─────────────────┐    ┌──────────────────────────────────┐   │
│  │ BackendClient   │    │ Orchestrator                      │   │
│  │ - classify_error│    │ - cascade retry loop              │   │
│  │ - report_event  │    │ - 10% half-open routing           │   │
│  │ - report_result │    │ - fire-and-forget circuit reports  │   │
│  └────────┬────────┘    └──────────────────────────────────┘   │
│           │ HTTP                                                  │
└───────────┼──────────────────────────────────────────────────────┘
            │
┌───────────┼──────────────────────────────────────────────────────┐
│ Backend   │                                                       │
│  ┌────────▼────────┐    ┌──────────────────────────────────┐    │
│  │ ai_internal.py  │    │ ai_config.py (frontend API)       │    │
│  │ - circuit-event │    │ - reset-circuit (manual, owner)   │    │
│  │ - circuit-reset │    │ - recovery_schedule in CRUD       │    │
│  │ - half-open-res │    │ - circuit_state in response       │    │
│  │ - /ai/config    │    └──────────────────────────────────┘    │
│  │   (state trans) │                                             │
│  └─────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘
```

**Import direction constraint:** Agent cannot import from backend directly. All communication is via HTTP through `BackendClient`.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| `String(20)` for circuit_state, not SQLAlchemy Enum | Avoids migration pain when adding states; follows AIExtractionCircuit pattern |
| Agent-side probabilistic routing (10%) | Backend doesn't need to know about traffic percentages; agent decides locally |
| Fire-and-forget for circuit event reporting | Circuit reporting must never block the user-facing response path |
| Single `db.commit()` after provider list loop | Avoids N round-trips and partial state on exception |
| `error_type` required (not optional) | Prevents silent misclassification when old agents forget the field |
| 409 Conflict for wrong-state half-open results | Caller can distinguish "recorded" from "ignored" |
| Exact equality for recovery schedule matching | `endswith` would match `:1` against minute `01`, `11`, `21`, `31`, `41`, `51` |

## Anti-Patterns Avoided

1. **Silent fallback to mismatched provider** — Cascade retry returns None when no provider has the required capability, rather than degrading to a wrong-capability provider
2. **Multiple commits inside loops** — Coalesced to single commit to prevent partial state and reduce DB round-trips
3. **Implicit half-open via timeout expiry** — Explicit three-state model with tracked window start time and success rate calculation
4. **Same retry for all error types** — Permanent errors (auth) skip cascade entirely; only transient errors cascade

## Testing Strategy

20 integration tests covering:
- Error-type-aware circuit event handling (permanent vs transient)
- Three-state transitions (threshold, recovery schedule, window expiry)
- Half-open success/failure tracking with immediate re-open on failure
- Recovery schedule pattern matching (exact minute equality)
- Error classification function (HTTP codes + message keywords)
- Manual reset clears all circuit state fields

```bash
uv run pytest tests/backend/test_circuit_breaker_three_state.py -v
```
