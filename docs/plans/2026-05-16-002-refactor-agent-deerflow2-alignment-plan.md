---
title: "refactor: Agent module DeerFlow 2.0 alignment"
date: 2026-05-16
status: active
origin: docs/brainstorms/agent-deerflow2-refactor-requirements.md
type: refactor
---

# refactor: Agent module DeerFlow 2.0 alignment

**Origin:** `docs/brainstorms/agent-deerflow2-refactor-requirements.md`  
**Scope:** `server/apps/agent/` + backend schema migration for R4

---

## Problem Frame

The agent module was built on the DeerFlow 2.0 harness but drifted from its standard paths in three ways:

1. **Protocol deviation** — `adapter.py` produces custom `[THINK]`/`[TEXT]` string prefixes instead of consuming DeerFlow's native `StreamEvent` types. Both streaming consumers (`orchestrator.stream_dispatch` and `_chunk_to_event_lines`) depend on these prefixes.
2. **Capability gaps** — `DeerFlowClient` is initialized with only `config_path` + `checkpointer`; `model_name`, `subagent_enabled`, and `plan_mode` are never passed. Concurrency is hard-coded at 4 workers with a 60s default timeout. `SkillConfig` has no `subagent_enabled` or `plan_mode` fields.
3. **Isolation gaps** — All families share one DeerFlow memory file (`/app/data/deerflow-memory.json`). The JSONL session path is computed but never persisted to the backend DB, so it cannot be recovered after a restart.

---

## Success Criteria

| Requirement | Acceptance |
|-------------|-----------|
| R1: Protocol alignment | `_produce()` emits structured events; no `[THINK]`/`[TEXT]` string parsing in orchestrator |
| R2: Full DeerFlowClient params | `model_name`, `thinking_enabled`, `subagent_enabled`, `plan_mode` passed at `DeerFlowClient.__init__` time; cache key is `(family_id, config_id, subagent_enabled, plan_mode)` |
| R3: Memory isolation | Each family reads/writes its own `memory/{family_id}.json`; no cross-family bleed |
| R4: JSONL path persistence | `jsonl_path` stored in `ai_chat_sessions` table; `GET /sessions/{id}/events` resolves via DB, not `_path_cache` |
| R5: Long-task support | Concurrency 8, default timeout 120s, per-skill `subagent_enabled`/`plan_mode` flags |
| R6: Gateway API | Three internal proxy endpoints authenticated by `X-Agent-Token` |

---

## Scope Boundaries

### In scope
- `services/deerflow_adapter/adapter.py` — streaming protocol, concurrency constants
- `services/deerflow_adapter/family_adapter_cache.py` — DeerFlowClient params, memory path injection
- `services/deerflow_adapter/skill_loader.py` — new `subagent_enabled`/`plan_mode` fields
- `services/orchestrator.py` — remove `[THINK]`/`[TEXT]` prefix consumption
- `services/session_store.py` — verify `jsonl_path` wiring (already present; confirm end-to-end)
- `app/config.py` — new `DEERFLOW_CONCURRENCY`, `DEERFLOW_GATEWAY_URL` settings
- `app/routers/cache.py` — three new Gateway API proxy endpoints
- `skills/*.md` frontmatter — add `subagent_enabled`, `plan_mode` fields
- `deerflow_config/base/config.yaml` — memory path template, timeout/concurrency defaults
- Backend: Alembic migration adding `jsonl_path` to `ai_chat_sessions`; backend upsert endpoint update
- Unit tests for each changed unit

### Deferred to Follow-Up Work
- Frontend UI for Gateway API management (skill enable/disable, thread cleanup)
- APScheduler job activation (Phase 0 constraint)
- JSONL file migration to object storage (files stay on disk; only path reference is persisted)
- Postgres checkpointer migration (removing `_CHECKPOINTER_LOCK` requires Postgres checkpointer verification)
- `_CHECKPOINTER_LOCK` removal (deferred until Postgres checkpointer is confirmed safe for concurrent writes)

### Outside scope
- New AI capabilities or skills
- Frontend changes beyond Gateway API management UI (deferred above)
- New Python dependencies beyond what DeerFlow harness already provides

---

## Key Technical Decisions

**D1: Init-time `subagent_enabled`/`plan_mode` with 4-tuple LRU cache key**  
Context7 documentation confirms `DeerFlowClient.__init__` accepts `subagent_enabled` and `plan_mode` as constructor parameters; `stream(message, thread_id)` does **not** accept these as kwargs. They must be bound at client creation time. Consequently, the LRU cache key in `family_adapter_cache.py` must expand from `(family_id, config_id)` to `(family_id, config_id, subagent_enabled, plan_mode)`. For a given family, most skills use `(False, False)` so the common case still hits the same cached instance; only `report` and `time_machine` create a second instance with `(True, True)`. Cache fragmentation is bounded to at most 4 variants per family (2 flags × 2 values), which is acceptable given the LRU cap of 100 entries.

**D2: Memory isolation via per-family subdirectory path in temp config**  
`_generate_temp_config()` already injects `ai_model_id` and `api_key` into the temp YAML. Adding `memory.storage_path: {AGENT_DATA_DIR}/{family_id}/memory.json` follows the same pattern and requires no harness changes. Context7 confirms the correct YAML key is `storage_path` (not `path`). The alternative (DeerFlow Postgres namespace) is **not supported** in the current DeerFlow version — the memory system only supports file-based `storage_path`; no `namespace` or `db_url` option exists.

**D3: Structured event objects from `_produce()`**  
Instead of string prefixes, `_produce()` will put typed `StreamChunk` dataclass instances into the queue. Both consumers (raw text path and NDJSON path) switch to `isinstance` dispatch. This eliminates the string-parsing coupling without changing the queue/executor architecture.

**D4: `jsonl_path` backend wiring is already present on the agent side**  
Research confirmed `session_store.py` already passes `jsonl_path` through to `BackendClient.upsert_session()`. The gap is on the backend: the `ai_chat_sessions` table lacks the column and the upsert endpoint ignores the field. R4 is primarily a backend migration unit.

**D5: Concurrency via `AgentSettings`**  
`_EXECUTOR` and `_SEMAPHORE` are module-level constants today. Making them configurable requires lazy initialization (read settings at first use, not at import time). A `_get_executor()` / `_get_semaphore()` pattern avoids the circular-import risk of reading settings at module level.

---

## High-Level Technical Design

The streaming protocol change (R1) is the most structurally significant. Current flow vs. target:

```
Current:
  DeerFlow StreamEvent
    → adapter._produce() → "[THINK]{text}" / "{text}" strings → queue
    → orchestrator.stream_dispatch() → raw text chunks (text/plain)
    → orchestrator._chunk_to_event_lines() → NDJSON events

Target:
  DeerFlow StreamEvent
    → adapter._produce() → StreamChunk(type="thinking"|"text", content=...) → queue
    → orchestrator.stream_dispatch() → raw text (strips thinking, joins text)
    → orchestrator._chunk_to_event_lines() → NDJSON events (isinstance dispatch)
```

`StreamChunk` is a lightweight dataclass defined in `services/deerflow_adapter/adapter.py`:

```python
# Directional guidance — not implementation specification
@dataclass
class StreamChunk:
    type: Literal["thinking", "text"]
    content: str
```

*This illustrates the intended approach and is directional guidance for review, not implementation specification.*

---

## Implementation Units

### U1. Add `StreamChunk` dataclass and migrate `_produce()` to structured events

**Goal:** Replace `[THINK]`/`[TEXT]` string prefix production with typed `StreamChunk` objects in the adapter queue.

**Requirements:** R1

**Dependencies:** none

**Files:**
- `server/apps/agent/services/deerflow_adapter/adapter.py`
- `server/apps/agent/tests/conftest.py` (new — create test directory structure)
- `server/apps/agent/tests/unit/test_adapter_stream.py` (new)

**Approach:**
- Create `tests/`, `tests/unit/`, and `tests/integration/` directories with `__init__.py` files and a shared `tests/conftest.py` (mock fixtures for `DeerFlowClient` and `BackendClient`) as part of this first unit.
- Define `StreamChunk(type: Literal["thinking","text"], content: str)` dataclass at module level in `adapter.py`
- Update `_produce()`: instead of `queue.put_nowait(f"[THINK]{reasoning}")` and `queue.put_nowait(content)`, put `StreamChunk("thinking", reasoning)` and `StreamChunk("text", content)`
- Update `_async_stream_chunks()` type annotation: `queue: asyncio.Queue[StreamChunk | BaseException | None]`; yield `StreamChunk` objects instead of `str`
- Update `stream_dispatch()` return type annotation to `AsyncGenerator[StreamChunk, None]`
- `_sync_dispatch()` is unaffected (non-streaming, returns `str`)

**Patterns to follow:** Existing `StreamEvent` dataclass in `vendor/deerflow-harness/deerflow/client.py`

**Test scenarios:**
- Happy path: `_produce()` with a `messages-tuple` AI event containing plain text → yields `StreamChunk(type="text", content=...)`
- Thinking block: event with `additional_kwargs.reasoning_content` → yields `StreamChunk(type="thinking", ...)` before `StreamChunk(type="text", ...)`
- Anthropic-style thinking block: event with `content=[{"type":"thinking","thinking":"..."},{"type":"text","text":"..."}]` → yields thinking chunk then text chunk
- Empty content: event with empty string content → no chunk yielded
- Error propagation: exception in `_produce()` → `BaseException` in queue → `DeerFlowError` raised by consumer
- Timeout: `asyncio.wait_for` timeout → `DeerFlowTimeoutError`

**Verification:** `uv run pytest tests/unit/test_adapter_stream.py -v` passes; no `[THINK]` or `[TEXT]` string literals remain in `adapter.py`

---

### U2. Migrate orchestrator streaming consumers to `StreamChunk` dispatch

**Goal:** Remove `[THINK]`/`[TEXT]` string prefix parsing from both orchestrator streaming paths.

**Requirements:** R1

**Dependencies:** U1

**Files:**
- `server/apps/agent/services/orchestrator.py` (both `stream_dispatch()` raw text path lines ~360–369 and `_chunk_to_event_lines()` NDJSON path)
- `server/apps/agent/tests/unit/test_orchestrator_stream.py` (new)

**Approach:**
- `stream_dispatch()` in orchestrator (raw text/plain path, ~lines 360–369): change `async for chunk in adapter.stream_dispatch(...)` to handle `StreamChunk` objects via `isinstance` dispatch. For `type="text"` chunks, yield `chunk.content`. For `type="thinking"` chunks, skip (raw text path does not expose thinking to callers). Do not call `.startswith()` on chunks — they are no longer strings.
- `_chunk_to_event_lines()` (NDJSON path): replace `if chunk.startswith("[THINK]")` / `chunk[7:]` with `if isinstance(chunk, StreamChunk) and chunk.type == "thinking"` / `chunk.content`. Replace `chunk[6:] if chunk.startswith("[TEXT]") else chunk` with `chunk.content`.
- Remove the `[THINK]`/`[TEXT]` string constants from `stream_events.py` if they exist there.

**Patterns to follow:** Existing `EventStreamBuilder` usage in `orchestrator._chunk_to_event_lines()`

**Test scenarios:**
- NDJSON path: `StreamChunk(type="thinking", content="reasoning")` → emits `phase.thinking` + `token.stream(is_thinking=True)` NDJSON lines
- NDJSON path: `StreamChunk(type="text", content="answer")` → emits `phase.answering` + `token.stream` NDJSON lines
- Raw text path: `StreamChunk(type="text", content="answer")` → yields `"answer"` string
- Raw text path: `StreamChunk(type="thinking", content="reasoning")` → yields nothing (thinking suppressed on text/plain path)
- Mixed stream: thinking chunk followed by text chunk → correct ordering in both paths
- Empty stream: no chunks → clean end, no error

**Verification:** `uv run pytest tests/unit/test_orchestrator_stream.py -v` passes; grep for `[THINK]` and `[TEXT]` in `orchestrator.py` returns zero matches

---

### U3. Complete `DeerFlowClient` parameter set — init-time model and flags

**Goal:** Pass `model_name`, `thinking_enabled`, `subagent_enabled`, and `plan_mode` to `DeerFlowClient.__init__` at client creation time; expand LRU cache key to `(family_id, config_id, subagent_enabled, plan_mode)`.

**Requirements:** R2, R5 (partial)

**Dependencies:** U5 (must know `subagent_enabled`/`plan_mode` values before cache key can be constructed; implement U5 first or in the same PR)

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`
- `server/apps/agent/tests/unit/test_family_adapter_cache.py` (new)

**Approach:**
- Context7 confirms `DeerFlowClient.__init__` accepts `model_name`, `thinking_enabled`, `subagent_enabled`, and `plan_mode` as constructor parameters. `stream(message, thread_id)` does **not** accept these as kwargs — they must be bound at init time.
- Expand the LRU cache key from `(family_id, config_id)` to `(family_id, config_id, subagent_enabled, plan_mode)`. The `get_family_adapter()` function signature gains two new bool parameters passed in from the orchestrator (which reads them from `skill_config` after U5).
- Pass all four params to `DeerFlowClient.__init__`: `model_name=family_model_id`, `thinking_enabled=skill.thinking`, `subagent_enabled=subagent_enabled`, `plan_mode=plan_mode`.
- The current `_generate_temp_config()` block that injects `api_key` and `base_url` into `config['models']` must be retained — these have no direct constructor param path in the harness.
- `model_name` is an additional direct param that takes precedence over the config-file model name; do not remove the config-file model entry.
- `thinking_enabled` moves from `adapter.stream_dispatch()` kwarg to `DeerFlowClient.__init__` param. Remove the `thinking_enabled=enable_thinking` kwarg from `self._client.stream(...)` calls in `adapter.py` (it is now bound at init time).
- Cache fragmentation: most skills use `(False, False)` → same instance reused. Only `report` and `time_machine` create a `(True, True)` variant. Maximum 4 variants per family; LRU cap of 100 entries is not a concern.

**Patterns to follow:** Existing `(family_id, config_id)` cache key pattern in `family_adapter_cache.py`; existing `DeerFlowClient.__init__` signature from Context7 docs

**Test scenarios:**
- `model_name` passed to `DeerFlowClient.__init__` when `ai_config` contains `ai_model_id`
- `subagent_enabled=True, plan_mode=True` → new cache entry with key `(family_id, config_id, True, True)`
- `subagent_enabled=False, plan_mode=False` → cache entry with key `(family_id, config_id, False, False)`; same family with different flags → two distinct cache entries
- Cache hit: same `(family_id, config_id, subagent_enabled, plan_mode)` → returns existing client, no new `DeerFlowClient` created
- `thinking_enabled` no longer passed to `client.stream()` — confirmed absent from stream call kwargs
- Temp config `models` block still present (api_key/base_url still injected via config file)

**Verification:** `uv run pytest tests/unit/test_family_adapter_cache.py -v` passes; `DeerFlowClient` mock confirms `model_name`, `subagent_enabled`, `plan_mode` in `__init__` kwargs; `stream()` mock confirms neither flag appears in stream call kwargs

---

### U4. Per-family memory isolation via temp config injection

**Goal:** Each family reads/writes its own DeerFlow memory file; no cross-family memory bleed.

**Requirements:** R3

**Dependencies:** none

**Files:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py`
- `server/apps/agent/deerflow_config/base/config.yaml`
- `server/apps/agent/tests/unit/test_family_adapter_cache.py` (new — shares file with U3 tests)

**Approach:**
- In `_generate_temp_config()`, after injecting `api_key`/`model_id`, also set `config['memory']['storage_path']` to `{AGENT_DATA_DIR}/{family_id}/memory.json` where `AGENT_DATA_DIR` is a new `AgentSettings` field (default `{PROJECT_ROOT}/data/workspace`, added in U6). Use `family_id` from the cache key — already available in scope. The correct YAML key is `storage_path` (maps to `MemoryConfig.storage_path` in `vendor/deerflow-harness/deerflow/config/memory_config.py`), not `path` — using `path` would be silently ignored by Pydantic's model validation.
- Before calling `DeerFlowClient(...)`, ensure the memory directory exists: `Path(f"{settings.AGENT_DATA_DIR}/{family_id}/memory.json").parent.mkdir(parents=True, exist_ok=True)` — `FileMemoryStorage` does not create parent directories automatically.
- The `base/config.yaml` template keeps `memory.storage_path: /app/data/deerflow-memory.json` as the global default (used by the global singleton adapter). Per-family temp configs override this.
- On cache eviction (`_evict_entry()`), optionally retain the memory file for audit (do not delete). Add a comment explaining the retention decision.
- Validate that `family_id` passes `_SAFE_ID_PATTERN` before using it in the path (already validated upstream in `session_journal.py`; add the same check here for defense-in-depth).

**Patterns to follow:** Existing `_generate_temp_config()` YAML injection pattern in `family_adapter_cache.py`

**Test scenarios:**
- Two different `family_id` values → two different `memory.storage_path` values in their temp configs
- Same `family_id` → same `memory.storage_path` (cache hit, no new temp config)
- `family_id` with path-traversal characters (`../`, `/`) → `ValueError` raised before path construction
- Memory file path uses `{family_id}/memory.json` as a path segment under `AGENT_DATA_DIR`
- Subdirectory structure allows multiple files per family in future (e.g., `{AGENT_DATA_DIR}/{family_id}/chat_session/{session_id}.jsonl`)

**Verification:** `uv run pytest tests/unit/test_family_adapter_cache.py -v` passes; inspect temp config YAML to confirm `memory.storage_path` contains `{family_id}/memory.json` path

---

### U5. Add `subagent_enabled` and `plan_mode` to `SkillConfig` and skill frontmatter

**Goal:** Per-skill `subagent_enabled` and `plan_mode` flags readable by the orchestrator.

**Requirements:** R5

**Dependencies:** U2 (orchestrator StreamChunk dispatch must exist before wiring skill flags through); U3 depends on U5 (cache key needs flag values — implement U5 before or together with U3)

**Files:**
- `server/apps/agent/services/deerflow_adapter/skill_loader.py`
- `server/apps/agent/skills/alerts.md`
- `server/apps/agent/skills/allocation.md`
- `server/apps/agent/skills/chat.md`
- `server/apps/agent/skills/disposal.md`
- `server/apps/agent/skills/liability.md`
- `server/apps/agent/skills/report.md`
- `server/apps/agent/skills/spending_leak.md`
- `server/apps/agent/skills/time_machine.md`
- `server/apps/agent/tests/unit/test_skill_loader.py` (new)

**Approach:**
- Add `subagent_enabled: bool = False` and `plan_mode: bool = False` to `SkillConfig` dataclass in `skill_loader.py`.
- Update `SkillLoader.load()` to read these fields from frontmatter (default `False` if absent — backward compat).
- Add `subagent_enabled: false` and `plan_mode: false` to all existing `skills/*.md` frontmatter. Set `subagent_enabled: true` and `plan_mode: true` on `report.md` and `time_machine.md` (long-cycle skills per requirements).
- Orchestrator reads `skill_config.subagent_enabled` and `skill_config.plan_mode` and passes them to `get_family_adapter(family_id, ai_config, subagent_enabled, plan_mode)` (wired in U3) — not to `adapter.stream_dispatch()`.

**Patterns to follow:** Existing `thinking: bool` field in `SkillConfig` and frontmatter

**Test scenarios:**
- Skill file with `subagent_enabled: true` → `SkillConfig.subagent_enabled == True`
- Skill file without `subagent_enabled` key → `SkillConfig.subagent_enabled == False` (default)
- `report.md` and `time_machine.md` → both flags `True`
- All other skills → both flags `False`
- `plan_mode: true` without `subagent_enabled: true` → valid, both read independently

**Verification:** `uv run pytest tests/unit/test_skill_loader.py -v` passes; `report.md` and `time_machine.md` frontmatter confirmed with both flags `true`

---

### U6. Configurable concurrency and timeout via `AgentSettings`

**Goal:** `_EXECUTOR` and `_SEMAPHORE` read from settings; default timeout raised to 120s; `DEERFLOW_GATEWAY_URL` added.

**Requirements:** R5, R6 (partial)

**Dependencies:** none

**Files:**
- `server/apps/agent/app/config.py`
- `server/apps/agent/services/deerflow_adapter/adapter.py`
- `server/apps/agent/tests/unit/test_adapter_concurrency.py` (new)

**Approach:**
- Add to `AgentSettings`: `AGENT_DATA_DIR: str = "{PROJECT_ROOT}/data/workspace"`, `DEERFLOW_CONCURRENCY: int = 8`, `DEERFLOW_DEFAULT_TIMEOUT: int = 120`, `DEERFLOW_GATEWAY_URL: str = "http://localhost:8001"`. The `AGENT_DATA_DIR` is used by U4 for per-family memory path construction and by U7 for session JSONL storage.
- In `adapter.py`, replace module-level `_EXECUTOR = ThreadPoolExecutor(max_workers=4)` and `_SEMAPHORE = asyncio.Semaphore(4)` with lazy-initialized module-level variables and `_get_executor()` / `_get_semaphore()` accessors. To avoid a concurrent-init race (two coroutines both seeing `None` before first init completes), initialize under a `threading.Lock` (same pattern as `_get_shared_checkpointer` in `family_adapter_cache.py`). The semaphore must be created in the event loop that will use it — initialize it on first call from within an async context, or initialize eagerly during app startup in `main.py` lifespan.
- Replace the hard-coded `timeout_seconds=120` default in `_make_adapter()` with `settings.DEERFLOW_DEFAULT_TIMEOUT`.
- The `_CHECKPOINTER_LOCK` remains unchanged (SQLite serialization still required).

**Patterns to follow:** Existing `AgentSettings` pydantic-settings pattern in `app/config.py`

**Test scenarios:**
- `DEERFLOW_CONCURRENCY=8` env var → `_get_executor()` returns `ThreadPoolExecutor(max_workers=8)`
- `DEERFLOW_CONCURRENCY` not set → defaults to 8
- `DEERFLOW_DEFAULT_TIMEOUT=300` → adapter `_timeout` uses 300
- `DEERFLOW_GATEWAY_URL` readable from settings

**Verification:** `uv run pytest tests/unit/test_adapter_concurrency.py -v` passes; `grep -n "max_workers=4" adapter.py` returns zero matches

---

### U7. Backend: Wire `jsonl_path` through the upsert endpoint

**Goal:** Ensure the backend upsert endpoint reads and persists `jsonl_path` (file path reference only, not session content) from the agent's request payload so sessions can be recovered after restart. Session events are stored exclusively in local JSONL files, never in the database.

**Requirements:** R4

**Dependencies:** none (independent backend change)

**Files:**
- `server/apps/backend/app/models/ai_chat_session.py` (verify `jsonl_path` field is `String(512)` — already present per ORM model)
- `server/apps/backend/app/routers/<ai_chat_or_ai_internal>.py` (upsert endpoint — confirm exact router file at implementation time; verify it reads and persists `jsonl_path` from request body)
- `server/apps/backend/tests/test_ai_sessions.py` (new)

**Approach:**
- No Alembic migration needed — `jsonl_path` column already exists in `ai_chat_sessions` as `String(512)`.
- Confirm the upsert endpoint handler reads `jsonl_path` from the request body and writes it to the ORM model. The `jsonl_path` is a **file path reference only** (e.g., `/data/workspace/{family_id}/chat_session/{session_id}.jsonl`), not the actual session content.
- **Important:** Session event data is stored **exclusively in local JSONL files** written by `SessionJournalService` in the agent module. The database only stores the file path reference (`jsonl_path`), never the session content itself.
- The agent's `session_store.py` always passes a non-empty `jsonl_path` on session creation (it does — `write_session_start` sets the path before the first upsert). This path is constructed as `{AGENT_DATA_DIR}/{family_id}/chat_session/{session_id}.jsonl` where `AGENT_DATA_DIR` comes from `AgentSettings` (added in U6).
- `GET /sessions/{id}/events` endpoint: reads `jsonl_path` from the DB row, locates the JSONL file on disk, and streams events from that file. No fallback to computed path needed since the column is the authoritative source.
- Write failure (DB unavailable) is silent — log WARNING, do not block the main flow (per NFR). The JSONL file on disk is the source of truth for session events.
- **No persistence of session content to DB:** The database table `ai_chat_sessions` only contains metadata (session_id, family_id, jsonl_path, created_at, etc.), never the actual conversation events. This design keeps the database lightweight and allows session data to tolerate DB failures.

**Patterns to follow:** Existing upsert handler pattern in the backend router; existing `ai_chat_sessions` ORM model

**Test scenarios:**
- Upsert with `jsonl_path` set → column persisted in DB as file path reference (e.g., `/data/workspace/{family_id}/chat_session/{session_id}.jsonl`)
- Upsert called twice for same session → second call does not overwrite `jsonl_path` (path is set once at session start)
- `GET /sessions/{id}/events` → reads `jsonl_path` from DB, opens file from disk, returns events from JSONL file
- Missing `jsonl_path` in upsert request → 422 validation error (path reference required)
- JSONL file contains actual session events; DB `ai_chat_sessions` table never contains conversation content
- DB failure during upsert → JSONL file still exists on disk as source of truth; WARNING logged, main flow continues

**Verification:** `uv run pytest tests/test_ai_sessions.py -v` passes; confirm no Alembic migration is generated by `alembic revision --autogenerate` (column already present)

---

### U8. Gateway API proxy endpoints

**Goal:** Three internal proxy endpoints that forward to DeerFlow Gateway API, authenticated by `X-Agent-Token`.

**Requirements:** R6

**Dependencies:** U6 (for `DEERFLOW_GATEWAY_URL` setting)

**Files:**
- `server/apps/agent/app/routers/cache.py` (extend, or new `app/routers/gateway.py`)
- `server/apps/agent/tests/unit/test_gateway_router.py` (new)

**Approach:**
- Add three endpoints to `cache.py` (or a new `gateway.py` router registered in `app/main.py`):
  - `GET /internal/models` → proxy `GET {DEERFLOW_GATEWAY_URL}/api/models`
  - `PUT /internal/skills/{name}` → proxy `PUT {DEERFLOW_GATEWAY_URL}/api/skills/{name}` with request body forwarded
  - `DELETE /internal/threads/{id}` → proxy `DELETE {DEERFLOW_GATEWAY_URL}/api/threads/{id}`
- All three require `X-Agent-Token` header (same auth as existing `/internal/cache/invalidate/{family_id}`).
- Use `httpx.AsyncClient` for the proxy calls (already used in `core/backend_client.py`). Propagate non-2xx responses as `HTTPException` with the upstream status code.
- `DEERFLOW_GATEWAY_URL` from `AgentSettings` (added in U6).
- Skill name and thread ID are path parameters — validate against `_SAFE_ID_PATTERN` before forwarding to prevent SSRF via path traversal.

**Patterns to follow:** Existing `POST /internal/cache/invalidate/{family_id}` in `app/routers/cache.py`; `BackendClient` httpx usage in `core/backend_client.py`

**Test scenarios:**
- `GET /internal/models` with valid token → proxies to gateway, returns model list
- `GET /internal/models` without token → 401
- `PUT /internal/skills/chat` with valid token and body → proxies PUT to gateway
- `DELETE /internal/threads/abc123` with valid token → proxies DELETE to gateway
- Gateway returns 404 → endpoint returns 404 (status propagated)
- Gateway unreachable → 502 or 503 with error detail
- Skill name with path traversal (`../admin`) → 422 validation error before proxy call

**Verification:** `uv run pytest tests/unit/test_gateway_router.py -v` passes; `GET /internal/models` returns 401 without token in integration smoke test

---

### U9. End-to-end integration test and CLAUDE.md update

**Goal:** Verify the full dispatch pipeline with the new protocol; update module docs to reflect new env vars and patterns.

**Requirements:** All (verification)

**Dependencies:** U1–U8

**Files:**
- `server/apps/agent/tests/integration/test_deerflow2_alignment.py` (new)
- `server/apps/agent/CLAUDE.md` (update)
- `server/apps/agent/deerflow_config/HARNESS_API.md` (update)

**Approach:**
- Integration test: mock `DeerFlowClient.stream()` to emit `StreamEvent(type="messages-tuple", data={"type":"ai","content":"hello"})` and `StreamEvent(type="end", data={"usage":{}})`. Assert that `orchestrator.stream_dispatch_events()` yields correct NDJSON events with no `[THINK]`/`[TEXT]` strings anywhere in the output.
- Integration test: mock `DeerFlowClient.stream()` to emit a thinking block. Assert NDJSON output contains `phase.thinking` event.
- Update `CLAUDE.md`: add `DEERFLOW_CONCURRENCY`, `DEERFLOW_DEFAULT_TIMEOUT`, `DEERFLOW_GATEWAY_URL` to the environment variables table; update streaming protocols section to remove `[THINK]`/`[TEXT]` mention; add `subagent_enabled`/`plan_mode` to the unified skill schema example.
- Update `HARNESS_API.md`: document `model_name`, `subagent_enabled`, `plan_mode` as init-time constructor params; document 4-tuple cache key pattern; document per-family memory path pattern.

**Test scenarios:**
- Full pipeline: `StreamEvent(messages-tuple, ai, text)` → NDJSON `token.stream` event, no prefix strings
- Full pipeline: `StreamEvent(messages-tuple, ai, thinking block)` → NDJSON `phase.thinking` + `token.stream(is_thinking=True)`
- Full pipeline: `StreamEvent(end)` → NDJSON `capability.end` event
- `subagent_enabled=True` from skill config → passed to `get_family_adapter()` as init-time param; `DeerFlowClient.__init__` mock confirms flag in constructor kwargs

**Verification:** `uv run pytest tests/integration/test_deerflow2_alignment.py -v` passes; `grep -rn "\[THINK\]\|\[TEXT\]" server/apps/agent/services/` returns zero matches

---

## Sequencing

```
U1 (StreamChunk dataclass + _produce migration)
  └─ U2 (orchestrator consumers)
       └─ U5 (SkillConfig flags) ─┐
                                   ├─ U3 (DeerFlowClient init-time params + 4-tuple cache key)
U4 (memory isolation) ─────────────┘   (U5 must exist so orchestrator can pass flags to get_family_adapter)

U6 (AgentSettings: AGENT_DATA_DIR, concurrency, timeout, gateway URL)
  ├─ U4 (reads AGENT_DATA_DIR — implement U6 first or add setting inline)
  └─ U8 (Gateway API endpoints)

U7 (backend jsonl_path wiring) — independent

U1 + U2 + U3 + U4 + U5 + U6 + U7 + U8
  └─ U9 (integration test + docs)
```

Parallel tracks: `{U1→U2→U5→U3}`, `{U4}`, `{U6→U8}`, `{U7}` can proceed concurrently. U5 gates on U2 (StreamChunk dispatch must exist). U3 gates on U5 (needs flag values for cache key). U9 gates on all prior units.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| `model_name` direct param not honored by harness at runtime | Low (confirmed in vendor source) | High | Fallback to temp config injection (NFR); unit test with real harness mock |
| `subagent_enabled`/`plan_mode` init-time binding causes stale client reuse when skill flags change | Low | Medium | 4-tuple cache key `(family_id, config_id, subagent_enabled, plan_mode)` ensures flag changes always create a new client instance |
| Per-family memory file path causes DeerFlow to fail on first write (dir not created) | Medium | Low | `Path(memory_path).parent.mkdir(parents=True, exist_ok=True)` before client init |
| Backend `jsonl_path` field present in ORM model but ignored by upsert endpoint handler | Medium | Medium | U7 explicitly verifies handler reads and persists the field; integration test confirms round-trip read from DB |
| Concurrency increase from 4→8 causes SQLite `SQLITE_BUSY` under load | Medium | Medium | `_CHECKPOINTER_LOCK` remains; streaming calls don't hold it; monitor in staging |
| Gateway proxy SSRF via crafted skill name or thread ID | Low | High | Path-segment validation against `_SAFE_ID_PATTERN` before forwarding |

---

## Deferred Implementation Notes

- ~~Exact YAML key path for `memory.path` in DeerFlow config~~ — **Confirmed:** key is `storage_path` in `MemoryConfig` (`vendor/deerflow-harness/deerflow/config/memory_config.py`). U4 uses `config['memory']['storage_path']`.
- ~~DeerFlow Postgres namespace for memory~~ — **Confirmed not supported:** Context7 docs show memory only supports file-based `storage_path`; no `namespace` or `db_url` option exists. U4's file-path approach is the only viable path.
- ~~`subagent_enabled`/`plan_mode` per-dispatch via `stream()` kwargs~~ — **Confirmed init-time only:** Context7 docs confirm these are `DeerFlowClient.__init__` parameters; `stream(message, thread_id)` accepts no additional kwargs. Cache key must be 4-tuple `(family_id, config_id, subagent_enabled, plan_mode)`.
- Memory directory pre-creation: `FileMemoryStorage` does not create parent directories — `Path(...).parent.mkdir(parents=True, exist_ok=True)` must be called in `_generate_temp_config()` before client init (noted in U4 approach).
- Exact backend router file for `ai_chat_sessions` upsert endpoint — confirm at implementation time by reading `server/apps/backend/app/routers/`; likely `ai_internal.py` or `ai_chat.py`.
- Whether `_CHECKPOINTER_LOCK` can be removed after Postgres checkpointer is confirmed — deferred to a follow-up plan.
- U6 lazy-init: `_get_semaphore()` must be initialized exactly once. Use `threading.Lock` guard or initialize eagerly in `main.py` lifespan before first request. Confirm the chosen pattern in implementation.
- `reload_app_config()` singleton race (pre-existing): each `get_family_adapter()` call under `_init_lock` calls `reload_app_config()`, which overwrites the global `_memory_config` singleton. With per-family `storage_path` injection, concurrent family initializations could overwrite each other's memory config before `_ensure_agent()` completes. Investigate whether `_init_lock` (which serializes family cache misses) is sufficient to prevent this, or whether a deeper fix is needed.
- `_SAFE_ID_PATTERN` (`^[A-Za-z0-9_\-]+$`) blocks `.` — UUID thread IDs (containing `-`) pass; skill names (lowercase alpha + underscore) pass. Pattern is safe for U8 SSRF mitigation as-is.
