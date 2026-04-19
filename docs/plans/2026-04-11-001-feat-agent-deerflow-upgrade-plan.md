---
title: "feat: Upgrade agent/ to DeerFlow Harness Architecture"
type: feat
status: completed
date: 2026-04-11
---

# feat: Upgrade agent/ to DeerFlow Harness Architecture

## Overview

Upgrade the existing `agent/` microservice from a collection of single-shot LLM call handlers into a structured DeerFlow-harness-style intelligent execution layer. The upgrade adds planning, skill dispatch, sub-task decomposition, structured output contracts, PII protection, policy enforcement, audit logging, and fallback mechanisms — while keeping the `backend -> agent` HTTP boundary completely stable.

DeerFlow (bytedance/deer-flow) is used exclusively as an internal runtime inside `agent/`. The frontend and backend never see DeerFlow internals.

## Problem Frame

The current `agent/` is a thin wrapper: each endpoint fetches data, builds a prompt, calls an LLM once, and returns text. This works for simple Q&A but cannot support:

- Multi-step reasoning or research decomposition
- Skill-based domain specialization
- Structured, stable output contracts for the frontend
- Streaming long-running analyses
- Persistent low-sensitivity memory (user preferences, tracking strategies)
- Graceful fallback when the LLM path fails

The goal is to evolve `agent/` into a "family finance brain" that can handle deep analysis requests while remaining a safe, auditable, policy-controlled internal service.

## Scope Boundaries

- Only `agent/` is modified. `backend/` and `frontend/` are not changed except for minor additions to the backend's internal AI config endpoint if needed.
- DeerFlow is NOT exposed as a public API. Its internal thread model, gateway, and router are never visible outside `agent/`.
- No new user-facing features are added in this plan — the upgrade is infrastructure for future capability expansion.
- The `backend -> agent` HTTP contract (7 agent endpoints, headers `X-Family-Id` + `X-Agent-Token`) remains stable throughout. (The backend exposes 8 AI-facing routes to the frontend, but the agent itself has 7 endpoints.)
- DeerFlow reference repo (`../deer-flow-reference/`) is cloned outside the numina repo and is never imported into production code paths.

## Requirements Trace

- R1. DeerFlow harness embedded inside `agent/` as an internal runtime, not exposed externally
- R2. Single adapter layer (`services/deerflow_adapter/`) is the only code that imports DeerFlow internals
- R3. All existing 8 agent endpoints continue to work after upgrade (backward compatibility)
- R4. PII redaction runs before any data reaches DeerFlow or the LLM
- R5. Policy guard enforces family admin capability switches before dispatching to DeerFlow
- R6. Every agent invocation produces a structured audit log entry
- R7. Fallback engine returns a rule-based or cached response when DeerFlow path fails
- R8. Output mapper transforms DeerFlow raw output into the stable domain schema before returning to backend
- R9. Custom skills for 4 family finance domains are defined as `SKILL.md` files
- R10. Feature flag `USE_DEERFLOW=true/false` allows instant rollback to legacy path
- R11. Unit tests, integration tests, and golden cases cover all new modules
- R12. Upgrade, rollback, and operations documentation is written

## Context & Research

### Relevant Code and Patterns

- `agent/core/llm.py` — current LLM client; becomes the fallback engine's LLM backend
- `agent/core/desensitize.py` — existing PII redaction; extended and promoted to `services/pii_redactor.py`
- `agent/core/backend_client.py` — data fetching from backend; preserved as-is
- `agent/services/health_report.py` — most complex existing service; becomes the reference for the `family-asset-checkup` skill
- `agent/routers/*.py` — all 7 routers preserved; routing logic unchanged, dispatch logic upgraded
- `backend/app/routers/ai_internal.py` — internal endpoints the agent calls; no changes needed
- `backend/app/auth/ai_deps.py` — `verify_agent_token` dependency; no changes needed

### Known Bugs to Fix During Upgrade

1. `health_report.py:87` references `remaining_amount_range_mid` but `desensitize_liabilities()` returns `remaining_amount_range` (string). Liability totals are always 0.
2. JSON extraction via `raw.find("{")` / `raw.rfind("}")` breaks when LLM wraps output in markdown fences.
3. LLM SDK clients instantiated per-call — no connection reuse.
4. `AGENT_INTERNAL_TOKEN` defaults to empty string — no startup validation.
5. `desensitize_assets()` defined but not called in disposal/aging services.

### Institutional Learnings

- Security: `AGENT_INTERNAL_TOKEN` must be validated at startup (fail-fast, same pattern as Redis cache backend doc)
- Security: Rate limiting per family using `CacheBackend` pattern (security-protection.md)
- Security: Structured security event logging to `logs/security.log` (security-audit.md)
- Cache: Never silently fall back from Redis to memory cache in multi-node deployments (redis-fail-fast-strategy.md)

### External References

- DeerFlow GitHub: https://github.com/bytedance/deer-flow
- DeerFlow docs: https://bytedance-deer-flow.mintlify.app
- DeerFlow Python requirement: 3.12+; no PyPI package; install via `pip install -e backend/packages/harness`
- `DeerFlowClient` is the in-process entry point — wraps `stream()` (sync generator) and `chat()` (returns string)
- Skills are `SKILL.md` files in `skills/custom/` — no Python code required for most domain skills
- Memory: `memory.json` facts injected into system prompt; CRUD via `DeerFlowClient` memory API

## Key Technical Decisions

- **DeerFlow as sidecar harness, not pip library**: Clone `deer-flow` alongside the project; install the harness package with `pip install -e ../deer-flow-reference/backend/packages/harness` pinned to a specific commit SHA. This avoids vendoring the entire repo while keeping the dependency auditable and upgradeable.

- **Single `DeerFlowClient` instance per agent process**: Instantiated once at FastAPI lifespan startup, shared across requests. `stream()` is sync — wrapped in `asyncio.run_in_executor` for async handlers.

- **Feature flag `USE_DEERFLOW`**: Environment variable (default `false` during migration, `true` in production after validation). When `false`, all routers use the existing legacy service path. When `true`, routers dispatch through the new orchestrator → adapter → DeerFlow path.

- **Output mapper is mandatory**: DeerFlow raw output (plain string or `StreamEvent` stream) is never returned directly. `output_mapper.py` transforms it into the stable `AgentResponse` domain schema.

- **PII redactor promoted to service**: `core/desensitize.py` logic is moved to `services/pii_redactor.py` with a unified `redact(context: FamilyContext) -> RedactedContext` interface. All data passes through this before reaching DeerFlow or the legacy LLM path.

- **Skills as SKILL.md files, not Python**: Domain skills (`family-asset-checkup`, `family-liability-review`, `fixed-asset-followup`, `family-finance-insight-planner`) are defined as structured Markdown files. This keeps them version-controlled, readable, and upgradeable without touching Python code.

- **Audit logger as middleware, not per-service**: A single `AuditLogger` class wraps every dispatch call. Services do not call it directly — the orchestrator calls it before and after dispatch.

- **Fallback engine**: When DeerFlow raises an exception or times out, `fallback_engine.py` runs the legacy single-shot LLM path (or returns a cached/rule-based response). The fallback is transparent to the caller.

## Open Questions

### Resolved During Planning

- **Should DeerFlow be a git submodule?** No. Submodules add operational complexity. Install the harness package from a local clone pinned to a commit SHA via pip editable install. The reference clone lives outside the numina repo.
- **Should the backend HTTP contract change?** No. All 8 existing endpoints keep their current request/response shapes. The upgrade is internal to `agent/`.
- **Should streaming be added to existing endpoints?** Not in this plan. Streaming is a future capability. The WebSocket report endpoint already exists in backend; its agent-side implementation can be upgraded later.
- **Which Python version for DeerFlow?** DeerFlow requires 3.12+. The current agent uses 3.13 — compatible.

### Deferred to Implementation

- Exact `config.yaml` structure for the DeerFlow instance (depends on reading the reference repo)
- Whether `DeerFlowClient` needs a custom checkpointer or the default SQLite one suffices
- Exact skill trigger phrases and `allowed-tools` list for each `SKILL.md`
- Whether `SubagentExecutor` should be enabled for deep research tasks (start disabled, enable per skill)
- Memory fact schema for family finance preferences (low-sensitivity only)

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
Request from backend
        │
        ▼
  Router (unchanged HTTP contract)
        │
        ▼
  PolicyGuard ──── admin switch off? ──► 403 / feature disabled response
        │
        ▼
  PIIRedactor (redact FamilyContext → RedactedContext)
        │
        ▼
  Orchestrator
        │
   USE_DEERFLOW?
   ┌────┴────┐
  yes       no
   │         │
   ▼         ▼
DeerFlow  LegacyService (existing services/*.py)
Adapter       │
   │          │
   ▼          │
OutputMapper ◄┘
        │
        ▼
  AuditLogger (log result summary)
        │
        ▼
  AgentResponse (stable domain schema)
        │
        ▼
  Router returns JSON to backend
```

**DeerFlow Adapter internals:**

```
DeerFlowAdapter.dispatch(skill_name, redacted_context)
  → build RunnableConfig (model, skill, plan_mode, subagent_enabled)
  → client.stream() in executor  ──► StreamEvent generator
  → collect events → raw_output string
  → on exception → raise DeerFlowError (caught by Orchestrator → Fallback)
```

**Output schema (stable contract):**

```
AgentResponse {
  capability: str          # which skill/endpoint produced this
  summary: str             # human-readable summary
  scorecards: list[Scorecard]
  risk_flags: list[RiskFlag]
  recommendations: list[Recommendation]
  followup_actions: list[Action]
  disclaimers: list[str]
  ui_blocks: list[UIBlock]
  needs_confirmation: list[ConfirmationItem]
  rule_based_findings: list[Finding]
  ai_inferences: list[Finding]
  fallback_used: bool
  audit_id: str
}
```

## Implementation Units

See part 2: `2026-04-11-001-feat-agent-deerflow-upgrade-plan-part2.md`

## System-Wide Impact

- **Interaction graph**: All 7 agent routers are affected. Backend AI routers (`ai_report.py`, `ai_chat.py`, etc.) are NOT changed. The APScheduler (`agent/scheduler.py`) calls service functions directly — when `USE_DEERFLOW=true` those calls route through Orchestrator, which has no HTTP request context; the scheduler must supply a synthetic `FamilyContext` with a timeout budget, or DeerFlow hangs will block the APScheduler thread indefinitely.
- **Error propagation**: DeerFlow errors are caught by `Orchestrator` → `FallbackEngine` → `AgentResponse(fallback_used=true)`. However, legacy service functions (e.g., `disposal_advisor.py`) raise exceptions on backend client failure rather than returning empty results. `FallbackEngine` must catch all exceptions from the legacy path and return a hardcoded safe `AgentResponse` as a final backstop — not re-raise.
- **State lifecycle risks**: DeerFlow SQLite checkpointer (`/app/data/deerflow-checkpoints.db`) and `memory.json` must be volume-mounted. If `USE_DEERFLOW` is toggled back to `false` after DeerFlow has written checkpoints, the legacy path ignores them. On re-enable, DeerFlow may resume from a stale checkpoint. Rollback procedure must include clearing or archiving these files.
- **Chat free-text PII**: `chat.py` passes user-typed free text directly to the LLM. Field-stripping redaction cannot sanitize free text. `PIIRedactor` must add a regex-based pass for the chat input path (phone numbers, ID card patterns, bank card patterns) before the question reaches DeerFlow or the legacy LLM.
- **memory.json content filter**: `max_facts` and `fact_confidence_threshold` are quantity/quality controls, not content controls. DeerFlow can extract and persist financial figures as facts if they appear in prompt context. A fact-type allowlist must be configured (behavioral preferences only; no monetary values, no identifiers). This must be enforced in `deerflow_config/prod/config.yaml`.
- **Decrypted API key in DeerFlow context**: `get_family_ai_config()` returns the decrypted API key. This key must never appear in any prompt string passed to DeerFlow. The `DeerFlowAdapter` must receive the key separately and inject it into the DeerFlow `RunnableConfig` model config — not embed it in the context string.
- **Concurrent stream() calls**: `run_in_executor(None, ...)` uses the default thread pool, which is unbounded. Under concurrent requests, each `stream()` call holds a thread for its full duration. A dedicated `ThreadPoolExecutor` with a bounded size (e.g., `max_workers=4`) must be used to cap concurrency.
- **SQLite checkpointer thread safety**: Multiple concurrent `run_in_executor` calls through a single `DeerFlowClient` instance write to the same SQLite DB. SQLite WAL mode handles concurrent reads but concurrent writes from multiple threads through one client are undefined. Either serialize DeerFlow calls with an asyncio semaphore or use one client instance per thread.
- **API surface parity**: The 8 existing agent endpoints keep their current JSON response shapes during migration. `AgentResponse` enrichment is additive and out of scope for this plan.
- **Unchanged invariants**: `backend -> agent` HTTP contract (endpoints, headers, auth) is explicitly frozen for this plan.
- **Audit log user_id gap**: The planned audit fields include `family_id` but not `user_id` (the specific member who triggered the call). Without `user_id`, member-level abuse cannot be attributed. Routers must pass `user_id` from the `X-Family-Id` header context to `AuditLogger`.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| DeerFlow 2.0 has no stable release tag — pinning to a commit SHA may miss security fixes | Pin to a specific SHA at plan time; document upgrade procedure in `docs/agent-upgrade-playbook.md` |
| `DeerFlowClient.stream()` is sync — blocks thread pool for full stream duration | Use a dedicated bounded `ThreadPoolExecutor(max_workers=4)`, not the default pool |
| SQLite checkpointer unsafe under concurrent threaded writes | Serialize DeerFlow calls with an asyncio semaphore (max 4) or use per-thread client instances |
| DeerFlow Python 3.12+ requirement — verify agent base image | Current agent Dockerfile uses `python:3.13-slim` — compatible; document explicitly |
| memory.json accumulates financial facts if no content filter | Add fact-type allowlist to `prod/config.yaml`; only behavioral preferences permitted |
| Decrypted API key must not appear in DeerFlow prompt context | Adapter injects key via `RunnableConfig`, never embeds in context string |
| Chat free-text bypasses field-stripping PII redaction | Add regex-based PII pass in `PIIRedactor` for free-text inputs |
| FallbackEngine legacy path can also raise exceptions | FallbackEngine must catch all exceptions and return a hardcoded safe `AgentResponse` |
| Rollback leaves stale DeerFlow checkpoints on disk | Rollback playbook must include checkpoint/memory archive or clear step |
| Scheduler has no request context for Orchestrator dispatch | Scheduler must supply synthetic `FamilyContext` + explicit timeout; document in ops manual |
| Feature flag `USE_DEERFLOW=false` means legacy bugs persist until flag is enabled | Fix the 5 known bugs (listed in Context) regardless of flag state |
| DeerFlow sandbox (`allow_host_bash`) could execute arbitrary code if misconfigured | Set `allow_host_bash: false` in `config.yaml`; document in security section of ops manual |

## Sources & References

- Related code: `agent/` (all files), `backend/app/routers/ai_*.py`, `backend/app/auth/ai_deps.py`
- Institutional docs: `docs/solutions/best-practices/security-protection.md`, `docs/solutions/best-practices/security-audit.md`, `docs/solutions/best-practices/redis-fail-fast-strategy.md`
- External: https://github.com/bytedance/deer-flow, https://bytedance-deer-flow.mintlify.app
- Prior plan: `docs/plans/2026-04-10-004-feat-ai-agent-module-plan.md`
