---
title: Migrate AI Chat History to JSONL Storage with File Backup Integration
type: feat
status: active
date: 2026-04-20
origin: docs/brainstorms/2026-04-20-008-chat-history-jsonl-requirements.md
---

# Migrate AI Chat History to JSONL Storage with File Backup Integration

## Overview

Migrate AI chat conversation history from full SQLite storage (`ai_chat_messages` table) to per-session JSONL files. The database will store only session metadata (file path, message count, preview). JSONL files will integrate with the existing file backup module (`CachedFile` + `FileRemoteLocation`) for automatic remote sync. Session IDs will align with DeerFlow's `thread_id` for conversation state continuity.

## Problem Frame

Current `ai_chat_messages` table stores every message's full content in SQLite TEXT columns. As conversation history grows, this causes:
- **DB bloat** — message content accumulates in the database
- **Poor portability** — conversation history cannot be independently backed up or migrated
- **DeerFlow misalignment** — chat router bypasses DeerFlow's session framework (generates fresh `thread_id` per request)

The requirements document (see origin) defines the target architecture: JSONL files as the single source of truth for message content, DB as session index, and integration with existing file backup infrastructure.

## Requirements Trace

- R1. DB stores only session metadata, not message content (see origin: section "目标")
- R2. Each session corresponds to one JSONL file with one message per line (see origin: section "JSONL 文件格式")
- R3. `session_id` aligns with DeerFlow `thread_id` for state continuity (see origin: section "DeerFlow 集成")
- R4. JSONL files register as `CachedFile` entries and sync via existing backup module (see origin: section "文件备份互通")
- R5. Existing messages migrate to legacy JSONL files during Alembic upgrade (see origin: section "迁移策略")
- R6. API maintains backward compatibility — endpoints work without `session_id` (see origin: section "向后兼容")

## Scope Boundaries

- Only covers chat conversation history — other agent capabilities (report, suggest, alerts) remain unchanged
- No cross-session full-text search in this iteration
- No new backup infrastructure — reuses existing `StorageService` and sync scheduler
- No changes to DeerFlow checkpointer internals — only passes stable `thread_id`

## Context & Research

### Relevant Code and Patterns

**Current state:**
- `backend/app/models/ai_chat_message.py` — flat message table with `family_id`, `role`, `content`, `status`, `created_at`
- `backend/app/routers/ai_chat.py` — 4 endpoints: POST chat, GET history, DELETE history, PUT read
- `agent/services/deerflow_adapter/adapter.py` — accepts `thread_id` but orchestrator generates fresh UUID per request
- `backend/app/services/storage/service.py` — `upload_file()` handles image uploads with SHA256 dedup, `CachedFile` registration, and `FileRemoteLocation` queueing

**File backup patterns:**
- 4-table schema: `storage_backends`, `cached_files`, `file_remote_locations`, `sync_events`
- `CachedFile.local_path` stores absolute path, `date_dir` for organization (yyyyMMdd)
- APScheduler sync job picks up `sync_status="pending"` rows and syncs to remote backends
- SHA256 dedup per family via `UNIQUE(sha256, family_id)` constraint

**Alembic patterns:**
- Guard table creation with `if 'table_name' not in inspector.get_table_names()`
- Use `sa.text("'value'")` for string server defaults
- Always run `uv run alembic upgrade head` before app start (see institutional learnings)

### Institutional Learnings

- **File storage abstraction** (docs/solutions/best-practices/file-storage-abstraction-2026-04-10.md):
  - Cache backend instances by config hash to avoid connection pool leaks
  - Use `max_instances=1` for APScheduler sync jobs to prevent concurrent runs
  - Use dedicated `STORAGE_ENCRYPTION_KEY` env var, never derive from `SECRET_KEY`
  - In tests, capture ORM object IDs before async jobs run, then re-query by ID after

- **DeerFlow harness integration** (docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md):
  - `_CHECKPOINTER_LOCK` must be acquired in async context before `run_in_executor`
  - SQLite checkpointer requires `asyncio.Lock` to prevent `SQLITE_BUSY` errors

- **Alembic deployment order** (docs/solutions/best-practices/gamified-child-system-architecture-2026-04-17.md):
  - `Base.metadata.create_all()` creates tables for fresh installs but does NOT apply migrations
  - Always run `uv run alembic upgrade head` before starting the app
  - Skipping this causes `OperationalError: no such column` on newly added columns

### External References

None — this is a data storage refactor following established codebase patterns.

## Key Technical Decisions

1. **JSONL file path outside static mount**: Store at `./data/chat/{family_id}/{session_id}.jsonl` (not under `UPLOAD_DIR`) to avoid exposing conversation history via static file URLs. Add `CHAT_DIR` config key.

2. **Session ID = thread_id**: Use the same UUID for both `ai_chat_sessions.id` and DeerFlow `thread_id`. Backend generates stable session ID on first message, passes it to agent via new `X-Thread-Id` header.

3. **Backward compatibility via optional session_id**: All endpoints accept optional `session_id` query param. When omitted, default to the family's most recent session (or create new session on POST).

4. **Keep ai_chat_messages table for migration**: Don't drop the table — mark it as deprecated in code comments. Alembic migration backfills existing messages into `legacy_{family_id}.jsonl` files and creates corresponding `ai_chat_sessions` rows.

5. **JSONL registration as CachedFile**: Create `CachedFile` row for each JSONL file with `mime_type="application/x-ndjson"`. `AIChatSession` stores `cached_file_id` FK to locate the row for updates. SHA256 is recomputed after each append and the existing `CachedFile` row is updated in-place (no new row). `CachedFile.user_id` is populated from the session's `user_id` (NOT NULL constraint). Remote sync is opt-in via `CHAT_ENABLE_REMOTE_SYNC: bool = False` (default off) to protect conversation privacy.

6. **Agent router receives thread_id**: Backend passes `X-Thread-Id: {session_id}` header to agent. Agent router extracts it and passes to `orchestrator.dispatch(thread_id=...)`. The orchestrator's existing `thread_id=audit_id` hardcode (line ~113 of `orchestrator.py`) must be replaced with the caller-supplied value — this is the load-bearing change for DeerFlow session continuity.

7. **Path safety**: `family_id` and `session_id` must be validated as UUID format before constructing any file path. Use `Path.resolve()` and verify the result is under `CHAT_DIR` to prevent path traversal. All session queries must filter by `current_user.family_id` — this is a security invariant.

8. **File locking is async-safe**: JSONL append runs in `asyncio.run_in_executor` (matching the DeerFlow adapter pattern) so the synchronous `filelock` lock does not block the event loop. The DB commit happens inside the executor call, after the file write, so lock scope covers both operations.

## Open Questions

### Resolved During Planning

- **Q: Should JSONL files be under UPLOAD_DIR?**  
  A: No — `UPLOAD_DIR` is mounted as static files at `/uploads`. JSONL files contain conversation history and should not be publicly accessible. Use separate `CHAT_DIR = "./data/chat"`.

- **Q: How to handle concurrent message appends to the same JSONL file?**  
  A: Use `filelock` library (cross-platform) inside `asyncio.run_in_executor` so the synchronous lock does not block the event loop. DB commit happens inside the executor after the file write, so both operations are covered by the lock scope.

- **Q: Should `thread_id` be a separate column on `AIChatSession`?**  
  A: No — use `session.id` directly as the DeerFlow `thread_id`. A separate column adds no value and creates confusion about when they diverge (they never will in this design).

- **Q: Should JSONL files sync to remote backends by default?**  
  A: No — conversation history is sensitive (family financial data). Default `CHAT_ENABLE_REMOTE_SYNC=False`. Users must explicitly opt in.

- **Q: How to handle `CachedFile.user_id` NOT NULL constraint for legacy sessions?**  
  A: Check whether `CachedFile.user_id` is actually NOT NULL in the current schema. If it is, either: (a) make it nullable via a separate Alembic migration before the backfill migration, or (b) set `user_id` to the first adult member of the family during backfill. Implementer should verify the constraint and choose the simpler path.

- **Q: Should we drop ai_chat_messages table after migration?**  
  A: No — keep it as deprecated for rollback safety. Mark with code comment: `# DEPRECATED: Messages now stored in JSONL files. This table is kept for migration rollback only.`

### Deferred to Implementation

- **Exact SHA256 update strategy**: Decide whether to recompute SHA256 of entire JSONL file after each append (simple but I/O-heavy) or maintain incremental hash state (complex but efficient). Start with full recompute; optimize if profiling shows it's a bottleneck.

- **JSONL file rotation**: If a session grows very large (e.g., 10,000+ messages), consider splitting into multiple JSONL files. Defer until we see real usage patterns.

- **Cross-session search**: Full-text search across all sessions would require indexing. Out of scope for this iteration — document as future consideration.

## Implementation Units

- [ ] **Unit 1: Add CHAT_DIR config and create ai_chat_sessions table**

**Goal:** Introduce `CHAT_DIR` config key and create the new `ai_chat_sessions` table via Alembic migration.

**Requirements:** R1

**Dependencies:** None

**Files:**
- Modify: `backend/app/config.py`
- Create: `backend/alembic/versions/XXXX_add_chat_sessions_table.py`
- Create: `backend/app/models/ai_chat_session.py`

**Approach:**
- Add `CHAT_DIR: str = "./data/chat"` to `Settings` class in `config.py`
- Add `CHAT_ENABLE_REMOTE_SYNC: bool = False` to `Settings` (default off for privacy — conversation history should not sync to remote backends unless explicitly enabled)
- Add startup validation: verify `CHAT_DIR` is not under `UPLOAD_DIR` (raise `RuntimeError` if it is)
- Create Alembic migration with `inspector.get_table_names()` guard (follows existing pattern)
- Define `AIChatSession` model with fields: `id` (String 36, PK), `family_id` (String 36, FK), `user_id` (String 36, FK, nullable), `cached_file_id` (String 36, FK to `cached_files.id`, nullable), `jsonl_path` (String 500, relative to `CHAT_DIR`), `message_count` (Integer, default 0), `last_preview` (Text, nullable), `created_at`, `updated_at`
- Remove `thread_id` field — use `id` directly as the DeerFlow thread ID (no need for separate column)
- Add deprecation comment to `ai_chat_message.py`: `# DEPRECATED: Messages now stored in JSONL files. This table is kept for migration rollback only.`

**Patterns to follow:**
- `backend/app/models/cached_file.py` — model structure with `family_id` FK and path fields
- `backend/alembic/versions/c21c36dc5fbf_add_file_storage_tables.py` — migration guard pattern

**Test scenarios:**
- Happy path: Migration creates `ai_chat_sessions` table with correct schema
- Edge case: Migration runs successfully on fresh DB (table doesn't exist) and existing DB (table already exists via `create_all`)
- Integration: `AIChatSession` model can be imported and queried via SQLAlchemy session

**Verification:**
- `uv run alembic upgrade head` completes without errors
- `backend/tests/test_models.py` can create and query `AIChatSession` instances
- `CHAT_DIR` config value is accessible via `settings.CHAT_DIR`

---

- [ ] **Unit 2: Create ChatSessionService for JSONL file operations**

**Goal:** Implement service layer for JSONL file append, read, and `CachedFile` registration.

**Requirements:** R2, R4

**Dependencies:** Unit 1

**Files:**
- Create: `backend/app/services/chat_session.py`
- Test: `backend/tests/test_chat_session_service.py`

**Approach:**
- `ChatSessionService.append_message(session: AIChatSession, role: str, content: str, user: User, db: Session)`:
  - **Path safety**: Validate `session.family_id` and `session.id` are valid UUIDs (36 chars, alphanumeric + hyphens only)
  - Construct absolute path: `resolved = Path(CHAT_DIR).resolve() / session.family_id / f"{session.id}.jsonl"`
  - Verify `resolved.is_relative_to(Path(CHAT_DIR).resolve())` — raise `ValueError` if not (path traversal protection)
  - Run the following in `asyncio.run_in_executor` (sync file I/O must not block event loop):
    - Acquire file lock using `filelock` library (cross-platform)
    - Append JSON line: `{"message_id": uuid, "role": role, "content": content, "timestamp": ISO8601}\n`
    - Update `session.message_count += 1`
    - If `role == "assistant"`, update `session.last_preview = content[:100]`
    - Recompute SHA256 of entire JSONL file
    - If `session.cached_file_id` is NULL (first append):
      - Insert `CachedFile` row with `user_id=user.id`, `family_id=session.family_id`, SHA256, `mime_type="application/x-ndjson"`, `local_path` (absolute)
      - Set `session.cached_file_id = cached_file.id`
      - If `settings.CHAT_ENABLE_REMOTE_SYNC` is True AND default `StorageBackend` exists, insert `FileRemoteLocation(sync_status="pending")`
    - Else (subsequent appends):
      - Load existing `CachedFile` by `session.cached_file_id`
      - Update `CachedFile.sha256` and `size_bytes` in-place (no new row)
    - Commit DB transaction (inside executor, after file write and lock release)

- `ChatSessionService.read_messages(session: AIChatSession) -> list[dict]`:
  - **Path safety**: Validate and resolve path (same as `append_message`)
  - Read JSONL file line by line
  - Parse each line as JSON (wrap in `try/except json.JSONDecodeError` to skip partial lines)
  - Return list of message dicts in ascending order by timestamp (JSONL files are append-only, so file order = time order)

- `ChatSessionService.create_session(family_id: str, user_id: str, db: Session) -> AIChatSession`:
  - **Path safety**: Validate `family_id` is a valid UUID
  - Generate new UUID for `session_id` using `uuid.uuid4()`
  - Set `jsonl_path = f"{family_id}/{session_id}.jsonl"` (relative to `CHAT_DIR`)
  - Construct absolute path and verify it's under `CHAT_DIR` (same validation as `append_message`)
  - Create directory `{CHAT_DIR}/{family_id}/` if not exists
  - Create empty JSONL file at the resolved path
  - Insert `AIChatSession` row with `cached_file_id=None` (will be set on first append)
  - Return session object

**Patterns to follow:**
- `backend/app/services/storage/service.py` — SHA256 computation, `CachedFile` registration, `FileRemoteLocation` queueing
- Use `filelock` library for cross-platform file locking (add to `pyproject.toml` dependencies)

**Test scenarios:**
- Happy path: `create_session` creates directory, empty JSONL file, and DB row
- Happy path: `append_message` writes valid JSON line, updates `message_count` and `last_preview`
- Happy path: `read_messages` parses JSONL file and returns list of dicts
- Edge case: `append_message` handles concurrent writes via file lock (spawn 2 threads appending to same session)
- Edge case: `read_messages` returns empty list for new session (empty JSONL file)
- Integration: `append_message` creates `CachedFile` row with correct SHA256 and `mime_type="application/x-ndjson"`
- Integration: `append_message` creates `FileRemoteLocation(sync_status="pending")` when default backend exists

**Verification:**
- All test scenarios pass
- JSONL files are valid (each line is parseable JSON)
- `CachedFile` rows have correct SHA256 matching actual file content

---

- [ ] **Unit 3: Update ai_chat router to use sessions and JSONL storage**

**Goal:** Modify `POST /ai/chat`, `GET /ai/chat/history`, `DELETE /ai/chat/history` to use `ChatSessionService` and support optional `session_id` param.

**Requirements:** R2, R6

**Dependencies:** Unit 2

**Files:**
- Modify: `backend/app/routers/ai_chat.py`
- Modify: `backend/app/schemas/ai_chat.py` (if exists, otherwise create)
- Test: `backend/tests/test_ai_chat_router.py` (create new file)

**Approach:**

**POST /ai/chat**:
- Accept optional `session_id` in request body (add to `ChatRequest` schema)
- **Security**: If `session_id` provided, load session with `filter_by(id=session_id, family_id=current_user.family_id)` — MUST filter by family_id to prevent cross-family access
- If not found, return 404
- If `session_id` not provided, query for family's most recent session (filter by `family_id`, order by `created_at DESC`); if none exists, create new session via `ChatSessionService.create_session(current_user.family_id, current_user.id, db)`
- Call `ChatSessionService.append_message(session, "user", question, current_user, db)` (pass `current_user` for `CachedFile.user_id`)
- Call agent with `X-Thread-Id: {session.id}` header (use session.id directly as thread_id)
- On success, call `ChatSessionService.append_message(session, "assistant", answer, current_user, db)`
- Return `{question, answer, message_id, session_id}`

**GET /ai/chat/history**:
- Accept optional `session_id` query param
- **Security**: If `session_id` provided, load session with `filter_by(id=session_id, family_id=current_user.family_id)` — MUST filter by family_id
- If not found, return 404
- If `session_id` not provided, load family's most recent session (filter by `family_id`); if none exists, return empty list
- Call `ChatSessionService.read_messages(session)`
- Apply `limit` to returned messages (slice last N messages from the end — `messages[-limit:]`)
- Return list of messages in ascending order by timestamp (matches existing behavior: file is already in ascending order)

**DELETE /ai/chat/history**:
- Accept optional `session_id` query param
- **Security**: If `session_id` provided, verify it belongs to `current_user.family_id` before deleting
- If `session_id` not provided, delete all sessions for the family (filter by `family_id`)
- For each session:
  - If `session.cached_file_id` is not NULL:
    - Soft-delete `CachedFile` via `deleted_at = datetime.utcnow()`
    - If `FileRemoteLocation` rows exist, update `sync_status = "deleted"` to prevent sync scheduler from syncing deleted files
  - Delete `AIChatSession` row
  - Optionally delete physical JSONL file (or leave for manual cleanup)
- Return `{ok: True}`

**Patterns to follow:**
- Existing `ai_chat.py` router structure — keep same endpoint paths and auth dependencies
- `backend/app/routers/assets.py` — optional query param pattern for filtering

**Test scenarios:**
- Happy path: POST without `session_id` creates new session and appends messages
- Happy path: POST with valid `session_id` appends to existing session
- Happy path: GET without `session_id` returns messages from most recent session
- Happy path: GET with valid `session_id` returns messages from that session
- Happy path: DELETE without `session_id` deletes all family sessions
- Happy path: DELETE with valid `session_id` deletes only that session
- Error path: POST with invalid `session_id` returns 404
- Error path: GET with invalid `session_id` returns 404
- Edge case: GET on family with no sessions returns empty list
- Edge case: POST creates new session when family has no sessions
- Integration: POST passes `X-Thread-Id` header to agent (mock httpx call and assert header)
- Integration: DELETE soft-deletes `CachedFile` via `deleted_at` timestamp

**Verification:**
- All test scenarios pass
- JSONL files contain correct message sequence after multiple POST calls
- `session_id` is returned in POST response and can be used in subsequent GET/DELETE calls
- Agent receives `X-Thread-Id` header matching `session.thread_id`

---

- [ ] **Unit 4: Update agent router to accept and forward thread_id**

**Goal:** Modify agent's `POST /chat/ask` to accept `X-Thread-Id` header and pass it to orchestrator for DeerFlow continuity.

**Requirements:** R3

**Dependencies:** Unit 3

**Files:**
- Modify: `agent/routers/chat.py`
- Modify: `agent/services/orchestrator.py`
- Test: `agent/tests/test_chat_router.py` (create if not exists)

**Approach:**
- In `chat.py` router, extract `X-Thread-Id` header (optional, defaults to `str(uuid.uuid4())` if not provided for backward compatibility)
- Pass `thread_id` to `orchestrator.dispatch(capability="chat", family_id=..., user_id=..., free_text=question, thread_id=thread_id)`
- In `orchestrator.py`, accept `thread_id` parameter in `dispatch()` signature
- **Critical change**: Replace the existing `thread_id=audit_id` hardcode (line ~113 of `orchestrator.py`) with the caller-supplied `thread_id` parameter when calling `deerflow_adapter.dispatch()`. This is the load-bearing change for session continuity.
- When routing to `fallback_engine`, ignore `thread_id` (fallback doesn't use checkpointer)

**Patterns to follow:**
- Existing header extraction pattern in `chat.py` for `X-Family-Id`, `X-Agent-Token`, `X-User-Id`
- `agent/services/deerflow_adapter/adapter.py` — `dispatch()` already accepts `thread_id` parameter

**Test scenarios:**
- Happy path: Router extracts `X-Thread-Id` header and passes to orchestrator
- Happy path: Orchestrator forwards `thread_id` to DeerFlow adapter
- Edge case: Router generates fresh UUID when `X-Thread-Id` header is missing (backward compatibility)
- Integration: DeerFlow adapter receives stable `thread_id` across multiple requests with same session ID

**Verification:**
- Test scenarios pass
- DeerFlow checkpointer uses stable `thread_id` for conversation state (verify by checking SQLite checkpointer DB for repeated `thread_id` values)
- Agent can resume conversation context when same `thread_id` is provided

---

- [ ] **Unit 5: Add GET /ai/chat/sessions endpoint**

**Goal:** Create new endpoint to list all sessions for the current family.

**Requirements:** R1

**Dependencies:** Unit 1

**Files:**
- Modify: `backend/app/routers/ai_chat.py`
- Test: `backend/tests/test_ai_chat_router.py`

**Approach:**
- Add `GET /ai/chat/sessions` endpoint with `limit: int = 50` query param (default 50, consistent with other list endpoints)
- Query `AIChatSession` by `family_id`, order by `created_at DESC`, apply `limit`
- Return list: `[{session_id, created_at, message_count, last_preview}]`
- Use `require_adult` dependency (same as other chat endpoints)

**Patterns to follow:**
- `backend/app/routers/family.py` — list endpoint pattern with family scoping

**Test scenarios:**
- Happy path: Returns list of sessions for the family, ordered by creation date descending
- Edge case: Returns empty list when family has no sessions
- Integration: Sessions from different families are isolated (create sessions for two families, verify each sees only their own)

**Verification:**
- Test scenarios pass
- Endpoint returns correct session metadata matching DB state

---

- [ ] **Unit 6: Alembic migration to backfill existing messages**

**Goal:** Create migration that exports existing `ai_chat_messages` rows to legacy JSONL files and creates corresponding `ai_chat_sessions` rows.

**Requirements:** R5

**Dependencies:** Unit 1, Unit 2

**Files:**
- Create: `backend/alembic/versions/XXXX_backfill_chat_messages_to_jsonl.py`

**Approach:**
- **IMPORTANT**: Inline all JSONL write and SHA256 logic directly in the migration — do NOT import `ChatSessionService` or any application code. Alembic migrations must be self-contained.

- In `upgrade()`:
  - Query all distinct `family_id` values from `ai_chat_messages`
  - For each family:
    - Create session: `session_id = uuid4()`, `jsonl_path = f"{family_id}/legacy_{family_id}.jsonl"`
    - **Path safety**: Validate `family_id` is a valid UUID before constructing path
    - Create directory `{CHAT_DIR}/{family_id}/` if not exists
    - Query all messages for that family, order by `created_at ASC`
    - Write each message to JSONL file: `{"message_id": msg.id, "role": msg.role, "content": msg.content, "timestamp": msg.created_at.isoformat()}\n`
    - Compute SHA256 of JSONL file (inline: `hashlib.sha256(file_content).hexdigest()`)
    - Insert `CachedFile` row with `user_id=NULL` (legacy sessions have no single owner), `family_id`, SHA256, `mime_type="application/x-ndjson"`, `local_path` (absolute path)
    - Insert `AIChatSession` row with `cached_file_id=cached_file.id`, `user_id=NULL`, `message_count`, `last_preview` (last assistant message content[:100])
    - If `settings.CHAT_ENABLE_REMOTE_SYNC` is True AND default `StorageBackend` exists, insert `FileRemoteLocation(sync_status="pending")`
  - Do NOT delete `ai_chat_messages` rows — keep for rollback safety

- In `downgrade()`:
  - Delete all `AIChatSession` rows
  - Delete all `CachedFile` rows where `mime_type="application/x-ndjson"`
  - Delete all JSONL files in `{CHAT_DIR}/*/` (not just `legacy_*.jsonl` — clean up all chat JSONL files)
  - Do NOT restore `ai_chat_messages` rows (they were never deleted)

**Patterns to follow:**
- `backend/alembic/versions/c21c36dc5fbf_add_file_storage_tables.py` — migration structure
- `backend/app/services/chat_session.py` — JSONL write and SHA256 computation logic (reuse or inline)

**Test scenarios:**
- Happy path: Migration exports messages from 2 families into separate legacy JSONL files
- Happy path: Migration creates `AIChatSession` rows with correct `message_count` and `last_preview`
- Happy path: Migration creates `CachedFile` rows with correct SHA256
- Edge case: Migration handles family with no messages (skips that family)
- Edge case: Migration handles family with only user messages (no assistant messages) — `last_preview` is NULL
- Integration: After migration, `GET /ai/chat/history` (without `session_id`) returns messages from legacy session

**Verification:**
- Migration runs successfully on test DB with existing `ai_chat_messages` rows
- Legacy JSONL files are valid and contain all messages in correct order
- `AIChatSession` rows have correct metadata
- `CachedFile` SHA256 matches actual file content
- Downgrade migration cleans up all created artifacts

---

- [ ] **Unit 7: Update backend tests to use new session-based API**

**Goal:** Update or create tests for the modified chat endpoints, ensuring coverage of session lifecycle and JSONL storage.

**Requirements:** All

**Dependencies:** Unit 3, Unit 5, Unit 6

**Files:**
- Create: `backend/tests/test_ai_chat_router.py` (comprehensive test suite)
- Modify: `backend/tests/conftest.py` (add `chat_session` fixture if needed)

**Approach:**
- Test full session lifecycle: create session (via POST without `session_id`), append messages, read history, delete session
- Test backward compatibility: POST/GET/DELETE without `session_id` work as expected
- Test cross-family isolation: sessions from different families don't leak
- Test JSONL file integrity: after multiple appends, JSONL file is valid and contains all messages
- Test `CachedFile` integration: JSONL files are registered and queued for sync
- Mock agent httpx call to avoid external dependency

**Patterns to follow:**
- `backend/tests/test_assets.py` — comprehensive router test suite with auth fixtures
- `backend/tests/test_upload.py` — file storage integration tests

**Test scenarios:**
- Happy path: Full session lifecycle (create, append, read, delete)
- Happy path: Multiple sessions per family
- Happy path: Session continuity across multiple POST calls with same `session_id`
- Error path: Invalid `session_id` returns 404
- Edge case: Family with no sessions
- Edge case: Session with only user messages (no assistant replies due to agent failure)
- Integration: JSONL files are created and updated correctly
- Integration: `CachedFile` rows are created with correct SHA256
- Integration: `FileRemoteLocation` rows are created when default backend exists
- Integration: Cross-family isolation (sessions from family A not visible to family B)

**Verification:**
- All test scenarios pass
- Test coverage for `ai_chat.py` router is >90%
- Tests run in isolation (each test gets fresh DB and file system state)

## System-Wide Impact

- **Interaction graph**: 
  - `POST /ai/chat` → `ChatSessionService.append_message` → `CachedFile` insert/update → APScheduler sync job picks up pending `FileRemoteLocation`
  - Agent router → orchestrator → DeerFlow adapter → SQLite checkpointer (now uses stable `thread_id`)

- **Error propagation**:
  - JSONL file write failures should rollback DB transaction — the DB commit happens inside the executor call, after the file write, so both are atomic
  - If DB commit succeeds but JSONL write fails (e.g., disk full), the executor will raise an exception and the outer handler should catch it, log the error, and return 500 (the `message_count` will be inconsistent — document this as a known edge case)
  - Agent call failures should NOT create assistant message (existing behavior preserved)
  - File lock timeout should raise `AppError(ErrorCode.CHAT_SESSION_BUSY)` (add new error code)
  - Path traversal attempts (invalid UUID in `family_id` or `session_id`) should raise `ValueError` and return 400

- **State lifecycle risks**:
  - Concurrent appends to same JSONL file — mitigated by file-level locking
  - Partial writes if process crashes mid-append — JSONL format is append-only, so partial line at EOF is ignored by parser (add `try/except json.JSONDecodeError` in `read_messages`)
  - SHA256 mismatch if file is modified outside the service — acceptable risk (file backup sync will detect mismatch)

- **API surface parity**:
  - All existing endpoints maintain backward compatibility via optional `session_id` param
  - New `GET /ai/chat/sessions` endpoint follows existing REST conventions

- **Integration coverage**:
  - Unit 7 tests cover cross-layer scenarios: HTTP request → service layer → JSONL file → DB state
  - Integration test for file backup sync: create session, append message, verify `FileRemoteLocation` row exists with `sync_status="pending"`

- **Unchanged invariants**:
  - `EnvelopeResponse` wrapper still wraps all responses in `{"data": ..., "code": ..., "message": ...}`
  - `require_adult` auth dependency still gates all chat endpoints
  - Agent internal token validation still required for backend → agent calls
  - Family-scoped data isolation still enforced via `family_id` filtering

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Path traversal via malicious `family_id` or `session_id` | Validate all path components are UUIDs; use `Path.resolve()` and verify result is under `CHAT_DIR` |
| Cross-family session access via missing `family_id` filter | Always filter session queries by `current_user.family_id` — document as security invariant |
| Conversation history exposed via remote sync | Default `CHAT_ENABLE_REMOTE_SYNC=False`; require explicit opt-in; document privacy implications |
| JSONL file corruption due to concurrent writes | Use file-level locking (`filelock` library) in `run_in_executor` for all append operations |
| `CachedFile.user_id` NOT NULL constraint fails on legacy sessions | Set `user_id=NULL` for legacy sessions in migration; make `user_id` nullable in `CachedFile` schema (separate migration) OR set to first family member's ID |
| Large JSONL files (10,000+ messages) cause slow reads | Defer file rotation to future iteration; monitor file sizes in production |
| Migration fails on large existing message tables | Test migration on production-sized dataset before deploying; add progress logging; inline all logic (no service imports) |
| DeerFlow checkpointer SQLite lock contention | Existing `_CHECKPOINTER_LOCK` in adapter already mitigates this (see institutional learnings) |
| Backward compatibility breaks existing frontend | Maintain optional `session_id` param; existing frontend continues to work without changes |

## Documentation / Operational Notes

- **Deployment order**: Run `uv run alembic upgrade head` before starting the app (critical — see institutional learnings)
- **Config changes**: Add `CHAT_DIR` env var (defaults to `./data/chat`)
- **Monitoring**: Track JSONL file sizes and `CachedFile` sync status for chat sessions
- **Rollback**: If issues arise, downgrade migration and revert to `ai_chat_messages` table (messages were not deleted)

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-20-008-chat-history-jsonl-requirements.md](docs/brainstorms/2026-04-20-008-chat-history-jsonl-requirements.md)
- Related code: `backend/app/models/ai_chat_message.py`, `backend/app/routers/ai_chat.py`, `agent/services/deerflow_adapter/adapter.py`
- Related patterns: `backend/app/services/storage/service.py` (file registration), `backend/alembic/versions/c21c36dc5fbf_add_file_storage_tables.py` (migration guard pattern)
- Institutional learnings: `docs/solutions/best-practices/file-storage-abstraction-2026-04-10.md`, `docs/solutions/integration-issues/deerflow-harness-silent-fallback-and-concurrency-fixes-2026-04-12.md`
