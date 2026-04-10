---
title: "feat: File Storage Abstraction with Local, GitHub, and WebDAV Backends"
type: feat
status: active
date: 2026-04-10
---

# feat: File Storage Abstraction with Local, GitHub, and WebDAV Backends

## Overview

The current upload endpoint (`POST /api/v1/upload/image`) writes files directly to a flat local directory with no DB record. This plan abstracts file storage into a pluggable backend system supporting local filesystem, GitHub, and WebDAV, with a normalized DB schema that tracks file metadata and per-backend sync state.

## Problem Frame

Files are saved inline in the router with no indexing, no date-based organization, and no way to manage, migrate, or back up uploads. Users need the ability to configure remote storage (GitHub repo or WebDAV server) as a backup/primary store, switch between backends over time, and still access files uploaded under a previous backend.

## Requirements Trace

- R1. Local storage: date-based directory structure (`yyyyMMdd`), DB record per file (path, sha256, filename, mime type, size)
- R2. GitHub backend: upload, delete, preview/download via raw URL; periodic sync from local to GitHub
- R3. WebDAV backend: upload, delete, preview/download; periodic sync from local to WebDAV
- R4. Extensible DB schema: supports N remote backends, per-file per-backend sync state
- R5. Default remote: only one backend is the active sync target at a time; switchable
- R6. Historical compatibility: files uploaded under a retired backend remain readable and deletable

## Scope Boundaries

- No S3/object storage backend in this plan (future extension)
- No chunked/resumable upload (files stay under 5 MB per existing limit)
- No frontend UI for backend configuration in this plan — settings are env-var or DB-driven via admin API
- No migration of existing uploaded files into the new schema (existing `/uploads/images/*.{ext}` files remain as-is)
- Excel/document upload endpoint is out of scope for this plan; the abstraction is designed to support it later

## Context & Research

### Relevant Code and Patterns

- `backend/app/routers/upload.py` — current upload endpoint; inline file write, no DB record, flat directory
- `backend/app/services/cache/base.py` + `factory.py` — ABC + singleton factory pattern to mirror for `StorageBackend`
- `backend/app/db/backend.py` + `factory.py` — second ABC + factory precedent
- `backend/app/config.py` — `pydantic-settings` `BaseSettings`; add new storage fields here
- `backend/app/scheduler.py` — `BackgroundScheduler` with `add_job(..., trigger="cron")`; hook for periodic sync jobs
- `backend/app/services/file_validation.py` — `validate_image_magic_bytes()` / `detect_image_format()`; must be preserved in refactored router
- `backend/app/services/security_log.py` — `_log_security_event(SecurityEventType.UPLOAD_MAGIC_BYTES_MISMATCH, ...)`; must be preserved
- `backend/app/main.py` — `StaticFiles` mount at `/uploads`; `Base.metadata.create_all()` on startup; model imports with `# noqa: F401`

### Institutional Learnings

- File upload security: always validate magic bytes via `file_validation.py`; call `_log_security_event` on mismatch; call `await file.seek(0)` after `file.read()` if passing downstream
- No prior art for storage abstraction, background sync, or external API integration in this repo

### External References

- GitHub Contents API: PUT requires base64 content + blob SHA for updates; DELETE requires blob SHA; 409 on stale SHA → re-fetch and retry; rate limit 5000 req/hr; serialize writes (1 write/sec for batch); raw URL: `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}`
- WebDAV: PUT for upload; MKCOL to create directories (one level at a time; 405 = already exists = OK); DELETE for removal; use `httpx.AsyncClient` with `BasicAuth` — not `webdavclient3` (not true async)
- DB schema: separate `file_remote_locations` join table (one row per file × backend) is the correct model for N-backend support; `storage_backends` config table with `is_default` flag; `sync_status` enum per location row

## Key Technical Decisions

- **StorageBackend ABC mirrors CacheBackend**: `save()`, `delete()`, `get_url()` abstract methods; factory selects implementation by `backend_type` string — consistent with existing cache and DB backend patterns
- **4-table DB schema** (`storage_backends`, `cached_files`, `file_remote_locations`, `sync_events`): scales to N backends without schema changes; `file_remote_locations` UNIQUE on `(file_id, backend_id)` enforces one location record per file per backend
- **Local storage is always the primary write target**: on upload, file is always written locally first; remote sync is async (background job), never blocking the upload response
- **`is_default` on `storage_backends`**: only one row has `is_default=True` at a time; enforced in service layer (not DB constraint, to keep SQLite-compatible); switching default is a two-update transaction
- **GitHub blob SHA stored in `file_remote_locations.remote_sha`**: required for subsequent PUT/DELETE; cached after each successful write; invalidated on 409
- **`httpx.AsyncClient` for both GitHub and WebDAV**: single lifespan-managed client per backend instance; avoids per-request connection pool teardown
- **Periodic sync via APScheduler**: new `setup_file_sync_schedule()` function in `scheduler.py`; runs every N minutes (configurable); processes `sync_status='pending'` rows for the default backend
- **Credentials stored in `storage_backends.config` as JSON**: encrypted at application layer before write (use `cryptography.fernet` with `SECRET_KEY`-derived key); never stored plaintext

## Open Questions

### Resolved During Planning

- **Separate table vs columns for remote locations**: separate `file_remote_locations` table — columns break at 2+ backends and can't index sync_status efficiently
- **webdavclient3 vs httpx**: use `httpx.AsyncClient` — webdavclient3 is not true async and would block the event loop
- **Sync blocking upload response**: no — local write is synchronous and immediate; remote sync is always background
- **GitHub SHA tracking**: store `remote_sha` on `file_remote_locations`; re-fetch on 409 conflict

### Deferred to Implementation

- Exact Fernet key derivation from `SECRET_KEY` (PBKDF2 or direct truncation) — decide during Unit 2
- Whether `sync_events` table is needed for MVP or can be added later — implementer may defer it
- Exact cron schedule for sync jobs — make configurable via `Settings`
- Admin API endpoint design for managing `storage_backends` rows — out of scope for this plan, but the table must support it

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification. The implementing agent should treat it as context, not code to reproduce.*

```
Upload Request
     │
     ▼
upload.py router
  ├─ validate extension + magic bytes (existing)
  ├─ compute sha256
  ├─ call StorageService.save_local(content, filename, date_dir)
  │     └─ writes to UPLOAD_DIR/images/yyyyMMdd/{uuid}{ext}
  │     └─ inserts cached_files row
  ├─ if default remote backend configured:
  │     └─ inserts file_remote_locations row (status=pending)
  └─ returns {url, file_id}

Background Sync Job (APScheduler, every N min)
  ├─ query file_remote_locations WHERE sync_status='pending' AND backend_id=default
  ├─ for each pending row:
  │     ├─ load cached_files.local_path
  │     ├─ call backend.save(content, remote_path)
  │     └─ update sync_status='synced' | 'failed'
  └─ throttle: 1 write/sec for GitHub backend

StorageBackend ABC
  ├─ LocalStorageBackend   → filesystem write
  ├─ GitHubStorageBackend  → httpx PUT to Contents API (base64, SHA tracking)
  └─ WebDAVStorageBackend  → httpx PUT with MKCOL path creation

DB Schema (4 tables)
  storage_backends      ← one row per configured backend (type, config JSON, is_default)
  cached_files          ← one row per uploaded file (local_path, sha256, filename, mime)
  file_remote_locations ← one row per (file × backend) (remote_path, sync_status, remote_sha)
  sync_events           ← append-only audit log (optional for MVP)
```

## Implementation Units

- [ ] **Unit 1: DB Models — 4-table schema**

**Goal:** Define SQLAlchemy models for `storage_backends`, `cached_files`, `file_remote_locations`, and `sync_events`.

**Requirements:** R1, R4, R5, R6

**Dependencies:** None

**Files:**
- Create: `backend/app/models/storage_backend.py`
- Create: `backend/app/models/cached_file.py`
- Create: `backend/app/models/file_remote_location.py`
- Create: `backend/app/models/sync_event.py`
- Modify: `backend/app/main.py` (add model imports with `# noqa: F401`)
- Create: `backend/alembic/versions/<hash>_add_file_storage_tables.py`
- Test: `backend/tests/test_file_storage_models.py`

**Approach:**
- `storage_backends`: `id` (TEXT PK, slug), `backend_type` (TEXT: 'local'|'github'|'webdav'), `display_name`, `config` (TEXT, JSON-encoded encrypted credentials), `is_default` (BOOLEAN), `is_active` (BOOLEAN), `created_at`
- `cached_files`: `id` (UUID TEXT PK), `family_id` (FK → families), `user_id` (FK → users), `sha256` (TEXT, UNIQUE), `local_path` (TEXT), `original_filename` (TEXT), `mime_type` (TEXT), `size_bytes` (INTEGER), `date_dir` (TEXT, yyyyMMdd), `created_at`
- `file_remote_locations`: `id` (UUID TEXT PK), `file_id` (FK → cached_files), `backend_id` (FK → storage_backends), `remote_path` (TEXT), `remote_url` (TEXT), `remote_sha` (TEXT, for GitHub blob SHA), `sync_status` (TEXT: 'pending'|'synced'|'failed'|'deleted'), `synced_at`, `last_error` (TEXT), `retry_count` (INTEGER), `created_at`, `updated_at`; UNIQUE constraint on `(file_id, backend_id)`
- `sync_events`: `id` (UUID TEXT PK), `file_id` (FK), `backend_id` (FK), `event_type` (TEXT), `detail` (TEXT JSON), `occurred_at`
- Use `Mapped[type]` + `mapped_column()` pattern (see `backend/app/models/asset.py`)
- Add indexes: `cached_files.sha256`, `cached_files.family_id`, `file_remote_locations(file_id)`, `file_remote_locations(backend_id, sync_status)`

**Patterns to follow:**
- `backend/app/models/asset.py` — `Mapped` + `mapped_column`, UUID string PK, `server_default=func.now()`
- `backend/app/models/family.py` — FK relationships

**Test scenarios:**
- Happy path: create `storage_backend` row, create `cached_file` row, create `file_remote_location` row linking them — all persist and are queryable
- Edge case: inserting two `file_remote_location` rows with same `(file_id, backend_id)` raises IntegrityError
- Edge case: `cached_files.sha256` UNIQUE constraint rejects duplicate hash
- Happy path: `sync_status` transitions from 'pending' → 'synced' via update

**Verification:**
- `uv run alembic upgrade head` applies without error
- `uv run pytest tests/test_file_storage_models.py -v` passes
- `Base.metadata.tables` contains all 4 new table names after import

---

- [ ] **Unit 2: StorageBackend ABC + LocalStorageBackend**

**Goal:** Define the `StorageBackend` abstract interface and implement `LocalStorageBackend` with date-based directory structure.

**Requirements:** R1

**Dependencies:** Unit 1

**Files:**
- Create: `backend/app/services/storage/__init__.py`
- Create: `backend/app/services/storage/base.py`
- Create: `backend/app/services/storage/local.py`
- Create: `backend/app/services/storage/factory.py`
- Modify: `backend/app/config.py` (add `UPLOAD_DIR`, `STORAGE_DEFAULT_BACKEND` settings)
- Test: `backend/tests/test_storage_local.py`

**Approach:**
- `StorageBackend` ABC methods: `save(content: bytes, filename: str, date_dir: str) -> str` (returns remote_path), `delete(remote_path: str) -> None`, `get_url(remote_path: str) -> str`
- `LocalStorageBackend.save()`: writes to `{UPLOAD_DIR}/images/{date_dir}/{filename}`; creates directory with `mkdir(parents=True, exist_ok=True)`; returns relative path `images/{date_dir}/{filename}`
- `LocalStorageBackend.get_url()`: returns `/uploads/{remote_path}` (matches existing `StaticFiles` mount)
- `LocalStorageBackend.delete()`: removes file from disk; logs warning if file not found (don't raise)
- Factory: `get_storage_backend(backend_type: str) -> StorageBackend` — mirrors `app/services/cache/factory.py` singleton pattern
- Move `UPLOAD_DIR` from `os.getenv()` inline in router to `settings.UPLOAD_DIR`

**Patterns to follow:**
- `backend/app/services/cache/base.py` — ABC structure
- `backend/app/services/cache/factory.py` — singleton factory

**Test scenarios:**
- Happy path: `LocalStorageBackend.save(content, "photo.jpg", "20260410")` creates file at correct path, returns `"images/20260410/photo.jpg"`
- Happy path: `get_url("images/20260410/photo.jpg")` returns `"/uploads/images/20260410/photo.jpg"`
- Happy path: `delete("images/20260410/photo.jpg")` removes file from disk
- Edge case: `delete()` on non-existent path logs warning, does not raise
- Edge case: `save()` with same filename twice overwrites (idempotent)
- Happy path: factory returns `LocalStorageBackend` for `backend_type="local"`

**Verification:**
- `uv run pytest tests/test_storage_local.py -v` passes
- Files are written to `{UPLOAD_DIR}/images/yyyyMMdd/` directory structure

---

- [ ] **Unit 3: Refactor upload router to use StorageService**

**Goal:** Replace inline file write in `upload.py` with `StorageService` that writes locally, records to DB, and enqueues remote sync if a default backend is configured.

**Requirements:** R1, R5

**Dependencies:** Unit 1, Unit 2

**Files:**
- Create: `backend/app/services/storage/service.py`
- Modify: `backend/app/routers/upload.py`
- Modify: `backend/app/schemas/` — add `backend/app/schemas/file_record.py` (`FileRecordResponse`)
- Test: `backend/tests/test_upload.py` (extend existing or create)

**Approach:**
- `StorageService.upload_file(content, original_filename, ext, user, db) -> FileRecordResponse`:
  1. Compute `sha256` of content
  2. Check `cached_files` for existing sha256 — if found, return existing record (deduplication)
  3. Generate UUID filename: `{uuid4().hex}{ext}`
  4. Compute `date_dir = datetime.now().strftime("%Y%m%d")`
  5. Call `LocalStorageBackend.save(content, filename, date_dir)`
  6. Insert `cached_files` row
  7. If default remote backend exists in `storage_backends`: insert `file_remote_locations` row with `sync_status='pending'`
  8. Return `FileRecordResponse` with `url`, `file_id`
- Router: replace `open()` block with `StorageService.upload_file()`; preserve all existing validation (extension, size, magic bytes, security log)
- `FileRecordResponse`: `file_id: str`, `url: str`, `filename: str`, `size_bytes: int`
- Response remains backward-compatible: still includes `url` field

**Patterns to follow:**
- `backend/app/routers/assets.py` — `Depends(get_db)` + service call pattern
- `backend/app/services/asset.py` — service function signature

**Test scenarios:**
- Happy path: POST `/api/v1/upload/image` with valid JPEG returns 200 with `url` and `file_id`; `cached_files` row exists in DB
- Happy path: uploading same file twice (same sha256) returns existing `file_id` without creating duplicate DB row
- Error path: file exceeds 5 MB → 400, no DB row created
- Error path: invalid extension → 400, no DB row created
- Error path: magic bytes mismatch → 400, security event logged, no DB row created
- Integration: after upload, `file_remote_locations` row with `sync_status='pending'` exists when default remote backend is configured
- Integration: after upload, `file_remote_locations` row is absent when no default remote backend is configured

**Verification:**
- `uv run pytest tests/test_upload.py -v` passes (all existing tests still pass)
- `uv run pytest tests/ -v` — full suite passes

---

- [ ] **Unit 4: GitHubStorageBackend**

**Goal:** Implement GitHub Contents API backend with SHA tracking, retry on 409, and rate-limit awareness.

**Requirements:** R2

**Dependencies:** Unit 2

**Files:**
- Create: `backend/app/services/storage/github.py`
- Modify: `backend/app/services/storage/factory.py` (register `GitHubStorageBackend`)
- Modify: `backend/app/config.py` (add `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` settings)
- Test: `backend/tests/test_storage_github.py`

**Approach:**
- `GitHubStorageBackend.__init__`: takes `token`, `repo` ("owner/repo"), `branch`; creates `httpx.AsyncClient` with auth headers and `base_url="https://api.github.com"`
- `save(content, filename, date_dir)`: PUT to `/repos/{repo}/contents/{date_dir}/{filename}`; base64-encode content; if 409 → GET current SHA → retry PUT with new SHA (max 3 retries); capture and store `remote_sha` from response; return `remote_path`
- `delete(remote_path)`: GET file to obtain current SHA (or use cached); DELETE with SHA; on 409 → re-fetch SHA and retry
- `get_url(remote_path)`: return `https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{remote_path}`
- Rate limit handling: check `x-ratelimit-remaining` header; if 0, raise `StorageRateLimitError` with reset time; on 403 secondary limit, raise with 60s backoff signal
- SHA caching: `_sha_cache: dict[str, str]` on instance; invalidate on 409
- `httpx.AsyncClient` is lifespan-managed (created in `__init__`, closed in `aclose()`)

**Patterns to follow:**
- `backend/app/services/cache/factory.py` — backend registration
- GitHub API: `Authorization: Bearer {token}`, `Accept: application/vnd.github+json`, `X-GitHub-Api-Version: 2022-11-28`

**Test scenarios:**
- Happy path: `save()` with mocked httpx returns 201 → `remote_path` returned, `remote_sha` cached
- Happy path: `get_url("images/20260410/photo.jpg")` returns correct raw.githubusercontent.com URL
- Error path: `save()` returns 409 → re-fetches SHA → retries PUT → succeeds on second attempt
- Error path: `save()` returns 409 three times → raises `StorageConflictError`
- Error path: `x-ratelimit-remaining: 0` → raises `StorageRateLimitError`
- Error path: `delete()` with stale SHA → re-fetches → retries → succeeds
- Edge case: `save()` to existing path (update) requires SHA in request body

**Verification:**
- `uv run pytest tests/test_storage_github.py -v` passes (all tests use mocked httpx)
- Factory returns `GitHubStorageBackend` for `backend_type="github"`

---

- [ ] **Unit 5: WebDAVStorageBackend**

**Goal:** Implement WebDAV backend with MKCOL path creation, Basic auth, and provider-agnostic URL handling.

**Requirements:** R3

**Dependencies:** Unit 2

**Files:**
- Create: `backend/app/services/storage/webdav.py`
- Modify: `backend/app/services/storage/factory.py` (register `WebDAVStorageBackend`)
- Modify: `backend/app/config.py` (add `WEBDAV_URL`, `WEBDAV_USERNAME`, `WEBDAV_PASSWORD` settings)
- Test: `backend/tests/test_storage_webdav.py`

**Approach:**
- `WebDAVStorageBackend.__init__`: takes `base_url`, `username`, `password`; creates `httpx.AsyncClient` with `BasicAuth` and generous write timeout (120s)
- `_ensure_path(remote_dir)`: walk path segments, MKCOL each; treat 405 as success (already exists); raise on 409 (parent missing — should not happen with sequential walk)
- `save(content, filename, date_dir)`: call `_ensure_path(date_dir)`; PUT to `{base_url}/{date_dir}/{filename}`; return `remote_path`
- `delete(remote_path)`: DELETE with `Depth: infinity` header; treat 404 as success
- `get_url(remote_path)`: return `{base_url}/{remote_path}` (direct WebDAV GET URL)
- Error handling: wrap all calls in `try/except httpx.TransportError`; raise `StorageConnectionError` on network failure; raise `StorageAuthError` on 401/403

**Patterns to follow:**
- `backend/app/services/storage/github.py` — lifespan-managed client, error hierarchy

**Test scenarios:**
- Happy path: `save()` with mocked httpx — MKCOL returns 201, PUT returns 201 → `remote_path` returned
- Happy path: `_ensure_path()` — MKCOL returns 405 (already exists) → treated as success, no error raised
- Error path: PUT returns 401 → raises `StorageAuthError`
- Error path: `httpx.TransportError` on PUT → raises `StorageConnectionError`
- Happy path: `delete()` returns 204 → success
- Edge case: `delete()` returns 404 → treated as success (already gone)
- Happy path: `get_url("images/20260410/photo.jpg")` returns `{base_url}/images/20260410/photo.jpg`

**Verification:**
- `uv run pytest tests/test_storage_webdav.py -v` passes (all tests use mocked httpx)
- Factory returns `WebDAVStorageBackend` for `backend_type="webdav"`

---

- [ ] **Unit 6: Background sync job + file management API**

**Goal:** Add periodic sync job that pushes pending local files to the default remote backend, and add API endpoints for file delete and URL retrieval.

**Requirements:** R2, R3, R5, R6

**Dependencies:** Unit 1, Unit 2, Unit 3, Unit 4, Unit 5

**Files:**
- Modify: `backend/app/scheduler.py` (add `setup_file_sync_schedule()`)
- Modify: `backend/app/main.py` (call `setup_file_sync_schedule()` in lifespan)
- Create: `backend/app/routers/files.py` (file management endpoints)
- Modify: `backend/app/main.py` (register `files` router)
- Modify: `backend/app/config.py` (add `FILE_SYNC_INTERVAL_MINUTES: int = 15`)
- Test: `backend/tests/test_file_sync.py`

**Approach:**
- Sync job: query `file_remote_locations` WHERE `sync_status='pending'` AND `backend_id` = current default; for each row, load `cached_files.local_path`, call `backend.save()`; update `sync_status='synced'` or `'failed'` + `last_error`; increment `retry_count` on failure; skip rows with `retry_count >= 3`
- GitHub throttle: 1-second sleep between writes in sync job
- File management endpoints (all require `get_current_user`):
  - `DELETE /api/v1/files/{file_id}`: delete from local disk + all synced remote backends; update `sync_status='deleted'`; soft-delete `cached_files` row (add `deleted_at` column) or hard-delete
  - `GET /api/v1/files/{file_id}/url`: return URL for the file — prefer default backend URL if synced, fall back to local URL
- Historical compatibility: `GET /api/v1/files/{file_id}/url` checks `file_remote_locations` for any `sync_status='synced'` row (any backend), returns that URL; falls back to local `/uploads/` URL

**Patterns to follow:**
- `backend/app/scheduler.py` — `scheduler.add_job(..., trigger="interval", minutes=N)`
- `backend/app/routers/assets.py` — router + auth + db dependency pattern

**Test scenarios:**
- Happy path: sync job processes one `pending` row → calls `backend.save()` → updates `sync_status='synced'`
- Error path: `backend.save()` raises `StorageConnectionError` → `sync_status='failed'`, `last_error` set, `retry_count` incremented
- Edge case: row with `retry_count=3` is skipped by sync job
- Happy path: `DELETE /api/v1/files/{file_id}` — file removed from disk, remote backends called, `sync_status='deleted'`
- Happy path: `GET /api/v1/files/{file_id}/url` — returns remote URL when `sync_status='synced'`
- Happy path: `GET /api/v1/files/{file_id}/url` — returns local URL when no remote sync exists
- Integration: sync job runs end-to-end with `LocalStorageBackend` as mock remote (no real network call)

**Verification:**
- `uv run pytest tests/test_file_sync.py -v` passes
- `uv run pytest tests/ -v` — full suite (36 + new tests) passes
- `npm run build` (from `frontend/`) passes (no frontend changes, but verify no regressions)

## System-Wide Impact

- **Interaction graph:** `upload.py` router now depends on `StorageService` + `get_db`; `scheduler.py` lifespan now starts sync job; `main.py` imports 4 new models
- **Error propagation:** `StorageService.upload_local()` failure (disk full, permissions) → 500 to client; remote sync failures are silent to the upload caller (background job handles retries)
- **State lifecycle risks:** sha256 deduplication means two users uploading the same file share a `cached_files` row — `family_id` on `cached_files` scopes ownership; delete must check family ownership before removing
- **API surface parity:** existing `POST /api/v1/upload/image` response still includes `url` field — backward compatible; `file_id` is additive
- **Integration coverage:** sync job + GitHub/WebDAV backends require mocked httpx in tests; real network calls are not tested in unit suite
- **Unchanged invariants:** `Asset.image_url` continues to store the `/uploads/images/...` URL string; no change to asset model or existing asset endpoints

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| GitHub rate limit during bulk sync | Throttle to 1 write/sec; skip on `StorageRateLimitError`; retry next cycle |
| WebDAV provider quirks (Synology self-signed cert, Nextcloud path prefix) | Document in settings; allow `WEBDAV_VERIFY_SSL: bool = True` config flag |
| Credential plaintext in `storage_backends.config` | Encrypt with Fernet before write; derive key from `SECRET_KEY` |
| Sync job and upload race (same file pending + sync starts) | `file_remote_locations` UNIQUE constraint prevents duplicate rows; sync job reads `pending` rows only after insert commits |
| Existing uploaded files not in `cached_files` | Out of scope; existing files continue to be served via `StaticFiles` mount unchanged |
| `retry_count >= 3` files silently stuck | Add `GET /api/v1/files/sync-status` endpoint (or admin log) to surface failed rows — deferred |

## Sources & References

- Related code: `backend/app/routers/upload.py`, `backend/app/services/cache/`, `backend/app/db/`, `backend/app/scheduler.py`
- GitHub Contents API: https://docs.github.com/en/rest/repos/contents
- GitHub rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- WebDAV RFC 4918: https://datatracker.ietf.org/doc/html/rfc4918
- httpx async docs: https://www.python-httpx.org/async/
