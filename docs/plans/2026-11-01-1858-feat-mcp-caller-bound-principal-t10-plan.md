---
title: MCP Caller-Bound Principal T10 Gap Closure - Plan
type: feat
date: 2026-11-01
topic: mcp-caller-bound-principal-t10
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

## Goal Capsule

- **Objective:** Close the four remaining gaps in MCP caller-bound principal enforcement so T10 acceptance criteria are fully met.
- **Authority:** Issue #170 (part of #168).
- **Open blockers:** None.

---

## Product Contract

### Summary

Close four gaps in the MCP caller-bound principal implementation: (1) wire persistent DB audit into the internal SSE path, (2) pass caller context through the guardrail provider instead of discarding it, (3) re-validate caller role on every tool call instead of caching for connection lifetime, and (4) add agent-path confused-deputy tests covering the full pipeline.

### Problem Frame

The MCP caller-bound principal pattern is largely implemented: `MCPSession` freezes `_family_id`, `_caller_user_id`, and `_caller_role` in `__slots__` at construction; SSE handshake validates the caller before session creation; `call_tool()` ignores identity from tool arguments and re-validates via `_get_caller_user()` per call; and the public path writes persistent audit entries via `_audit_callback`.

Four gaps remain:

1. The internal SSE path (`mcp_internal.py`) constructs `MCPSession` without an `audit_callback`, so tool calls only produce `logger.info/warning/error` entries with no persistent DB audit in `mcp_access_logs`.
2. `NuminaGuardrailProvider.check_tool_call()` discards `context` via `del context` (`numina_guardrail_provider.py:117`), preventing any future caller-aware guardrail rules.
3. `caller_role` is cached at SSE handshake for the connection lifetime (plan D7). If a user's role changes mid-session (owner transfer, deactivation), the stale role persists until disconnect.
4. Confused-deputy tests exist at the backend session/handshake layer but not for the full `stream_run → worker → MCP SSE → backend` pipeline.

### Key Decisions

- **D1. Re-validate role on every tool call.** `(session-settled: user-directed — chosen over periodic heartbeat re-validation and accepting current D7 design: fits the existing per-call defense-in-depth pattern; _get_caller_user() already opens a DB session per call, so re-reading role adds no new connection pattern.)` Governs R6, R7, R8.
- **D2. Same audit table, `token_id=NULL` for internal calls.** `(session-settled: user-directed — chosen over separate internal audit table: one table, one query path; anomaly detection and stats already work on mcp_access_logs.)` Governs R1, R2, R3.
- **D3. Guardrail context wiring is structural only — no new rules.** `(session-settled: user-directed — chosen over adding caller-aware rules or mirroring MCP role checks: MCP already does role-based filtering at the protocol layer; the guardrail runs in the agent process and would add overlapping checks.)` Governs R4, R5.
- **D4. Agent-path confused-deputy tests are unit-level, not full integration.** Tests cover ContextVar→header injection and args-isolation at the unit level. Full end-to-end integration tests (requiring both services running) are deferred — the unit-level coverage addresses the attack surface without the infrastructure cost. Governs R9, R10, R11.

### Requirements

**Audit persistence (Gap 1)**

- R1. The internal SSE path (`mcp_internal.py`) wires an `audit_callback` to `MCPSession` that calls `write_mcp_access_log()` on every tool call, covering success, `permission_denied`, and `service_error` outcomes.
- R2. Internal audit entries use `token_id=NULL` since no external token is involved.
- R3. Existing anomaly detection (`scan_mcp_anomalies()`) and stats (`get_mcp_stats()`) queries continue to work correctly with mixed token-based and NULL-token entries.

**Guardrail caller context (Gap 2)**

- R4. `NuminaGuardrailProvider.check_tool_call` receives `caller_user_id` and `caller_role` in the `context` parameter. The caller context flows from `RunContext` through the DeerFlow adapter into the guardrail middleware.
- R5. No new caller-aware guardrail rules are added. The `del context` / `del tool_args` lines are removed, and the values are available for future use.

**Role re-validation (Gap 3)**

- R6. `_get_caller_user()` re-reads `user.role` from the database on every `call_tool()` invocation and returns the current role alongside the user record.
- R7. If the user's role has changed since SSE connection time, the next `call_tool()` uses the fresh role for permission checks.
- R8. If the user has been deactivated (or deleted) since SSE connection time, the next `call_tool()` returns `permission_denied` rather than succeeding with the stale cached state.

**Confused-deputy tests (Gap 4)**

- R9. Tests verify that `_resolve_numina_mcp_servers()` injects `X-Caller-User-Id` from the `RunContext` ContextVar (not from tool arguments or message content) into MCP SSE connection headers.
- R10. Tests verify that injecting a fake `caller_user_id` or `family_id` in tool arguments does not override the session-bound identity — `call_tool()` reads from `self._caller_user_id`, not from args.
- R11. Tests verify that the SSE handshake rejects cross-family, inactive, and unknown callers with 403 in the agent-path context (ContextVar set, headers injected by `_resolve_numina_mcp_servers`).

### Key Flows

- F1. Tool call with role re-validation
  - **Trigger:** `call_tool(name, args)` is invoked on an existing `MCPSession`.
  - **Steps:** `call_tool` opens a DB session → calls `_get_caller_user(family_id, caller_user_id, db)` → `_get_caller_user` re-reads the user row including `role` → checks `is_active` and family membership → returns the current role → `call_tool` uses the fresh role for the permission check → proceeds or denies.
  - **Outcome:** Every tool call uses the current role. A deactivated user is denied on the very next tool call.
  - **Covered by:** R6, R7, R8

- F2. Internal MCP audit
  - **Trigger:** A tool call completes on the internal SSE path (agent→backend).
  - **Steps:** `MCPSession` invokes `_audit_callback` with `family_id`, `caller_user_id`, `caller_role`, `tool_name`, `status`, `args` → callback calls `write_mcp_access_log(family_id=..., token_id=None, session_id=..., event_type="tool_call", ...)` → row written to `mcp_access_logs`.
  - **Outcome:** Every internal tool call has a persistent DB audit entry, queryable by the same anomaly detection and stats code as the public path.
  - **Covered by:** R1, R2, R3

### Acceptance Examples

- AE1. Role change mid-session
  - **Covers R7.**
  - **Given:** An active `member` has an open SSE connection. An admin transfers ownership, changing the user's role to `owner`.
  - **When:** The user's next `call_tool()` runs.
  - **Then:** `_get_caller_user()` re-reads the row, returns `role="owner"`, and the tool call proceeds with `owner` permissions — not the stale `member` role.

- AE2. User deactivated mid-session
  - **Covers R8.**
  - **Given:** An active `member` has an open SSE connection. An admin deactivates the user.
  - **When:** The user's next `call_tool()` runs.
  - **Then:** `_get_caller_user()` finds `is_active=False` → raises `RuntimeError("caller invalid")` → `call_tool()` returns `{"error": "permission_denied", "retryable": false}`.

- AE3. Confused-deputy args injection
  - **Covers R10.**
  - **Given:** An `MCPSession` bound to `caller_user_id="user-A"`, `family_id="fam-1"`.
  - **When:** Tool arguments contain `{"caller_user_id": "user-B", "family_id": "fam-2"}` (simulating an LLM output trying to escalate).
  - **Then:** `call_tool()` ignores the injected values. The tool runs as `user-A` in `fam-1`. Audit log records `caller_user_id="user-A"`.

### Scope Boundaries

- **No new caller-aware guardrail rules.** Adding rules like "child can never call write tools at the guardrail layer" is deferred to a future task. This brainstorm closes the structural gap (context availability), not the policy gap.
- **No periodic heartbeat re-validation.** Per-call re-validation subsumes this. A separate timer would add complexity without additional security.
- **Public SSE audit path unchanged.** The public path already has persistent audit via `_audit_callback`. The only change to the public path is adding `audit_callback` invocations on the `permission_denied` early-return paths (which were previously unaudited) — done as part of U1 step 4.
- **`MCPAccessLog` lacks `caller_user_id` column.** Internal audit entries with `token_id=NULL` identify the family (`family_id`) but not the individual caller. This is an accepted limitation — the agent dispatch path already knows the user from the JWT, and family-level audit is sufficient for anomaly detection. Adding a `caller_user_id` column is deferred to a future task if per-user forensic audit is needed.
- **`list_tools()` keeps cached role.** After U3, `call_tool()` uses the fresh `user.role` from DB but `list_tools()` continues using `self._caller_role` (cached at SSE handshake). This is an acceptable asymmetry — `call_tool()` is the security boundary, and `list_tools()` is an advertisement. After a mid-session role change, the LLM may see a stale tool catalogue until SSE reconnect, causing unnecessary `permission_denied` round-trips for tools that the fresh role would allow. This is benign.
- **D7 plan document update.** The existing plan doc at `docs/plans/2026-05-31-001-feat-mcp-caller-bound-principal-plan.md` states D7 as `caller_role lifetime = SSE connection`. This decision is superseded by D1 in this document. The plan doc should be updated to reflect the new per-call re-validation decision.

### Dependencies / Assumptions

- `_get_caller_user()` already opens a DB session per call — re-reading `role` adds no new connection pattern.
- `write_mcp_access_log()` already accepts `token_id` as a nullable field (or can be made nullable with a migration if it isn't already).
- `scan_mcp_anomalies()` and `get_mcp_stats()` do not filter on `token_id` — NULL entries are included naturally.
- `RunContext` already carries `caller_user_id` as a ContextVar — the guardrail wiring reads from this existing facade.

### Sources / Research

- `server/apps/backend/app/services/mcp_session.py` — `MCPSession` class, `__slots__`, `_get_caller_user()`, `call_tool()` audit paths.
- `server/apps/backend/app/routers/mcp_internal.py:135-141` — internal SSE `MCPSession` construction without `audit_callback`.
- `server/apps/backend/app/routers/mcp_public.py:248-273` — public SSE construction with `audit_callback` (reference implementation).
- `server/apps/backend/app/services/mcp_audit.py` — `write_mcp_access_log()` and redaction logic.
- `server/apps/agent/services/deerflow_adapter/numina_guardrail_provider.py:98-139` — `check_tool_call()` with `del context`.
- `server/apps/agent/services/runtime/run_context.py:32-67` — `RunContext` facade with `caller_user_id`.
- `server/apps/agent/services/runtime/run_pipeline.py:1032-1087` — `_resolve_numina_mcp_servers()` header injection.
- `server/tests/backend/unit/test_mcp_session_caller_binding.py` — 10 existing caller-binding tests.
- `server/tests/backend/unit/test_mcp_sse_caller_handshake.py` — 8 existing handshake tests.
- `docs/solutions/architecture-patterns/mcp-caller-bound-principal-2026-05-31.md` — 8 hard invariants.
- `docs/plans/2026-05-31-001-feat-mcp-caller-bound-principal-plan.md` — D7 decision (being superseded).

---

## Planning Contract

Product Contract unchanged.

### Key Technical Decisions

- KTD1. **Restructure `call_tool()` flow for role re-validation.** The current flow checks `self._caller_role` (line 329) before opening the DB session (line 388). Re-validation requires the fresh role from DB, so the DB read must move before the role check. The permission_denied response format stays identical — only the data source for the role changes from `self._caller_role` to `user.role`. Governs R6, R7, R8.

- KTD2. **Internal audit callback follows the public path's closure pattern.** `mcp_internal.py` creates a closure (like `mcp_public.py:_audit_tool_call`) that captures `client_ip="internal"` and calls `write_mcp_access_log()` with `token_id=None`. No new function or abstraction — mirrors the existing pattern exactly. Governs R1, R2.

- KTD3. **Guardrail context is pass-through, not transformed.** Remove `del context` and `del tool_args` from `check_tool_call`. Do not add new context fields, transformation logic, or caller-aware rules. The guardrail becomes context-aware at the data level; policy use is deferred. Governs R4, R5.

- KTD4. **Tests extend existing test files.** Confused-deputy tests for the agent path go into `tests/agent/unit/` (not `tests/backend/`), extending the existing caller-binding test patterns. No new integration test file — the attack surface is covered by unit tests on `_resolve_numina_mcp_servers()` header injection and `MCPSession` args-isolation. Governs R9, R10, R11.

### Assumptions

- `write_mcp_access_log()` already accepts `token_id: int | None = None` — verified at `mcp_audit.py:76`. No migration needed.
- `scan_mcp_anomalies()` and `get_mcp_stats()` do not filter on `token_id` — NULL entries are included naturally in aggregate queries.
- DeerFlow's `GuardrailMiddleware` already passes a `context` dict to `check_tool_call` — the provider just discards it. Removing the discard is sufficient.
- `_get_caller_user()` returning the user with a fresh `role` attribute is backward-compatible — the `User` ORM object always carries `role`.

---

## Implementation Units

### U1. Wire internal SSE audit callback

- **Goal:** Agent-initiated MCP tool calls (internal SSE path) produce persistent DB audit entries in `mcp_access_logs`, matching the public path's audit coverage.
- **Requirements:** R1, R2, R3
- **Dependencies:** None
- **Files:**
  - `server/apps/backend/app/routers/mcp_internal.py` — add `_audit_tool_call` closure and pass as `audit_callback`
  - `server/tests/backend/unit/test_mcp_internal_audit.py` — new test file
- **Approach:**
  1. In `mcp_internal.py:mcp_sse()`, after caller validation succeeds and before `MCPSession` construction, create an `_audit_tool_call` closure following the public path pattern (`mcp_public.py:248-264`). Use `client_ip="internal"` (no HTTP request client for agent-to-backend calls), `user_agent=None`, and `token_id=None`.
  2. Pass `audit_callback=_audit_tool_call` to `MCPSession()` constructor (currently omitted at line 135-141).
  3. The closure calls `write_mcp_access_log(family_id=int(family_id), token_id=None, event_type=..., tool_name=..., status=..., duration_ms=..., client_ip="internal", args_digest=..., error_code=...)`.
  4. In `mcp_session.py:call_tool()`, invoke `self._audit_callback` before each `permission_denied` early return (currently at lines ~347 and ~374) with `event_type="tool_call"`, `status="permission_denied"`, the appropriate `error_code` (`"role_not_allowed"` or `"not_in_allowed_tools"`), and `args_digest=arguments`. This applies to both internal and public paths — the callback already exists on the public path but was never invoked on the permission_denied paths. This closes the same gap on both paths simultaneously.
- **Patterns to follow:** `mcp_public.py:248-264` — `_audit_tool_call` closure pattern exactly.
- **Test scenarios:**
  - Internal SSE path constructs `MCPSession` with a non-None `audit_callback`
  - `audit_callback` is invoked with `event_type="tool_call"`, `status="success"` on successful tool execution
  - `audit_callback` is invoked with `status="error"`, `error_code="tool_execution_error"` on tool failure
  - `audit_callback` is invoked with `status="permission_denied"`, `error_code="role_not_allowed"` when role check fails
  - `audit_callback` is invoked with `status="permission_denied"`, `error_code="not_in_allowed_tools"` when whitelist check fails
  - `token_id` is `None` in all internal audit entries
  - `client_ip` is `"internal"` for all internal audit entries
  - Covers R3: write both token-based (public path) and NULL-token (internal path) entries to `mcp_access_logs`, then verify `scan_mcp_anomalies()` and `get_mcp_stats()` return correct results including the NULL-token entries in their aggregates
- **Verification:** `pytest tests/backend/unit/test_mcp_internal_audit.py -v` passes. Existing `test_mcp_sse_caller_handshake.py` tests still pass (no behavior change to handshake).

---

### U2. Wire caller context through guardrail provider

- **Goal:** `NuminaGuardrailProvider.check_tool_call` receives and preserves caller context (`caller_user_id`, `caller_role`) instead of discarding it, enabling future caller-aware guardrail rules.
- **Requirements:** R4, R5
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/deerflow_adapter/numina_guardrail_provider.py` — remove `del context` / `del tool_args`, pass context to `_check_internal`
  - `server/tests/agent/unit/test_numina_guardrail_provider.py` — extend with context pass-through tests
- **Approach:**
  1. Remove `del tool_args` (line 116) and `del context` (line 117) from `check_tool_call`.
  2. Update `_check_internal` signature to accept optional `context: dict | None = None` parameter. Pass `context` from `check_tool_call` to `_check_internal`.
  3. `_check_internal` does not use the context for any rule yet — it simply accepts and ignores it. The data is available for future rules.
  4. Add a debug log line: `logger.debug("[guardrail] context: caller_user_id=%s caller_role=%s", context.get("caller_user_id"), context.get("caller_role"))` when context is provided.
- **Patterns to follow:** The existing `check_tool_call` signature already declares `context: dict[str, Any] | None = None` — the parameter is there, just unused.
- **Test scenarios:**
  - `check_tool_call` with `context={"caller_user_id": "u1", "caller_role": "member"}` does not raise and returns a valid `GuardrailDecision`
  - `check_tool_call` with `context=None` (backward compat) still works
  - `check_tool_call` with `tool_args` does not raise (previously `del tool_args` would have worked, but now the args are preserved)
  - `_check_internal` receives the context dict when provided
- **Verification:** `pytest tests/agent/unit/test_numina_guardrail_provider.py -v` passes. Existing guardrail tests still pass.

---

### U3. Re-validate caller role on every tool call

- **Goal:** `call_tool()` uses the current `user.role` from the database on every invocation, not the stale `self._caller_role` cached at SSE handshake. Deactivated users and role changes are detected within one tool call.
- **Requirements:** R6, R7, R8
- **Dependencies:** None (but implemented alongside U1 since both touch `mcp_session.py`)
- **Files:**
  - `server/apps/backend/app/services/mcp_session.py` — restructure `call_tool()` flow
  - `server/tests/backend/unit/test_mcp_session_caller_binding.py` — extend with re-validation tests
- **Approach:**
  1. Move the `with SessionLocal() as db:` block and `_get_caller_user()` call (currently at line 388-389) to before the role check (currently at line 329).
  2. Replace ALL `self._caller_role` references in `call_tool()` with `user.role`: (a) line 329 main role check, (b) line 334 external_token bypass, (c) line 362 whitelist gate, (d) lines 341/368 permission_denied log messages. This ensures consistent use of the fresh role throughout the method.
  3. The `_get_caller_user()` call already checks `is_active` and family membership — a deactivated user raises `RuntimeError`. Add an explicit `try/except RuntimeError` around the call. In the except handler: (a) invoke `self._audit_callback(event_type="tool_call", tool_name=name, status="permission_denied", error_code="caller_invalid", args_digest=arguments)` to preserve the audit trail (currently, the RuntimeError propagates to the `except Exception` block at line 1069 which audits it as `tool_execution_error` — the new handler must audit it before returning), then (b) return a structured `permission_denied` TextContent response.
  4. The existing `self._caller_role` slot is still frozen at construction — it remains available as the session identity for logging. The role *check* now uses the fresh value from DB, but the session binding is unchanged.
  5. Also update `docs/plans/2026-05-31-001-feat-mcp-caller-bound-principal-plan.md` to mark D7 (`caller_role lifetime = SSE connection`) as superseded by D1 in this document, with a cross-reference link.
- **Execution note:** This restructures `call_tool()`'s early flow. Verify no code between the current role check (line 329) and the DB session open (line 388) depends on the role check having already happened. Note: after this change, every `call_tool()` — including denied calls — opens a DB connection for the fresh role read. This is an acceptable security tradeoff (the `_get_caller_user()` call was already made for allowed calls, so the marginal cost is zero for the common path; denied calls now pay one extra DB read that they previously avoided).
- **Patterns to follow:** `_get_caller_user()` at `mcp_session.py:206-213` — the existing per-call validation pattern.
- **Test scenarios:**
  - Covers AE1: `call_tool()` uses fresh `user.role` from DB, not `self._caller_role`. Mock `_get_caller_user` to return a user with `role="owner"` when session was created with `role="member"` — tool call proceeds with `owner` permissions.
  - Covers AE2: `_get_caller_user` raises `RuntimeError` (user deactivated) — `call_tool()` invokes `audit_callback` with `status="permission_denied"`, `error_code="caller_invalid"` before returning structured denial response. No audit regression.
  - `_get_caller_user` returns user with changed role — role check uses the new role for `allowed_roles` filtering.
  - Existing `TestCallToolIgnoresArgs` tests still pass — args-injection defense is unchanged.
- **Verification:** `pytest tests/backend/unit/test_mcp_session_caller_binding.py -v` passes (existing + new tests). `pytest tests/backend/ -v` full suite passes — no regressions.

---

### U4. Add agent-path confused-deputy tests

- **Goal:** Verify that the agent→backend MCP pipeline correctly propagates caller identity and rejects identity injection via tool arguments.
- **Requirements:** R9, R10, R11
- **Dependencies:** U1, U3 (tests exercise the final state of internal audit and role re-validation)
- **Files:**
  - `server/tests/agent/unit/test_mcp_caller_identity_propagation.py` — new test file
- **Approach:**
  1. Test ContextVar → header injection: verify that `_resolve_numina_mcp_servers()` injects `X-Caller-User-Id` from the `user_id` parameter (which comes from the `caller_user_id` ContextVar via `RunContext`) into MCP SSE headers. Mock `BackendClient.get_enabled_mcp_servers()` to return a server config, call `_resolve_numina_mcp_servers()`, and assert the headers dict contains the correct `X-Caller-User-Id`.
  2. Test args-isolation in agent-path context: create an `MCPSession` with known identity, call `call_tool()` with injected `caller_user_id` / `family_id` in arguments, and verify the tool executes with the session-bound identity (not the injected values). This extends the existing `TestCallToolIgnoresArgs` pattern to cover the agent-path scenario where ContextVar sets the identity.
  3. Test SSE handshake rejects cross-family callers in agent-path context: verify that `_resolve_numina_mcp_servers()` with a `user_id` belonging to a different family still injects the header correctly (the backend SSE endpoint then rejects it at handshake — this is already tested in `test_mcp_sse_caller_handshake.py`, but the agent-side test verifies the header injection is correct regardless).
- **Patterns to follow:** `tests/agent/unit/test_build_prompt.py:28` — existing test documenting ContextVar-based MCP identity. `tests/backend/unit/test_mcp_session_caller_binding.py` — args-isolation test pattern.
- **Test scenarios:**
  - `_resolve_numina_mcp_servers(family_id="fam-1", user_id="user-A")` produces headers with `X-Caller-User-Id: user-A` for backend MCP servers
  - `_resolve_numina_mcp_servers` with `user_id=None` does not include `X-Caller-User-Id` header (graceful degradation)
  - `MCPSession` bound to `user-A` / `fam-1`, tool args contain `{"caller_user_id": "user-B", "family_id": "fam-2"}` — tool executes as `user-A` in `fam-1`, audit log records `user-A`
  - `_resolve_numina_mcp_servers` identifies backend MCP servers by URL pattern (`/internal/mcp/`) and only injects headers into those
- **Verification:** `pytest tests/agent/unit/test_mcp_caller_identity_propagation.py -v` passes. Full agent test suite `pytest tests/agent/ -v` passes.

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Backend unit tests | `cd server && uv run pytest tests/backend/unit/test_mcp_session_caller_binding.py tests/backend/unit/test_mcp_internal_audit.py tests/backend/unit/test_mcp_sse_caller_handshake.py -v` | U1, U3 |
| Agent unit tests | `cd server && uv run pytest tests/agent/unit/test_numina_guardrail_provider.py tests/agent/unit/test_mcp_caller_identity_propagation.py -v` | U2, U4 |
| Full backend suite | `cd server && uv run pytest tests/backend/ -v` | All — no regressions |
| Full agent suite | `cd server && uv run pytest tests/agent/ -v` | All — no regressions |
| Backend typecheck | `cd server && uv run mypy apps/backend/app/services/mcp_session.py apps/backend/app/routers/mcp_internal.py` | U1, U3 |
| Agent typecheck | `cd server && uv run mypy --exclude vendor apps/agent/services/deerflow_adapter/numina_guardrail_provider.py` | U2 |
| Lint | `cd server && uv run ruff check apps/backend/app/routers/mcp_internal.py apps/backend/app/services/mcp_session.py apps/agent/services/deerflow_adapter/numina_guardrail_provider.py` | All |

---

## Definition of Done

- R1–R11 all have corresponding test scenarios that pass.
- All verification commands in the Verification Contract pass with zero failures.
- No existing tests regress — the full backend and agent test suites pass.
- The `mcp_access_logs` table receives entries from both internal and public paths with correct fields.
- `_get_caller_user()` is called on every `call_tool()` invocation (verifiable by test mock assertion).
- `NuminaGuardrailProvider.check_tool_call` no longer contains `del context` or `del tool_args`.
- Product Contract preservation: unchanged — all R-IDs, AEs, Flows, and Key Decisions from the brainstorm are intact.
