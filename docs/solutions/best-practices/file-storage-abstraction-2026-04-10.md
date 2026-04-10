---
title: Pluggable File Storage Abstraction with Local, GitHub, and WebDAV Backends
date: 2026-04-10
category: best-practices
module: storage
problem_type: best_practice
component: background_job
severity: high
applies_when:
  - Adding a new remote storage backend to the system
  - Implementing background sync jobs that use httpx.AsyncClient
  - Designing multi-backend DB schemas where files may exist on N remotes
  - Testing async jobs that close their own DB session in a finally block
tags: storage, file-upload, github-api, webdav, apscheduler, asyncio, httpx, fernet, dedup
---

# Pluggable File Storage Abstraction with Local, GitHub, and WebDAV Backends

## Context

The upload endpoint previously wrote files directly to a flat local directory with no DB record, no date-based organization, and no way to manage, migrate, or back up uploads. This document captures the design decisions, gotchas, and known issues from implementing a pluggable storage abstraction layer supporting local filesystem, GitHub Contents API, and WebDAV as backends.

## Guidance

### DB Schema: 4-table design for N-backend support

Use a separate `file_remote_locations` join table (one row per file × backend) rather than columns on the file record. This scales to N backends without schema changes.

```
storage_backends      ← one row per configured backend (type, encrypted config JSON, is_default)
cached_files          ← one row per uploaded file (local_path, sha256, filename, mime, family_id)
file_remote_locations ← one row per (file × backend) (remote_path, sync_status, remote_sha)
sync_events           ← append-only audit log
```

Key constraints:
- `UNIQUE(sha256, family_id)` on `cached_files` — per-family dedup, not global
- `UNIQUE(file_id, backend_id)` on `file_remote_locations`
- Only one `storage_backends` row has `is_default=True` at a time — enforced in service layer

### StorageBackend ABC pattern

Mirror the existing `CacheBackend` ABC pattern (`app/services/cache/base.py`):

```python
class StorageBackend(ABC):
    @abstractmethod
    async def save(self, content: bytes, filename: str, date_dir: str) -> str: ...
    @abstractmethod
    async def delete(self, remote_path: str) -> None: ...
    @abstractmethod
    def get_url(self, remote_path: str) -> str: ...
```

All backends are async. Local backend uses synchronous file I/O inside async methods — acceptable for small files but blocks the event loop. For production with large files, wrap with `asyncio.to_thread()`.

### Factory: cache instances to avoid httpx client leaks

`get_backend_for_type` must cache instances in `_instances` keyed by a stable config hash. Creating a new `httpx.AsyncClient` on every call leaks connection pools.

```python
# WRONG — leaks a new AsyncClient on every call
def get_backend_for_type(backend_type, config):
    return GitHubStorageBackend(token=config["token"], ...)

# CORRECT — cache by stable key
_instances: dict[str, StorageBackend] = {}

def get_backend_for_type(backend_type, config):
    key = f"{backend_type}:{config.get('repo', config.get('url', ''))}"
    if key not in _instances:
        _instances[key] = _create_backend(backend_type, config)
    return _instances[key]
```

Also add `max_instances=1` to the APScheduler sync job to prevent concurrent runs from double-processing the same `pending` rows:

```python
scheduler.add_job(file_sync_job, trigger="interval", minutes=N, id="file_sync",
                  max_instances=1, replace_existing=True)
```

### GitHub Contents API: SHA tracking is critical

Every PUT to an existing path requires the current blob SHA. Every DELETE requires the blob SHA. Store it in `file_remote_locations.remote_sha` after each successful write.

On 409 conflict (stale SHA): delete from cache, GET the file to fetch current SHA, retry PUT (max 3 attempts). After 3 failures raise `StorageConflictError`.

Rate limit: check `x-ratelimit-remaining` header on every response. If `"0"`, raise `StorageRateLimitError` with `reset_at` from `x-ratelimit-reset`. Throttle batch sync to 1 write/second for GitHub.

### WebDAV: MKCOL before PUT, treat 405 as success

WebDAV requires the parent collection to exist before PUT. Walk path segments and MKCOL each one. Treat 405 (already exists) as success — do not raise.

```python
async def _ensure_path(self, date_dir: str) -> None:
    segments = date_dir.split("/")
    for i in range(1, len(segments) + 1):
        path = "/".join(segments[:i])
        resp = await self._client.request("MKCOL", f"{self._base_url}/{path}")
        if resp.status_code not in (201, 405):
            raise StorageConnectionError(f"MKCOL failed: {resp.status_code}")
```

### Credential encryption: use a stable key, not SECRET_KEY directly

Deriving the Fernet key from `SECRET_KEY` via SHA-256 means rotating `SECRET_KEY` silently invalidates all stored encrypted configs. Use a dedicated `STORAGE_ENCRYPTION_KEY` setting (a proper Fernet key generated once with `Fernet.generate_key()`).

```python
# FRAGILE — key changes if SECRET_KEY rotates
key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())

# BETTER — dedicated stable key
key = settings.STORAGE_ENCRYPTION_KEY.encode()  # must be a valid Fernet key
```

Also: remove the plaintext JSON fast-path in `_decrypt_config`. It silently bypasses encryption for any config stored as plain JSON, making it impossible to audit whether credentials are actually encrypted at rest.

### Move crypto utilities out of scheduler.py

`encrypt_config` and `_decrypt_config` live in `scheduler.py` but are used by `routers/files.py`. This creates a wrong dependency direction (router → scheduler). Move them to `app/services/storage/crypto.py`.

### AsyncIOScheduler for async jobs

Switch from `BackgroundScheduler` (thread-based) to `AsyncIOScheduler` when jobs use `httpx.AsyncClient` or other async I/O. `BackgroundScheduler` runs jobs in threads, which cannot `await` coroutines.

```python
# scheduler.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
scheduler = AsyncIOScheduler()
```

Sync jobs (like `fetch_rates_job`) continue to work unchanged with `AsyncIOScheduler`.

### Testing async jobs that close their own DB session

When patching `SessionLocal` to return the test `db` fixture, the job's `finally: db.close()` will close the test session. Capture all IDs before the job runs, then re-query after:

```python
def test_sync_job(db, tmp_path):
    loc = _make_location(db, ...)
    loc_id = loc.id  # capture BEFORE job runs — loc becomes detached after db.close()

    with patch("app.scheduler.SessionLocal", return_value=db), \
         patch("app.scheduler.get_backend_for_type", return_value=mock_backend):
        asyncio.get_event_loop().run_until_complete(file_sync_job())

    # Re-query by captured ID — do NOT use db.refresh(loc)
    loc_updated = db.query(FileRemoteLocation).filter_by(id=loc_id).first()
    assert loc_updated.sync_status == "synced"
```

### Testing async methods without pytest-asyncio

Use `asyncio.run(coro)` (Python 3.11+) instead of `asyncio.get_event_loop().run_until_complete(coro)`. The latter is deprecated in Python 3.10+ and raises `RuntimeError` in Python 3.12 when no running loop exists.

```python
# DEPRECATED in 3.10+, broken in 3.12
def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

# CORRECT
def run(coro):
    return asyncio.run(coro)
```

## Why This Matters

- **httpx client leaks** accumulate silently — each unclosed `AsyncClient` holds an open connection pool and OS file descriptors. Under normal sync frequency this exhausts resources within hours.
- **SHA cache invalidation** causes every GitHub write to pay a 409 + GET + retry cost, burning rate-limit quota and slowing sync.
- **Concurrent sync jobs** without `max_instances=1` can double-process rows, causing duplicate remote writes and incorrect `retry_count` increments.
- **Plaintext config bypass** makes credential encryption unauditable and creates a false sense of security.
- **SECRET_KEY-derived Fernet key** means any key rotation silently breaks all stored backend configs with no error until the next sync cycle.

## Prevention

- Always add `max_instances=1` to interval-based APScheduler jobs that mutate DB rows
- Always cache `httpx.AsyncClient`-backed backend instances; never create per-call
- Use a dedicated `STORAGE_ENCRYPTION_KEY` env var (Fernet key) separate from `SECRET_KEY`
- Move crypto utilities to a dedicated module (`app/services/storage/crypto.py`) — never in scheduler or router
- Use `asyncio.run()` in tests, not `asyncio.get_event_loop().run_until_complete()`
- Capture all ORM object IDs before calling any function that closes the session

## Related Issues

- Plan: `docs/plans/2026-04-10-003-feat-file-storage-abstraction-plan.md`
- Security audit patterns: `docs/solutions/best-practices/security-audit.md`
- File upload security (magic bytes validation): `app/services/file_validation.py`
