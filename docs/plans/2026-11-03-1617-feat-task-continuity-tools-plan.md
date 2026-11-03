---
title: Task Continuity Tools - Plan
date: 2026-11-03
type: feat
topic: task-continuity-tools
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
---

# Task Continuity Tools — Plan

## Goal Capsule

- **Objective:** The AI maintains critical context across compaction boundaries and between sessions, so users don't re-explain important facts or rediscover prior analyses.
- **Means:** Enable DeerFlow's upstream `task_continuity` feature (provides `task_note` and thread-scoped `history_search`/`history_read`), and build a Numina-owned `thread_search` + `thread_read` pair for family-wide session discovery and cross-thread access (KTD3, KTD2 revised).
- **Execution profile:** Single PR. Config injection (`_inject_task_continuity`) + conversation reader callback + one new custom tool (`thread_search`) + unit tests. No frontend changes.
- **Stop conditions:** `task_note` survives a compaction cycle in test; `thread_search` returns relevant sessions from a family with 5+ past conversations; `read_conversation` reads cross-thread messages from another family thread.

---

## Product Contract

### Summary

Three LLM-callable tools give the AI explicit control over context continuity. `task_note` is a persistent scratchpad the LLM writes to during long conversations — notes survive compaction via DeerFlow's durable ThreadState channels. `thread_search` and `read_conversation` form a two-step cross-session discovery pattern: the LLM searches family-wide past sessions by relevance, then reads full content when deeper context is needed.

### Problem Frame

In long conversations, DeerFlow's `SummarizationMiddleware` auto-compacts when approaching token limits. Important facts — budget numbers, user preferences, intermediate decisions — get summarized away. The LLM then operates on incomplete context, re-asks questions it already answered, or contradicts earlier decisions.

Across sessions, the AI starts with a blank slate. A family may have dozens of past conversations containing valuable analyses, reports, and Q&A. None of this surfaces unless the user explicitly references it. The family's institutional knowledge is locked in past sessions with no way for the AI to discover or build on it.

### Key Decisions

- **KD1. task_note is an explicit LLM tool, not system auto-extraction.** The LLM proactively calls `task_note` to save important facts. Predictable, lightweight, and skill authors can include it in `allowed-tools`. (session-settled: user-directed — chosen over system auto-extraction and hybrid: explicit tool is simpler and more predictable.) Governs R1–R3.

- **KD2. Search scope is family-wide.** All family members' sessions are searchable. Matches Numina's family-scoped data model. (session-settled: user-directed — chosen over per-user and family-wide-with-privacy-controls: consistent with existing asset/liability/report scoping.) Governs R4–R5.

- **KD3. Tools are available to all skills by default.** Not restricted to specific skill `allowed-tools`. These are system-level tools, like DeerFlow's `tool_search`. Governs R6–R8.

### Requirements

**task_note — within-thread continuity**

- R1. The LLM can call `task_note(text)` to persist a text note in a durable ThreadState channel that survives compaction.
- R2. After compaction, persisted notes are projected back into the LLM's context so the LLM sees them in subsequent turns.
- R3. Notes accumulate additively within a thread — each call appends, never overwrites. The LLM can read back its notes by calling `task_note()` with no arguments.

**history_search — cross-session discovery**

- R4. The LLM can call `history_search(query)` to find matching sessions across the family's past conversations.
- R5. Results include session ID, title, relevant snippet, and timestamp — enough for the LLM to decide which sessions to read in full.
- R6. Results are scoped to the current family — only sessions belonging to the LLM's active family are returned.

**history_read — cross-session access**

- R7. The LLM can call `history_read(session_id)` to retrieve message history from a specific past session.
- R8. The returned content is truncated or paginated to avoid overwhelming the context window.

**Common**

- R9. All three tools are registered as DeerFlow tools following existing conventions.
- R10. Authorization uses Numina's existing family-scoped auth — no new permission model.

**Naming map.** The Requirements above use the brainstorm's names. Implementation maps them as follows: `history_search` (R4–R6) becomes Numina's `thread_search` because upstream `history_search` is thread-scoped, not family-wide (KTD3); `history_read` (R7–R8) is satisfied by upstream's `read_conversation`, because upstream `history_read` reads the compaction archive by `source_id`, not another session (KTD2). Both upstream tools are still enabled by `task_continuity.enabled` and remain available for thread-scoped use.

<!-- ce-section: work-relationships -->
### How This Work Fits Together

This plan covers T25 (Task Continuity Tools) from issue #176. It is one of six P3 future enhancement tasks (T22–T27). The breakdown reflects current understanding, not a committed roadmap — later brainstorms may revise it.

- T25 (this plan): Task continuity via task_note + thread_search + read_conversation
- T24 (Tool Promotion Middleware): Has a completed plan at `docs/plans/2026-11-03-1604-feat-tool-promotion-middleware-plan.md`. Can proceed independently.
- T22 (Container Sandbox): Can proceed independently.
- T23 (Scheduled Tasks): Can proceed independently.
- T26 (Thread Branching): Branch endpoint already exists. Can proceed independently.
- T27 (Evidence Seal): Can proceed independently.

### Scope Boundaries

**Deferred for later:**
- Semantic / embedding-based search — keyword-based search is the initial mechanism.
- Frontend UI for viewing or editing task notes — notes are LLM-facing only.
- Cross-thread note visibility — notes are thread-scoped; other threads cannot read them.
- Integration between task_note and DeerMem — notes are separate from DeerMem's automatic memory extraction.
- Message-level full-text search across family sessions — initial `thread_search` searches session titles and metadata. Deeper message content search is a future enhancement.

### Key Flows

- F1. Within-thread note persistence
  - **Trigger:** LLM is mid-conversation and identifies a critical fact (budget limit, user preference, decision).
  - **Steps:** LLM calls `task_note("The family monthly budget is ¥50,000")`. Note is stored in durable ThreadState channel. Conversation continues. Auto-compaction fires. After compaction, `DurableContextMiddleware` projects the note channel back into context.
  - **Outcome:** LLM sees its saved notes alongside the compacted summary. Can reference the budget without the user repeating it.
  - **Covers R1, R2, R3**

- F2. Cross-session discovery
  - **Trigger:** User starts a new session with a question related to past work (e.g., "How is our investment doing?").
  - **Steps:** LLM calls Numina's `thread_search("investment analysis")`. System lists family sessions via `list_sessions` and filters client-side on title and `last_message_summary`. Returns matching sessions with title, snippet, source, and timestamp.
  - **Outcome:** LLM has a list of relevant past conversations. Can decide whether to read any in full.
  - **Covers R4, R5, R6**

- F3. Deep dive into past session
  - **Trigger:** After thread_search, the LLM identifies a session worth reading in full.
  - **Steps:** LLM calls Numina's `thread_read(thread_id)`. The tool reads messages via the family-scoped checkpointer through `build_conversation_reader`. Returns paginated JSON content.
  - **Outcome:** LLM has full context from the past session. Can reference previous conclusions or avoid re-doing work.
  - **Covers R7, R8**

### Acceptance Examples

- AE1. Note survives compaction
  - **Given:** A family member is in a long analysis conversation. The LLM has called `task_note` 3 times to save key findings.
  - **When:** Auto-compaction triggers (token limit approached).
  - **Then:** After compaction, the LLM's context includes the 3 saved notes. The LLM can answer "What was the monthly budget we discussed?" correctly.
  - **Covers R1, R2**

- AE2. Cross-session search finds relevant past work
  - **Given:** A family has 10 past sessions across 2 members. One session's title contains "investment analysis".
  - **When:** The LLM calls `thread_search("investment")`.
  - **Then:** Results include that session with title, snippet, source metadata, and timestamp.
  - **Covers R4, R5, R6**

- AE3. Build on prior session's conclusions
  - **Given:** A previous session produced a detailed financial report. A new session starts with "Update the analysis from last month."
  - **When:** The LLM calls `thread_search` then `thread_read` on the matching session.
  - **Then:** The LLM has the prior conclusions and can build on them without re-asking the user for context.
  - **Covers R4, R7, R8**

*Product Contract preservation note: restructured, no scope change — R-IDs, Key Decisions, Flows, and Acceptance Examples are unchanged in meaning. The Summary and "How This Work Fits Together" now use implementation tool names (`thread_search`, `read_conversation`) instead of the brainstorm's `history_search`/`history_read`, with a naming map added under Requirements so both vocabularies remain traceable. R5's snippet requirement is met in implementation via `last_message_summary`, so it was not weakened.*

---

## Planning Contract

### Key Technical Decisions

KTD1. **Enable `task_continuity.enabled: true` by default with per-family `ai_config` override.** All families get task continuity tools unless explicitly disabled. Follows the `_inject_*` pattern from T15/T17/T24. Governs R1–R3, R9.

KTD2. **Numina-owned `thread_read` tool for cross-thread access, not upstream `read_conversation`.** Upstream's `read_conversation` is host-gated: its reader callable must reach `runtime.context`, but `DeerFlowClient._stream_turn` builds that dict internally and only forwards a fixed `_EMBEDDED_AUTHORIZATION_CONTEXT_KEYS` set from kwargs — the reader has no seam through the embedded client path. Numina's own `thread_read` tool (`services/runtime/thread_read_tool.py`) wraps `build_conversation_reader` as a `StructuredTool` that closes over the family-scoped checkpointer at construction time, avoiding any upstream modification. Product Contract R7–R8 are unchanged: the LLM still retrieves paginated messages from a specific past session. Governs R7–R8.

KTD3. **Build Numina `thread_search` for family-wide session discovery.** Upstream `history_search` is thread-scoped (searches within the current thread's messages via SQLite FTS). The brainstorm's R4–R6 requires cross-thread, family-wide discovery — a gap upstream doesn't fill. `thread_search` lists family sessions and matches on title and `last_message_summary`, returning thread ids for the LLM to read via `read_conversation`. Governs R4–R6.

KTD4. **Session-level search for `thread_search` v1.** Initial implementation searches session titles and `last_message_summary` client-side via `list_sessions`. Not message-level full-text search. The LLM discovers sessions by title/snippet, then reads content via `read_conversation`. Message-level FTS across family sessions is deferred.

KTD5. **Upstream thread-scoped tools stay enabled alongside `thread_search`.** Enabling `task_continuity` also exposes upstream `history_search` (current-thread messages) and `history_read` (compaction archive by `source_id`). These are complementary, not duplicates: `thread_search` finds *other sessions*, `history_search` finds within *this* session's compacted history. Tool descriptions must state each scope so the model selects correctly. Governs R4, R7.

### Assumptions

- DeerFlow upstream `task_continuity` feature is complete and functional in the installed version. The `task_notes` channel, `task_note`/`history_search`/`history_read` tools, and `DurableContextMiddleware` projection all work when `task_continuity.enabled: true`.
- The upstream `read_conversation` tool accepts a host-provided reader callable via `runtime.context["__conversation_reader"]`. When the reader is present, `include_conversation_reader` resolves to True and the tool is auto-appended.
- The upstream `task_notes` channel caps at 8 notes × 750 chars each. This is sufficient for initial use. Increasing limits requires upstream changes.
- Numina's existing `AiSessionRepository` (via `BackendClient`) provides family-scoped session listing, which `thread_search` builds on.
- The `_inject_task_continuity` function follows the same pattern as `_inject_subagent_limit` and `_inject_tool_progress` in `family_adapter_cache.py`.

---

## Implementation Units

### U1. Add `task_continuity` config block to base config

- **Goal:** Add default `task_continuity` configuration to the base DeerFlow config YAML.
- **Requirements:** R1–R3, R9
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/deerflow_config/base/config.yaml` (modify)
- **Approach:**
  1. Add a `task_continuity` block after the existing `tool_progress` block.
  2. Default `enabled: true` — all families get task continuity unless explicitly disabled.
  3. Do not add a note-count or note-length setting: upstream's `TaskNotesChannel` hardcodes the 8-notes × 750-char cap, so any such config key would have no consumer.
- **Patterns to follow:** Existing `tool_search` and `tool_progress` config blocks in the same file.
- **Test expectation:** none — config is covered by U3 injection tests.
- **Verification:** `grep -A3 task_continuity server/apps/agent/deerflow_config/base/config.yaml`

### U2. `_inject_task_continuity()` function

- **Goal:** Implement config injection following the `_inject_*` pattern, enabling per-family override.
- **Requirements:** R1–R3, R9
- **Dependencies:** U1
- **Files:**
  - `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (modify)
- **Approach:**
  1. Add `_inject_task_continuity(config, ai_config)` function after `_inject_tool_progress`.
  2. Read `ai_config.task_continuity.enabled` for explicit override (True/False/None).
  3. When override is None, use the base config default (`config["task_continuity"]["enabled"]`).
  4. Write the resolved value back to `config["task_continuity"]["enabled"]`.
  5. Call from `_generate_temp_config()` after `_inject_tool_progress` (line ~743).
- **Patterns to follow:** `_inject_subagent_limit()` and `_inject_tool_progress()` — same function signature `(config, ai_config)`, same logging pattern.
- **Test scenarios:**
  1. Default (no ai_config override): `task_continuity.enabled` resolves to `true` from base config
  2. Explicit override `true`: enabled regardless of base config
  3. Explicit override `false`: disabled regardless of base config
  4. Base config `enabled: false`, no override: disabled
  5. No regression: other `_inject_*` functions still work when called alongside `_inject_task_continuity`
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_task_continuity_injection.py -v`

### U3. Unit tests for `_inject_task_continuity`

- **Goal:** Verify threshold logic, override precedence, and edge cases.
- **Requirements:** R1–R3, R9
- **Dependencies:** U1, U2
- **Files:**
  - `server/tests/agent/unit/test_task_continuity_injection.py` (create)
- **Approach:** Follow the test structure from `test_tool_search_injection.py` (T24 plan). Each test constructs a config dict and ai_config dict, calls `_inject_task_continuity`, and asserts the resolved config.
- **Test scenarios:**
  1. Covers test for U2 scenarios 1–5 above
  2. `ai_config.task_continuity` key absent entirely: uses base config default
  3. `ai_config.task_continuity.enabled` is not a boolean (e.g., string): handled gracefully
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_task_continuity_injection.py -v`

### U4. Conversation reader callback

- **Goal:** Implement the `__conversation_reader` callable that enables upstream's `read_conversation` tool for cross-thread message access.
- **Requirements:** R7–R8, R10
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/conversation_reader.py` (create)
  - `server/tests/agent/unit/test_conversation_reader.py` (create)
- **Approach:**
  1. Create `build_conversation_reader(checkpointer, family_id)` factory returning an async callable.
  2. DeerFlow calls the reader in exactly two shapes — the callable must accept keyword arguments and handle both (`deerflow/tools/conversation.py:71,77`):
     - `reader(thread_id=..., cursor=..., limit=...)` for the initial/next page
     - `reader(thread_id=..., message_seq=..., offset=...)` for continuing a cut message
  3. Validate family ownership: look up the session via `get_session(family_id, session_id)` in `server/apps/agent/core/backend_client.py`, mapping the requested `thread_id` to its session row. Return an error payload when the thread is not in this family.
  4. Read the thread's messages from the LangGraph checkpointer (`aget`), taking `channel_values["messages"]`.
  5. Serialize to JSON, keeping `HumanMessage` and `AIMessage` only; drop tool/system messages and any message whose content is not a string.
  6. Apply pagination: `cursor`/`limit` returns the next page of messages (limit clamped to 1–50, default 20); `message_seq`/`offset` returns a slice of one message's text continuing at `offset`. Include the continuation fields the tool expects in the response.
  7. On a missing or unreadable checkpoint, return a JSON error payload rather than raising — the tool surfaces strings to the model.
- **Patterns to follow:** Message retrieval and serialization in `POST /api/threads/{id}/history` (`server/apps/agent/routers/threads.py:1175-1244`); checkpointer access in `server/apps/agent/services/compact_service.py`; upstream contract in `server/.venv/lib/python3.13/site-packages/deerflow/tools/conversation.py`.
- **Test scenarios:**
  1. Valid family thread — returns paginated messages as a JSON string
  2. Thread belonging to a different family — returns a permission error payload, no message content leaked
  3. Non-existent thread — returns a not-found error payload
  4. `cursor` + `limit` call shape — returns the correct page
  5. `message_seq` + `offset` call shape — returns the continuation slice starting at the requested offset
  6. Empty thread (no messages) — returns an empty page
  7. Thread with many messages — respects `limit`, clamped to 50
  8. Tool/system messages present — excluded from output
  9. Corrupted or missing checkpoint — returns an error payload instead of raising
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_conversation_reader.py -v`

### U5. `thread_search` tool

- **Goal:** Build a family-scoped session search tool for cross-session discovery.
- **Requirements:** R4–R6
- **Dependencies:** None
- **Files:**
  - `server/apps/agent/services/runtime/thread_search_tool.py` (create)
  - `server/tests/agent/unit/test_thread_search_tool.py` (create)
- **Approach:**
  1. Create `build_thread_search_tool(family_id)` factory returning a `StructuredTool`.
  2. The tool accepts `query: str` and optional `limit: int` (default 10, max 20).
  3. Internally calls `list_sessions(family_id, limit=limit, sort_by="updated_at", sort_order="desc")` from `server/apps/agent/core/backend_client.py`. There is no `search_sessions` method — v1 searches client-side (KTD4).
  4. Filters by case-insensitive substring match on `title` and `last_message_summary`. An empty `query` skips filtering and returns the most recent sessions.
  5. Returns a JSON string of matching sessions: `[{thread_id, title, snippet, source, updated_at}]`, where `snippet` is `last_message_summary` truncated to 200 chars (`null` when absent). This satisfies R5 without message-level search.
  6. Tool registration happens in U6 — this unit creates the module only.
- **Patterns to follow:** `StructuredTool.from_function()` as used by `deerflow/agents/task_continuity/tools.py`; `list_sessions` return shape at `server/apps/agent/core/backend_client.py:894` (`tuple[list[dict], int]`) and the `_session_to_dict` fields at `server/apps/backend/app/routers/ai_internal.py:615`.
- **Test scenarios:**
  1. Query matching a session title — returns the session with `thread_id`, `title`, `snippet`, `source`, `updated_at`
  2. Query matching only `last_message_summary` — returns the session (snippet-level matching)
  3. Query matching no sessions — returns an empty list
  4. Results scoped to family — `list_sessions` is called with the bound `family_id`; sessions from other families are never returned
  5. `limit` respected — never returns more than the requested count, and values above 20 are clamped
  6. Case-insensitive match — "Investment" matches "investment analysis"
  7. Empty query — returns the most recent sessions unfiltered
  8. Session with null `last_message_summary` — `snippet` is `null`, session still returned
  9. `list_sessions` raises (backend unavailable) — tool returns a readable error string rather than raising into the agent loop
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_thread_search_tool.py -v`

### U6. Integration wiring

- **Goal:** Connect `thread_search` and `thread_read` into the agent tool list so they are always available regardless of active skill.
- **Requirements:** R7–R10
- **Dependencies:** U4, U5
- **Files:**
  - `server/apps/agent/services/runtime/thread_read_tool.py` (create)
  - `server/tests/agent/unit/test_thread_read_tool.py` (create)
  - `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py` (modify)
- **Approach:**
  1. Implement `build_thread_read_tool(checkpointer, family_id)` that wraps `build_conversation_reader` (U4) as a `StructuredTool` named `thread_read`. The tool accepts `thread_id`, optional `cursor`, and `limit`, and returns a JSON page — the same contract the reader already produces.
  2. In `sync_tool_patch.py`, add `thread_search` and `thread_read` to `_NUMINA_ALWAYS_AVAILABLE_TOOLS`, so skill `allowed-tools` filtering never removes them.
  3. In the patched `get_available_tools`, obtain `family_id` from `get_family_sandbox_context()` (the same ContextVar the existing skill filter reads at `sync_tool_patch.py:326`). When no family context is available, skip appending the tools and log a warning; never call with an empty family.
  4. After the skill filter, append tools built by `build_thread_search_tool(family_id)` from U5 and `build_thread_read_tool(_get_shared_checkpointer(None), family_id)` from this unit.
  5. Do not attempt to enable upstream `read_conversation` — it requires host-gating machinery that does not have a clean seam through `DeerFlowClient._stream_turn` (see KTD2).
- **Patterns to follow:** `StructuredTool.from_function()` as used by `deerflow/agents/task_continuity/tools.py`; `_NUMINA_ALWAYS_AVAILABLE_TOOLS` pattern in `sync_tool_patch.py:277-281`; tool-appending pattern in `append_task_continuity_tools()`.
- **Test scenarios:**
  1. `thread_read` returns a paginated JSON page for a valid family thread
  2. `thread_read` returns a not-found error payload for a thread belonging to a different family
  3. `thread_read` returns a not-found error payload for a non-existent thread
  4. `thread_read` cursor pagination returns successive pages matching U4's pagination scheme
  5. `thread_read` clamps limit to 50
  6. `thread_read` returns an error payload on empty/invalid thread_id without raising
  7. `thread_read` factory produces a tool named `thread_read` bound to the supplied family_id
  8. `thread_read` returns a JSON error payload on checkpointer failure
  9. `thread_read` appears in the tool list when family context is present (integration with sync_tool_patch)
  10. `thread_read` survives an active skill whose `allowed-tools` omits it
  11. No family context — `thread_read` is not appended (skipped with warning)
- **Verification:** `cd server && uv run pytest tests/agent/unit/test_thread_read_tool.py tests/agent/unit/test_thread_search_tool.py -v`

---

## Verification Contract

| Check | Command | Scope |
|-------|---------|-------|
| Task continuity injection | `cd server && uv run pytest tests/agent/unit/test_task_continuity_injection.py -v` | U2, U3 |
| Conversation reader | `cd server && uv run pytest tests/agent/unit/test_conversation_reader.py -v` | U4 |
| Thread search tool | `cd server && uv run pytest tests/agent/unit/test_thread_search_tool.py -v` | U5 |
| Thread read tool | `cd server && uv run pytest tests/agent/unit/test_thread_read_tool.py -v` | U6 |
| Full agent regression | `cd server && uv run pytest tests/agent/unit/ -v` | All |
| Lint | `cd server && uv run ruff check apps/agent/services/deerflow_adapter/ apps/agent/services/runtime/thread_search_tool.py apps/agent/services/runtime/thread_read_tool.py apps/agent/services/conversation_reader.py` | Changed files |

## Definition of Done

- All six implementation units pass their verification commands
- `task_continuity.enabled` defaults to `true` in base config — task_note, history_search, history_read available to all families
- `_inject_task_continuity` follows the established `_inject_*` pattern in `family_adapter_cache.py`
- `thread_read` returns paginated family-scoped session messages, with ownership validation via the shared checkpointer
- `thread_search` returns family-scoped session results including a snippet from `last_message_summary`
- Both `thread_search` and `thread_read` are available to all skills by default (in `_NUMINA_ALWAYS_AVAILABLE_TOOLS`)
- `thread_search` and upstream `history_search` tool descriptions make their scopes distinct (KTD5)
- No regression in existing agent dispatch tests (full suite green)
- No upstream DeerFlow changes required — all work is Numina-side config, tools, and wiring

---

## Sources

**Brainstorm sources:**
- DeerFlow builtin tools: `server/.venv/lib/python*/site-packages/deerflow/tools/builtins/`
- DeerFlow `read_conversation` tool: `deerflow/tools/conversation.py`
- DeerFlow ThreadState channels: `deerflow/agents/thread_state.py`
- DeerFlow `DurableContextMiddleware`: `deerflow/agents/middlewares/durable_context_middleware.py`
- DeerFlow `TodoListMiddleware` (compaction persistence precedent): `deerflow/agents/middlewares/todo_middleware.py`
- Numina `compact_service`: `server/apps/agent/services/compact_service.py`
- Numina thread endpoints: `server/apps/agent/routers/threads.py`
- Existing T24 plan: `docs/plans/2026-11-03-1604-feat-tool-promotion-middleware-plan.md`
- Issue: [vincentruan/numina#176](https://github.com/vincentruan/numina/issues/176) — T25

**Planning research sources:**
- DeerFlow task_continuity tools: `deerflow/agents/task_continuity/tools.py` — `task_note`, `history_search`, `history_read` tool definitions using `StructuredTool.from_function()`
- DeerFlow `TaskNotesChannel` reducer: `deerflow/agents/thread_state.py:394` — max 8 notes, 750 chars each, 40-char alphanumeric keys
- DeerFlow `append_task_continuity_tools()`: called from `lead_agent/agent.py:1179,1347` — auto-appends tools when `task_continuity.enabled=True`
- DeerFlow `DurableContextMiddleware._render_durable_context_data`: projects `task_notes` + `task_history` as "Task working notes" block (capped at 12000 chars) when `task_continuity_enabled=True`
- DeerFlow `read_conversation` host-gating: requires `__conversation_reader` callable in `runtime.context`; `include_conversation_reader` parameter on `get_available_tools()` defaults to `False`. Reader call shapes verified at `deerflow/tools/conversation.py:71,77` — `(thread_id, cursor, limit)` and `(thread_id, message_seq, offset)`
- DeerFlow `history_read` signature takes `source_id` (compaction archive), not a session id — verified at `deerflow/agents/task_continuity/tools.py:44`; this is why R7–R8 map to `read_conversation` rather than `history_read`
- Numina `list_sessions`: `server/apps/agent/core/backend_client.py:894` — returns `tuple[list[dict], int]`; no `search_sessions` method exists
- Numina session fields incl. `last_message_summary` (the R5 snippet source): `server/apps/backend/app/routers/ai_internal.py:615` (`_session_to_dict`)
- Numina family context access: `get_family_sandbox_context()` at `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py:326`
- Numina `_inject_*` pattern: `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py:684-760` — `_generate_temp_config()` calls injection functions in sequence
- Numina `_NUMINA_ALWAYS_AVAILABLE_TOOLS`: `server/apps/agent/services/deerflow_adapter/sync_tool_patch.py` — tools that bypass skill `allowed-tools` filtering (currently just `"task"`)
- Numina session search: `POST /api/threads/search` in `threads.py:721-768` — queries `AiSessionRepository` by `family_id`, supports pagination and sorting
