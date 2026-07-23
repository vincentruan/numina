---
title: Two-AI-apps unified dispatch — stream_run + multi-app worker dispatch
date: 2026-07-20
category: architecture-patterns
module: agent
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - "Unifying two previously-separate AI dispatch mechanisms (a live path + a dead/legacy trigger pipeline) under a single multi-app dispatch entry point"
  - "Migrating LangGraph/DeerFlow SSE streaming agents to a per-app stream_run pattern where worker.run_agent reads record.metadata['app'] and routes to per-app runners"
  - "Consolidating per-domain family-* skills into one SOUL skill while promoting report/import-parse/suggest into first-class stream_run agents"
  - "Needing per-tenant sandbox isolation (set_family_sandbox_context) and ContextVar propagation through run_in_executor for agent file writes"
  - "Diagnosing whether an Orchestrator.dispatch code path is actually live or has been dead since an earlier refactor before investing in it"
tags: [ai-agent, stream-run, multi-app-dispatch, deerflow, sandbox-isolation, refactor]
---

# Two-AI-apps unified dispatch — stream_run + multi-app worker dispatch

## Context

Numina's agent layer grew two parallel AI dispatch mechanisms that never agreed on a single entry point. The **live** path was `/ai/chat`, which funneled every chat turn through `worker._run_numina_agent` and DeerFlow's `stream_run` route (`server/apps/agent/routers/runs_stream.py`). The **other** path was a trigger-skill pipeline: a constellation of routers (`ai_alerts.py`, `ai_allocation.py`, `ai_disposal.py`, `ai_liability.py`, `ai_spending_leaks.py`, plus a separate report router) that were supposed to dispatch specialist skills through an `Orchestrator.dispatch` method. Over a series of earlier refactors those routers had been wired to a `stream_dispatch` method that never existed — the `Orchestrator` only ever implemented `dispatch`, not `stream_dispatch`. Per this refactor's audit, the eight trigger-skill routers had been dead since commit `a97eb08c` on this branch and were never reachable at runtime. They compiled, they had tests, they appeared in route tables, but no live code path invoked them.

The "report skill" layered on top of that pipeline was the opposite: it was the **live** report-generation mechanism, while the `asset-report` agent that nominally replaced it was dead code before U4 rebuilt it. The NDJSON streaming stack built to surface report progress (the `/events` endpoints, `proxy_report_events`, and the NDJSON composables) was likewise entirely dead — three layers of plumbing that no client consumed. An earlier memory had also asserted an 8-hour scheduled report refresh existed; the refactor confirmed that job was never implemented (the scheduler entries were `snapshot_daily` and `exchange_rate`, conflated with report refresh). So the agent surface area was simultaneously carrying a large volume of dead code **and** missing the multi-app dispatch shape that the product actually needed: `asset-report`, `import-parse`, `finance-coach`, and `wish-advice` each wanted to run as first-class streamed agents through the same worker, not as orphan routers.

The friction this created was threefold. First, every new AI capability either had to bolt onto the chat path informally or revive the dead trigger pipeline, with no clean third option. Second, the dead routers actively obscured the real mechanism — a developer reading `ai_liability.py` would assume liability analysis flowed through it, when in fact it flowed nowhere. Third, the multi-tenant sandbox that all these agents depend on was only correct for the chat path; the per-app agents being added (notably `asset-report`, which writes a markdown file into the sandbox via the `write_file` tool) exposed that the sandbox's family-scoping ContextVar was never propagated into DeerFlow's executor threads, so tenant isolation silently failed for any non-chat agent. The goal of the U1–U8 refactor was to collapse both mechanisms into one multi-app `worker.run_agent` dispatch that reads `record.metadata["app"]` and routes to per-app `stream_run` agents, delete the dead pipeline and NDJSON stack outright, and fix the sandbox-isolation defects that the new per-app agents surfaced.

## Guidance

The canonical pattern is a single coroutine-scoped dispatch entry that (a) establishes per-tenant sandbox context before any branch runs, (b) branches on a metadata field to a per-app runner, and (c) resets that context in a `finally` that wraps every branch. The entry lives in `server/apps/agent/services/runtime/worker.py`:

```python
async def run_agent(
    *, bridge, run_manager, record, family_id, user_id, thread_id,
    graph_input, config, stream_modes=None, resume_answer=None, interrupt_id=None,
) -> None:
    # Resolved-3 blocker A: set the family_id ContextVar before any sandbox
    # tool (write_file/read_file) can be invoked. Must run in all branches.
    set_family_sandbox_context(family_id, caller_user_id=user_id)

    # P0, ce-code-review 2026-07-19: the family_id + extensions_config_path
    # ContextVars are coroutine-scoped and would leak into a subsequent run if
    # this coroutine is reused (shared worker task / executor thread). Mirror
    # the active-skill reset pattern: set above, reset in a finally that wraps
    # all dispatch branches + any exception path.
    try:
        app = record.metadata.get("app", "numina") if record.metadata else "numina"
        if app == "asset-report":
            await _run_asset_report_pipeline(...); return
        if app == "import-parse":
            await _run_import_parse_agent(...); return
        if app == "finance-coach":
            await _run_finance_coach_agent(...); return
        if app == "wish-advice":
            await _run_wish_advice_agent(...); return
        # Default / "numina"
        await _run_numina_agent(..., stream_modes=stream_modes,
                                resume_answer=resume_answer, interrupt_id=interrupt_id)
    finally:
        reset_family_sandbox_context()
```

(`worker.py:235` sets the context, the `try` opens at `worker.py:242`, `app` is read at `worker.py:243`, the branches span `worker.py:244-305`, and `worker.py:307` resets in `finally`.) Two things make this correct rather than merely convenient.

**Upstream allowlist — lockstep pair.** The `app` field is validated in `sse_gateway.start_run` before the run is even created: direct client calls with `app == "asset-report"` / `"import-parse"` / `"finance-coach"` / `"wish-advice"` are rejected with HTTP 409 ("…须经由后端触发端点，请勿直连 /runs/stream") in `sse_gateway.py`, and any unknown `app` value is rejected with 400. Only `numina` and internal (backend-triggered) calls reach `run_agent`. The worker's branch list and the gateway's allowlist are a lockstep pair — widening one without the other opens a security window.

**Per-branch context set + `finally` reset.** The ContextVar is set once at the top, not inside each branch, so a future branch addition cannot forget it; the `finally` guarantees reset even when a runner raises, which matters because the coroutine can be reused across runs (shared worker task / executor thread) and a leaked `family_id` would route the next family's `write_file` into the previous family's sandbox.

The second load-bearing pattern is propagating that ContextVar into DeerFlow's executor threads. DeerFlow runs the LangGraph agent via `loop.run_in_executor`, which does **not** propagate `contextvars` from the calling task into the pool thread. The fix is `_run_in_executor_with_context` in `server/apps/agent/services/deerflow_adapter/adapter.py:72`:

```python
def _run_in_executor_with_context(loop, executor, func, *args) -> asyncio.Future:
    """Submit ``func`` to ``executor`` preserving the caller's contextvars.

    Without propagation the provider sees family_id=None and returns empty
    path mappings, so write_file finds no mapping for /mnt/user-data/workspace
    and the file silently never lands on disk (the tool still returns "OK" —
    fail-open). This is the F2 root cause.
    """
    ctx = contextvars.copy_context()
    return loop.run_in_executor(executor, lambda: ctx.run(func, *args))
```

This is the same mechanism `asyncio.to_thread` uses internally. Every DeerFlow stream entry point that submits to the executor (`adapter.py:190`, `:351`, `:596`) goes through this wrapper so `sandbox_family_id` and `numina_active_skill_name` are visible inside the pool thread where LangGraph's `ToolNode` invokes `write_file` / `read_file` synchronously.

The third pattern is the `extensions_config` ContextVar isolation. DeerFlow resolves the MCP extensions config file via `ExtensionsConfig.resolve_config_path`, which consults the process-global `DEER_FLOW_EXTENSIONS_CONFIG_PATH` env var. That env var is a single process-wide slot — under multi-family concurrency two interleaved runs overwrite each other's value, leaking family-A's MCP SSE URL (which embeds family-A's id) into family-B's run. The fix in `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py:536` inserts a priority-0 step that consults Numina's coroutine-scoped `numina_extensions_config_path` ContextVar before falling back to the env var:

```python
def _patched_resolve_config_path(cls, config_path=None):
    from apps.agent.services.runtime.sandbox_provider import (
        get_extensions_config_path as _get_ext_path,
    )
    if config_path is None:
        ctx_path = _get_ext_path()
        if ctx_path:
            # Hand off to the original resolver with an explicit path so it
            # still validates existence and returns a Path (priority 1 path).
            return _orig_resolve_config_path.__func__(cls, ctx_path)
    return _orig_resolve_config_path.__func__(cls, config_path)

ExtensionsConfig.resolve_config_path = classmethod(_patched_resolve_config_path)
```

The ContextVar is set by the adapter alongside `family_id` and propagates into both the deerflow executor thread and the sync tool-executor pool via the `_run_in_executor_with_context` wrapper above, so every call site that resolves the extensions config — `get_available_tools`'s MCP gate check, the MCP cache's staleness check, and the patched `_patched_get_mcp_tools` — all see the same per-run path with no cross-family leakage. An explicit `config_path` argument still takes precedence (priority 1), preserving the original API contract.

Around these three pillars, the refactor made the supporting moves:

- **U1** renamed `stream_run_v2` to `stream_run` in `runs_stream.py` (route path `/{thread_id}/runs/stream` unchanged — a pure rename so the wire contract stays stable while the internal symbol matches the dispatch vocabulary).
- **U3** merged the four `family-*` skills (`family-asset-checkup`, `family-finance-insight-planner`, `family-liability-review`, `fixed-asset-followup`) into one `server/apps/agent/skills/builtin/public/chat/SKILL.md` "numina SOUL" skill and removed the orphaned agent profiles + `system_ids` via alembic migration `c3a1f5e7d901_remove_family_skill_orphans.py`.
- **U4** built the `asset-report` 3-step pipeline (`_run_asset_report_pipeline`) on top of the F2 fixes; unified all agent file paths to the DeerFlow layout (family_id as effective user) with a `_deerflow_default_workspace_md` dual-root search helper (the LLM sometimes emits a host path; the worker translates to the container path); persisted `markdown_file_path` to `ai_reports`; added cache re-validation on entity change.
- **U6** migrated `suggest` (`server/apps/agent/services/asset_suggest.py`) to a lightweight single-LLM call (`_create_lightweight_llm` + `ainvoke`) and added XML-delimiter injection defense so the delimiter cannot appear in model output.
- **U8** deleted the `Orchestrator` class + `dispatch` method + singleton entirely — `server/apps/agent/services/orchestrator.py` now retains only the module-level `_select_model` / `_fire_and_forget` helpers that `agent_dispatch.py` still imports, with a docstring noting the deletion.
- `RESERVED_NAMES` in `server/apps/backend/app/routers/ai_skills.py:56` settled to `["chat", "asset-report", "import-parse", "finance-coach"]` — these are the system fixed-flow ids that owners cannot shadow with a custom skill. (`wish-advice` is per-wish, not a system fixed-flow, so it is not reserved.)

## Why This Matters

The unification is not cosmetic. The previous shape had a live chat path that correctly handled tenant isolation and a dead trigger pipeline that looked like it handled five more capabilities but actually did nothing — a developer adding a sixth capability would have reasonably wired it into the dead pipeline and shipped a no-op. Collapsing both into one dispatch surface means there is exactly one place to read to understand "how does an AI app run" (`worker.run_agent`), one place to add a new app (a new branch + a per-app runner + an allowlist entry), and one place to enforce the per-tenant invariant (the `set_family_sandbox_context` + `finally` reset pair). The dead code was actively hostile: the eight routers and the NDJSON stack consumed review attention, test coverage, and mental model budget while providing zero behavior.

The sandbox-isolation fixes are the substantive correctness gain. `NuminaLocalSandboxProvider._build_thread_path_mappings` reads the `sandbox_family_id` ContextVar to scope paths under `AGENT_DATA_DIR/{family_id}/sandboxes/...`. When the ContextVar is absent — which is exactly what happened before the executor-propagation fix, because `run_in_executor` does not copy context — the provider returns empty mappings, `write_file` finds no mapping for `/mnt/user-data/workspace`, and the tool returns `"OK"` anyway. That is a fail-open silent data-loss bug: the agent believes it wrote the report, the run completes successfully, and no file exists. Worse, the same mechanism gates multi-tenant isolation: without per-run ContextVars, two concurrent families share whatever value last won the env-var race, so family-B's agent could resolve family-A's MCP config (which embeds family-A's id in the SSE URL) and family-A's sandbox paths. The `extensions_config` ContextVar fix closes the MCP-config half of that leak; the `sandbox_family_id` propagation closes the file-path half. Together they make concurrent multi-family agent runs actually isolated, which the product's privacy-first, multi-tenant premise requires.

## When to Apply

- A LangGraph / DeerFlow (or similar agent-harness) worker serves multiple AI applications behind one process and any of them touch per-tenant resources — sandbox filesystems, MCP config files, or skill-filter state held in ContextVars. The defining signal is: the harness submits agent execution to a thread pool or executor (`run_in_executor`, `to_thread`, a sync `ToolNode`), and tenant identity is carried in a ContextVar rather than threaded through every call. In that situation the default executor does not propagate the ContextVar, so you must wrap submission in `copy_context().run`, and you must set + reset the ContextVar at the dispatch boundary with a `finally` that covers every branch.
- Migrating from a trigger-skill or router-per-capability pipeline to a unified stream-dispatch model. The migration is not just moving code — it is surfacing which routers were already dead (no reachable caller) versus which were the real mechanism, then deleting the dead ones before they mislead the next maintainer. The pre-flight audit ("does anything actually call `stream_dispatch`?") should happen *before* any consolidation, because building a unified dispatch on top of routers that were never wired produces a system with two unified dispatches.
- A metadata field selects a privileged code path. Validate the field at the gateway boundary (rejecting direct-connect with 409 and unknown values with 400) and keep the worker's branch list a strict mirror of the gateway's allowlist, so widening one without the other is the only way to open a path.
- A process-global slot (env var, module global) that a per-run value is written to. Under concurrency it is a hazard; replace it with a coroutine-scoped ContextVar and patch the resolver to consult it first.

## Examples

**ContextVar-not-propagated dead end (F2).** The `asset-report` pipeline called the `write_file` MCP tool to land a markdown report in the family sandbox. The tool returned `"OK"`. No file appeared on disk. The instinct is to debug the tool. The actual cause was one layer up: `worker.run_agent` had called `set_family_sandbox_context(family_id)` correctly, but DeerFlow's adapter ran the LangGraph agent via `loop.run_in_executor(...)`, which does not copy the calling task's contextvars into the pool thread. Inside that thread, `NuminaLocalSandboxProvider._build_thread_path_mappings` read `sandbox_family_id` and got `None`, returned empty path mappings, and `write_file` — finding no mapping for `/mnt/user-data/workspace` — failed open and returned `"OK"`. The fix was not in the tool or the provider; it was `_run_in_executor_with_context` (`adapter.py:72`) capturing `contextvars.copy_context()` and running the submitted function inside it. After the fix, the same `write_file` call landed the file in `AGENT_DATA_DIR/{family_id}/sandboxes/...` as intended. **Lesson: a tool returning success while doing nothing is the signature of a context-propagation gap, not a tool bug.** *(auto memory [claude] — f2-sandbox-contextvar-not-propagated-fix)*

**`extensions_config` env-var leak (concurrent multi-family).** The process-global `DEER_FLOW_EXTENSIONS_CONFIG_PATH` env var is a single slot. Under concurrency, family-A's adapter set it to a path embedding family-A's id, then family-B's adapter overwrote it with family-B's path before family-A's MCP tools finished resolving. Family-A's `get_available_tools` gate (which calls `ExtensionsConfig.from_file()`, reading the env var at resolve time) then saw family-B's config. The e2e concurrent test ran `testuser` (8 configured tools, 0 assets) against `demouser` (~6.15M assets) simultaneously; before the fix, tool lists and config roots crossed families. After the fix — the priority-0 `numina_extensions_config_path` ContextVar lookup in `sync_tool_patch.py:536`, propagated into the executor by the same `_run_in_executor_with_context` wrapper — both families saw only their own tools and their own sandbox roots. **Lesson: any process-global slot that a per-run value is written to is a concurrency hazard; replace it with a coroutine-scoped ContextVar and patch the resolver to consult it first.** *(auto memory [claude] — extensions-config-contextvar-multifamily-fix)*

**Dead-router discovery.** The refactor's audit asked whether `Orchestrator.stream_dispatch` existed. It did not — `Orchestrator` had `dispatch` only. That meant `ai_alerts.py`, `ai_allocation.py`, `ai_disposal.py`, `ai_liability.py`, `ai_spending_leaks.py`, and three sibling routers, all of which appeared to dispatch specialist skills, had no reachable runtime caller; they had been dead since commit `a97eb08c` on this branch. The "report skill" they layered on was the live mechanism, and the NDJSON `/events` stack built to surface their progress had no consumer. U5 and U7 deleted the routers, the report skill, the NDJSON stack, the `time_machine` coupling, and five trigger-skill models (`ai_liability_result`, `ai_spending_leak`, etc.) — roughly 5,648 deletions across 58 files per this refactor's conclusion — and U8 deleted the `Orchestrator` class + singleton entirely, leaving only the provider-selection helpers that `agent_dispatch.py` still imports. **Lesson: before unifying dispatch, grep for the dispatch method you assume exists; if the routers point at a method that was never implemented, the routers are dead and should be deleted before they obscure the real mechanism.** *(auto memory [claude] — ai-dispatch-dead-routers-reality, ai-two-apps-refactor-findings)*

## Related

- **Supersedes** [`mcp-chat-adapter-architecture-2026-05-21.md`](./mcp-chat-adapter-architecture-2026-05-21.md) — that doc describes the pre-refactor `ChatAdapter.stream()` vs `Orchestrator.stream_dispatch()` dispatch model as the live architecture. This refactor deletes `Orchestrator.dispatch`/`stream_dispatch` entirely and replaces it with `worker.run_agent(app)` + per-app `stream_run` agents. The old doc's dispatch table and before/after examples are now historical.
- **Cross-reference** [`mcp-caller-bound-principal-2026-05-31.md`](./mcp-caller-bound-principal-2026-05-31.md) — the `MCPSession.__slots__` caller-binding invariant (family_id + caller_user_id frozen at handshake). This refactor's `extensions_config` per-run ContextVar + sandbox ContextVar propagation extend that tenant-isolation invariant from SSE-handshake scope to per-run executor-thread scope.
- **Cross-reference** [`../best-practices/cache-key-granularity-matches-data-scope-2026-04-27.md`](../best-practices/cache-key-granularity-matches-data-scope-2026-04-27.md) — the family-scoped sandbox cache key fix (P2 latent defect) applies the same "cache key scope must match data scope" principle to the agent sandbox cache.
- **Related** [`../integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`](../integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md) — prior DeerFlow adapter/orchestrator integration history; the executor-thread lock-acquisition lesson directly informs this refactor's ContextVar propagation through executor threads.
- **Related** [`../integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md`](../integration-issues/deerflow-adapter-stream-type-mismatch-and-security-issues-2026-05-16.md) — documents the `stream_dispatch` `StreamChunk`-vs-`str` contract and the NDJSON path, both of which this refactor deletes as dead code.
- **Related** [`unified-data-root-path-management-2026-05-17.md`](./unified-data-root-path-management-2026-05-17.md) — establishes the `DATA_ROOT/workspace/{family_id}/...` layout that the asset-report agent's `write_file` + DeerFlow default-workspace fallback builds on.
