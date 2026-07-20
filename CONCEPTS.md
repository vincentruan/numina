# Concepts

Shared domain vocabulary for this project — entities, named processes, and status concepts with project-specific meaning. Seeded with core domain vocabulary, then accretes as ce-compound and ce-compound-refresh process learnings; direct edits are fine. Glossary only, not a spec or catch-all.

## Agent dispatch

### stream_run
The single LangGraph SSE streaming entry point that runs an AI agent turn over the `/api/threads/{id}/runs/stream` route. All AI applications (chat, asset-report, import-parse, finance-coach, wish-advice) funnel through it via `worker.run_agent`, which reads `record.metadata["app"]` to select a per-app runner. The name replaced the earlier `stream_run_v2` symbol; the wire path was unchanged.

### RESERVED_NAMES
The set of system fixed-flow capability ids that an owner cannot shadow with a custom skill. Each maps to a built-in agent with a fixed pipeline (e.g. `asset-report` is a three-step report pipeline) or a reserved dispatch mode (`chat` is a reserved sentinel — `agent_skills == ["chat"]` is mapped to `[]` in the dispatch layer so the agent loads only the `chat/SKILL.md` "numina SOUL" skill via DeerFlow and never inherits family business skills). Per-wish capabilities such as `wish-advice` are not reserved.

### ChatAdapter
The chat-specific adapter that owns prompt resolution (family override → default `default_system_prompt.md`), MCP SSE URL construction (with `family_id` validation), and DeerFlow stream delegation for the conversational app. It wraps the system prompt in XML tags for privilege separation (DeerFlow has no native system role) and is the per-app runner's delegation target for the `numina` (chat) app. It survives the unified-dispatch refactor; the earlier `Orchestrator` that branched chat-vs-skill is deleted.

### sandbox_family_id
A coroutine-scoped ContextVar carrying the tenant family id that scopes every agent sandbox file operation (`write_file`, `read_file`, `str_replace`) under `AGENT_DATA_DIR/{family_id}/sandboxes/...`. It is set at the `worker.run_agent` dispatch boundary before any branch runs and reset in a `finally`, and must be propagated into executor threads via `copy_context().run` because `loop.run_in_executor` does not copy contextvars — without propagation the provider resolves empty path mappings and file tools fail open (return success without writing).

## API serialization

### SnowflakeBase
The base Pydantic response model every API response schema inherits from. At JSON serialization it converts `int` fields named `id` or ending in `_id` to `str` (the bigint-on-wire-as-string convention — JS doubles lose precision beyond 2^53). It is the mechanism that enforces the ID half of the money/bigint-as-strings wire convention; the money half is enforced per-schema by typing money fields `str` with a quantizing `field_validator`.
