---
title: "feat: DeerFlow Production Enablement — USE_DEERFLOW=True Readiness Criteria"
type: feat
status: draft
date: 2026-04-11
parent: 2026-04-11-001-feat-agent-deerflow-upgrade-plan.md
---

# DeerFlow Production Enablement Plan

This document defines the conditions that must be met before setting
`USE_DEERFLOW=true` in any production environment. It resolves Open Decisions
4, 5, 6, and 7 from the DeerFlow upgrade plan.

---

## OD-4: USE_DEERFLOW Production Enablement Trigger

`USE_DEERFLOW` must remain `false` (default) until **all** of the following
gates are passed:

### Gate 1 — Shadow-mode audit review (7 days minimum)

Run with `USE_DEERFLOW=false` in production for at least 7 days after the
upgrade ships. Review `logs/agent-audit.log` daily for:

- Unexpected `error_type` values in the legacy path
- `fallback_used=true` entries that indicate legacy service instability
- Any `output_summary` entries containing unredacted PII patterns

**Pass criteria:** Zero PII leaks in audit log; legacy error rate < 1% over
the 7-day window.

### Gate 2 — DeerFlow staging validation (3 days minimum)

Enable `USE_DEERFLOW=true` in the staging environment. Monitor:

| Metric | Target |
|--------|--------|
| DeerFlow error rate (`deerflow_attempted=true, fallback_used=true`) | < 5% |
| p99 response latency | < 30 s |
| `fallback_used=true` rate (all causes) | < 10% |
| Zero cross-family data leakage | Required |

**Pass criteria:** All targets met over 3 consecutive days in staging.

### Gate 3 — Data lifecycle verification

Before production enablement, verify:

- [ ] `deerflow-memory.json` facts are scoped by `family_id` (no cross-family facts)
- [ ] Family deletion triggers purge of associated memory facts (see OD-6)
- [ ] `deerflow-checkpoints.db` TTL purge job is running (see OD-6)
- [ ] `agent_logs` Docker volume is mounted and persisting across restarts (see OD-7)

### Gate 4 — Rate limiting in place

Per-family rate limiting must be implemented before production enablement
(see OD-5 below). Without it, a single family can exhaust the AI API budget.

---

## OD-5: Rate Limiting

**Decision:** Implement per-family rate limiting in `PolicyGuard` or as
middleware in the `Orchestrator`.

### Specification

- **Limit:** 20 AI capability calls per family per hour (configurable via
  `AGENT_RATE_LIMIT_PER_FAMILY_PER_HOUR` env var, default: 20)
- **Scope:** Per `family_id`, not per `user_id` (family is the billing unit)
- **Storage:** In-memory `dict[family_id, deque[timestamp]]` with a sliding
  window. Acceptable for single-instance deployment; replace with Redis if
  horizontal scaling is needed.
- **Response on limit exceeded:** `PolicyDecision(allowed=False, reason="AI调用频率超限，请稍后重试")`
- **Audit:** Rate-limited calls must still produce an `AuditEntry` with
  `success=False, error_type="RateLimitExceeded"`

### Implementation unit (future plan)

Add to `agent/services/policy_guard.py`:

```python
from collections import deque
from datetime import datetime, timezone

_rate_windows: dict[str, deque] = {}
_RATE_LIMIT = int(os.getenv("AGENT_RATE_LIMIT_PER_FAMILY_PER_HOUR", "20"))

def _check_rate_limit(family_id: str) -> bool:
    now = datetime.now(timezone.utc).timestamp()
    window = _rate_windows.setdefault(family_id, deque())
    # Evict entries older than 1 hour
    while window and now - window[0] > 3600:
        window.popleft()
    if len(window) >= _RATE_LIMIT:
        return False
    window.append(now)
    return True
```

---

## OD-6: Data Subject Deletion

When a family is deleted from Numina, the following agent-side data must
also be purged:

### deerflow-memory.json

- Facts are stored as a JSON array. Each fact must include a `family_id` field.
- On family deletion, the backend must call a new agent endpoint:
  `DELETE /internal/family/{family_id}/data`
- The agent endpoint must: (1) filter and remove all facts with matching
  `family_id` from `deerflow-memory.json`, (2) return 204 on success.

### deerflow-checkpoints.db

- Checkpoint records are keyed by `thread_id`. Thread IDs in this system
  are set to `audit_id` (UUID per request), so they are not directly
  queryable by `family_id`.
- **TTL purge (required):** Add a scheduled job that deletes checkpoint
  records older than 30 days. Run daily at 03:00.
- **On-demand purge:** Not feasible without a `family_id → thread_id` index.
  Accept this limitation; TTL purge is sufficient for GDPR compliance given
  the 30-day window.

### Implementation unit (future plan)

```
agent/routers/internal.py  — DELETE /internal/family/{family_id}/data
agent/services/data_purge.py — purge_family_memory(), purge_old_checkpoints()
agent/scheduler.py — add daily checkpoint TTL purge job
```

---

## OD-7: Audit Log Volume Mount

**Decision:** Use a named Docker volume `agent_logs` mounted at `/app/logs`.

This is already implemented in `docker-compose.yml`:

```yaml
agent:
  volumes:
    - ./data:/app/data
    - agent_logs:/app/logs

volumes:
  agent_logs:
```

### Access control

- The `agent_logs` volume is accessible only to the `numina-agent` container
  by default (Docker named volume isolation).
- On the host, the volume data is stored under Docker's volume directory
  (typically `/var/lib/docker/volumes/numina_agent_logs/`), accessible only
  to root or the Docker daemon.
- **Log rotation:** `TimedRotatingFileHandler` rotates daily, retains 30 days.
  The volume must have sufficient disk space for 30 × (estimated daily log size).
  At 1 KB per audit entry and 1000 calls/day, this is ~30 MB — well within
  typical volume limits.
- **File permissions:** `logs/agent-audit.log` is created by the Python process
  running as the container user. Ensure the container does not run as root;
  use a non-root user in the Dockerfile (`USER 1000:1000`).

### Backup

Audit logs are operational data, not source-of-truth. They do not need to be
included in the primary database backup. If compliance requires log retention
beyond 30 days, configure a log shipping solution (e.g., Loki, CloudWatch,
or a cron job that archives rotated files to object storage).

---

## Summary Checklist

Before setting `USE_DEERFLOW=true` in production:

- [ ] OD-4 Gate 1: 7-day shadow-mode audit review passed
- [ ] OD-4 Gate 2: 3-day staging validation passed (error rate, latency, no leakage)
- [ ] OD-4 Gate 3: Data lifecycle verified (memory scoping, TTL purge, volume mount)
- [ ] OD-4 Gate 4: Rate limiting implemented and tested
- [ ] OD-5: `AGENT_RATE_LIMIT_PER_FAMILY_PER_HOUR` configured
- [ ] OD-6: Family deletion endpoint implemented and tested
- [ ] OD-6: Daily checkpoint TTL purge job scheduled
- [ ] OD-7: `agent_logs` volume confirmed persisting in production deployment
