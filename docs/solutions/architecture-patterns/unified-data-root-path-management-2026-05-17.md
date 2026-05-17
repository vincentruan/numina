---
title: "Unified DATA_ROOT path management for multi-service monorepo"
date: 2026-05-17
category: docs/solutions/architecture-patterns
module: server
problem_type: architecture_pattern
component: service_object
severity: medium
applies_when:
  - "Adding new data paths or storage locations to any server module"
  - "Deploying to Docker or relocating data to a different disk"
  - "Configuring per-path env vars for operators"
tags: [data-root, path-management, pydantic-settings, docker-volume, configuration]
---

# Unified DATA_ROOT path management for multi-service monorepo

## Context

The numina server monorepo has three services (backend, agent, scheduler_worker) that each construct local file paths independently. Before this pattern, operators needed to set 6+ env vars (`UPLOAD_DIR`, `WORKSPACE_ROOT`, `CHAT_DIR`, `LOG_DIR`, `DATABASE_URL`, `SESSIONS_DATA_DIR`, `AGENT_DATA_DIR`) to relocate data. Docker required two volumes (`./data:/app/data` + `agent_logs:/app/logs`). Several paths were hardcoded entirely (DeerFlow checkpointer, audit log).

## Guidance

Introduce a single `DATA_ROOT` env var (default `~/.numina/data/`) from which all sub-paths derive. All existing per-path env vars remain as overrides.

### Pattern: pydantic-settings `@model_validator(mode="after")`

```python
from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings

_OLD_DEFAULTS = {
    "DATABASE_URL": "sqlite:///./data/numina.db",
    "UPLOAD_DIR": "./data/uploads",
    "LOG_DIR": "logs",
}

class Settings(BaseSettings):
    DATA_ROOT: str = "~/.numina/data"
    DATABASE_URL: str = "sqlite:///./data/numina.db"
    UPLOAD_DIR: str = "./data/uploads"
    LOG_DIR: str = "logs"

    @model_validator(mode="after")
    def _resolve_data_root(self) -> "Settings":
        root = str(Path(self.DATA_ROOT).expanduser().resolve())
        self.DATA_ROOT = root

        # Only override if the value is still the old default (not explicitly set)
        if _OLD_DEFAULTS["DATABASE_URL"] == self.DATABASE_URL:
            db_path = Path(root) / "db" / "numina.db"
            self.DATABASE_URL = f"sqlite:///{db_path}"

        if _OLD_DEFAULTS["UPLOAD_DIR"] == self.UPLOAD_DIR:
            self.UPLOAD_DIR = str(Path(root) / "workspace")

        if _OLD_DEFAULTS["LOG_DIR"] == self.LOG_DIR:
            self.LOG_DIR = str(Path(root) / "logs")

        return self
```

### Key design decisions

1. **`~` expansion is explicit** — `Path(DATA_ROOT).expanduser().resolve()` in the validator. No implicit expansion elsewhere.

2. **Old-default detection for backward compatibility** — Compare against `_OLD_DEFAULTS` dict to detect whether a field was explicitly set by the operator or still holds the class default. Only derive from `DATA_ROOT` when the value matches the old default.

3. **Docker: one volume, one env var** — `DATA_ROOT=/app/.numina/data` injected via `docker-compose.yml`. Single bind mount `${NUMINA_DATA_DIR:-./data}:/app/.numina/data` replaces multiple volumes.

4. **Sub-path structure** — Services construct their own sub-paths from the shared root:
   ```
   {DATA_ROOT}/
   ├── db/numina.db, deerflow-checkpoints.db
   ├── workspace/{family_id}/upload/{user_id}/...
   ├── workspace/{family_id}/agent/{capability}/{user_id}/...
   ├── workspace/{family_id}/chat/...
   └── logs/app.log, agent-audit.log
   ```

5. **Lazy init for audit logger** — Module-level init with hardcoded paths replaced by `setup_audit_logger()` called from lifespan startup, reading `settings.LOG_DIR`.

## Why This Matters

- **Operators set one env var** to relocate all data (vs 6+ previously)
- **Docker deployments** use one volume instead of two
- **New paths automatically land under DATA_ROOT** — developers add a field with empty default and derive in the validator
- **Backward compatible** — existing `.env` files with explicit paths continue to work unchanged

## When to Apply

- Adding any new data path to any server module: derive from `DATA_ROOT` in the validator
- Never hardcode absolute paths in service code — always read from settings
- For agent-specific paths, use `apps/agent/app/config.py` (has its own `DATA_ROOT` + validator)
- For backend/scheduler paths, use `packages/core/settings.py`

## Examples

### Adding a new path field

```python
# In packages/core/settings.py
class Settings(BaseSettings):
    NEW_EXPORT_DIR: str = ""  # Empty = derive from DATA_ROOT

    @model_validator(mode="after")
    def _resolve_data_root(self) -> "Settings":
        root = str(Path(self.DATA_ROOT).expanduser().resolve())
        # ... existing derivations ...

        if not self.NEW_EXPORT_DIR:
            self.NEW_EXPORT_DIR = str(Path(root) / "workspace" / "exports")

        return self
```

### Docker override for a specific path

```yaml
# docker-compose.yml — operator wants logs on a separate volume
environment:
  - DATA_ROOT=/app/.numina/data
  - LOG_DIR=/var/log/numina  # Explicit override, not derived
```

## Related

- `docs/plans/2026-05-17-001-refactor-unified-data-root-path-plan.md` — original plan document
- `docs/solutions/best-practices/file-storage-abstraction-2026-04-10.md` — storage backend pattern
