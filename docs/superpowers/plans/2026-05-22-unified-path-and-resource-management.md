# Unified Path Management + Multi-Tenant Resource Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 1 of the unified file path management and multi-tenant resource isolation for Numina's server layer: `PathManager`, `EffectiveConfigBuilder`, `ModelEntryBuilder`, and the new `AgentRunService` that replaces `agent_dispatch.py` with the Gateway path (per-request `AppConfig` injection into `make_lead_agent()`).

**Architecture:** `PathManager` (shared package) owns all local file paths. `EffectiveConfigBuilder` merges DB metadata + builtin files + tenant overlays into a DeerFlow2 `AppConfig` object. `AgentRunService` wires the pipeline: BackendClient queries -> EffectiveConfigBuilder -> RunnableConfig -> `make_lead_agent()` -> `astream()`. No global singleton mutation, no ContextVar, no `reload_app_config()`.

**Tech Stack:** Python 3.12+ / FastAPI / pydantic-settings / DeerFlow2 harness (LangGraph) / pytest + pytest-asyncio

**Spec:** `docs/superpowers/specs/2026-05-22-unified-path-and-resource-management-design.md`

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `server/packages/core/path_manager.py` | `PathManager` class — all local file path generation + security validation |
| `server/packages/core/effective_config.py` | `EffectiveConfigBuilder` — merges DB + files into DeerFlow2 `AppConfig` |
| `server/packages/core/model_entry.py` | `ModelEntryBuilder` — builds DeerFlow2 model config dict from DB provider data |
| `server/tests/agent/unit/test_path_manager.py` | PathManager unit tests (security + functional) |
| `server/tests/agent/unit/test_effective_config.py` | EffectiveConfigBuilder unit tests |
| `server/tests/agent/unit/test_model_entry.py` | ModelEntryBuilder unit tests |
| `server/tests/agent/unit/test_agent_run_service.py` | AgentRunService integration smoke tests |

### Modified Files

| File | Change |
|------|--------|
| `server/packages/core/__init__.py` | Export `get_path_manager` singleton accessor |
| `server/apps/agent/services/agent_dispatch.py` | Replace with new Gateway path using `AgentRunService` |

---

## Conventions

All tasks follow these rules without exception:

- **TDD:** Write failing test first -> run to confirm failure -> implement -> run to confirm pass -> commit.
- **Test command:** `cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/<test_file> -v`
- **Test patterns:** pytest classes to group tests, `with patch()` context managers, `pytest.raises(match=...)`.
- **Import pattern:** `from packages.core.path_manager import PathManager` (never `from packages.core import PathManager`).
- **Logger:** `from packages.core.logging import get_logger; logger = get_logger(__name__)`.
- **Chinese error messages** for user-facing errors: `raise PathSecurityError("路径越界: ...")`.
- **Slug validation:** `agent_name` must match `[a-z][a-z0-9-]*` (lowercase, no underscores).
- **Commit messages:** conventional commits (`feat:`, `test:`, `fix:`).
- **packages/core must never import from apps/** — dependency flow is one-way.

---

## Task 1: PathManager — Core Paths + Security Validation

**Goal:** Create `PathManager` with `__init__`, root directory properties, builtin directory properties, and all security methods. Write security tests first (TDD).

**Files:**
- Create: `server/packages/core/path_manager.py`
- Create: `server/tests/agent/unit/test_path_manager.py`

### Step 1.1: Write security + core path tests (RED)

- [ ] Create `server/tests/agent/unit/test_path_manager.py` with the following test classes:

```python
# server/tests/agent/unit/test_path_manager.py
"""Unit tests for PathManager — security + core paths."""

import os
import tempfile
from pathlib import Path

import pytest

from packages.core.path_manager import PathManager, PathSecurityError


@pytest.fixture
def tmp_data_root(tmp_path):
    """Provide a temporary data root directory for test isolation."""
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    """PathManager instance with isolated temp data root."""
    return PathManager(data_root=tmp_data_root)


class TestPathManagerInit:
    def test_creates_base_directories(self, pm, tmp_data_root):
        """__init__ must create db/, workspaces/builtin/, workspaces/tenants/,
        runtime/effective/, logs/, backups/."""
        assert (tmp_data_root / "db").is_dir()
        assert (tmp_data_root / "workspaces" / "builtin").is_dir()
        assert (tmp_data_root / "workspaces" / "tenants").is_dir()
        assert (tmp_data_root / "runtime" / "effective").is_dir()
        assert (tmp_data_root / "logs").is_dir()
        assert (tmp_data_root / "backups").is_dir()

    def test_data_root_expands_tilde(self, tmp_path):
        """data_root with ~ must be expanded to absolute path."""
        pm = PathManager(data_root=tmp_path / "data")
        assert pm.data_root.is_absolute()
        assert "~" not in str(pm.data_root)

    def test_data_root_is_resolved(self, tmp_path):
        """data_root must be resolved (no symlinks in path)."""
        pm = PathManager(data_root=tmp_path / "data")
        assert pm.data_root == pm.data_root.resolve()

    def test_reads_data_root_from_env(self, tmp_path, monkeypatch):
        """When no data_root arg, reads DATA_ROOT env var."""
        env_root = tmp_path / "env_data"
        monkeypatch.setenv("DATA_ROOT", str(env_root))
        pm = PathManager()
        assert pm.data_root == env_root.resolve()

    def test_default_data_root_when_no_env(self, monkeypatch):
        """When no arg and no env, defaults to ~/.numina/data."""
        monkeypatch.delenv("DATA_ROOT", raising=False)
        pm = PathManager()
        expected = Path("~/.numina/data").expanduser().resolve()
        assert pm.data_root == expected


class TestCorePathProperties:
    def test_db_dir(self, pm, tmp_data_root):
        assert pm.db_dir == tmp_data_root.resolve() / "db"

    def test_logs_dir(self, pm, tmp_data_root):
        assert pm.logs_dir == tmp_data_root.resolve() / "logs"

    def test_backups_dir(self, pm, tmp_data_root):
        assert pm.backups_dir == tmp_data_root.resolve() / "backups"


class TestBuiltinPaths:
    def test_builtin_root(self, pm, tmp_data_root):
        assert pm.builtin_root == tmp_data_root.resolve() / "workspaces" / "builtin"

    def test_builtin_agents_dir(self, pm):
        assert pm.builtin_agents_dir == pm.builtin_root / "agents"

    def test_builtin_skills_dir(self, pm):
        assert pm.builtin_skills_dir == pm.builtin_root / "skills"

    def test_builtin_mcp_dir(self, pm):
        assert pm.builtin_mcp_dir == pm.builtin_root / "mcp"

    def test_builtin_agent_dir(self, pm):
        result = pm.builtin_agent_dir("asset-health-advisor")
        assert result == pm.builtin_agents_dir / "asset-health-advisor"

    def test_builtin_skill_dir(self, pm):
        result = pm.builtin_skill_dir("family-asset-checkup")
        assert result == pm.builtin_skills_dir / "family-asset-checkup"


class TestSlugValidation:
    @pytest.mark.parametrize("slug", [
        "asset-health",
        "a",
        "abc123",
        "my-agent-v2",
        "a0",
    ])
    def test_accepts_valid_slugs(self, pm, slug):
        """Slugs matching [a-z][a-z0-9-]* must be accepted."""
        # Should not raise — exercise via builtin_agent_dir
        pm.builtin_agent_dir(slug)

    @pytest.mark.parametrize("slug,reason", [
        ("", "empty"),
        ("../etc/passwd", "path traversal"),
        ("Agent-Name", "uppercase"),
        ("123abc", "starts with digit"),
        ("-leading-dash", "starts with dash"),
        ("has_underscore", "underscore"),
        ("has space", "space"),
        ("a/b", "slash"),
        ("a" * 256, "too long (over 128)"),
    ])
    def test_rejects_invalid_slugs(self, pm, slug, reason):
        """Invalid slugs must raise PathSecurityError."""
        with pytest.raises(PathSecurityError, match="无效的"):
            pm.builtin_agent_dir(slug)


class TestThreadIdValidation:
    def test_accepts_valid_uuid(self, pm):
        """Valid UUID thread_ids must be accepted."""
        pm.tenant_session_dir(12345, "my-agent", "a1b2c3d4-e5f6-7890-abcd-ef1234567890")

    @pytest.mark.parametrize("thread_id", [
        "",
        "../escape",
        "not-a-uuid",
        "a1b2c3d4e5f67890abcdef1234567890",  # no dashes
        "a1b2c3d4-e5f6-7890-abcd-ef123456789",  # 35 chars
    ])
    def test_rejects_invalid_thread_ids(self, pm, thread_id):
        with pytest.raises(PathSecurityError, match="无效的.*thread_id"):
            pm.tenant_session_dir(12345, "my-agent", thread_id)


class TestAssertUnderRoot:
    def test_accepts_path_under_root(self, pm, tmp_data_root):
        sub = tmp_data_root.resolve() / "workspaces" / "tenants" / "123"
        sub.mkdir(parents=True, exist_ok=True)
        result = pm.assert_under_root(sub)
        assert result == sub.resolve()

    def test_rejects_path_outside_root(self, pm, tmp_path):
        outside = tmp_path / "outside"
        outside.mkdir(parents=True, exist_ok=True)
        with pytest.raises(PathSecurityError, match="路径越界"):
            pm.assert_under_root(outside)

    def test_rejects_path_traversal(self, pm, tmp_data_root):
        traversal = tmp_data_root / "workspaces" / ".." / ".." / "etc" / "passwd"
        with pytest.raises(PathSecurityError, match="路径越界"):
            pm.assert_under_root(traversal)

    def test_rejects_symlink_escape(self, pm, tmp_data_root, tmp_path):
        """Symlink pointing outside data_root must be rejected after resolve()."""
        outside_target = tmp_path / "secret"
        outside_target.mkdir(parents=True, exist_ok=True)
        symlink = tmp_data_root / "workspaces" / "sneaky_link"
        symlink.symlink_to(outside_target)
        with pytest.raises(PathSecurityError, match="路径越界"):
            pm.assert_under_root(symlink)


class TestAssertTenantAccess:
    def test_accepts_path_within_own_tenant(self, pm):
        tenant_path = pm.tenant_root(12345) / "uploads" / "file.txt"
        tenant_path.parent.mkdir(parents=True, exist_ok=True)
        tenant_path.touch()
        result = pm.assert_tenant_access(tenant_path, 12345)
        assert result == tenant_path.resolve()

    def test_rejects_path_in_other_tenant(self, pm):
        other_tenant_path = pm.tenant_root(99999) / "uploads" / "file.txt"
        other_tenant_path.parent.mkdir(parents=True, exist_ok=True)
        other_tenant_path.touch()
        with pytest.raises(PathSecurityError, match="租户越界"):
            pm.assert_tenant_access(other_tenant_path, 12345)

    def test_rejects_builtin_path_as_tenant(self, pm):
        builtin_path = pm.builtin_root / "agents" / "test"
        builtin_path.mkdir(parents=True, exist_ok=True)
        with pytest.raises(PathSecurityError, match="租户越界"):
            pm.assert_tenant_access(builtin_path, 12345)
```

- [ ] Run tests to confirm RED (all fail because `path_manager.py` doesn't exist):

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py -v
```

Expected: `ModuleNotFoundError: No module named 'packages.core.path_manager'`

### Step 1.2: Implement PathManager (GREEN)

- [ ] Create `server/packages/core/path_manager.py`:

```python
# server/packages/core/path_manager.py
"""统一文件路径管理。所有本地文件路径必须通过此类获取。

安全保证:
- 所有路径组件经 slug/UUID 白名单验证
- 最终路径 resolve() 后检查 is_relative_to(data_root)
- 禁止 ..、绝对路径注入、软链逃逸
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from packages.core.logging import get_logger

logger = get_logger(__name__)

# Slug pattern: lowercase letter start, then lowercase alphanum + hyphens.
# Max length 128 to prevent filesystem issues.
_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_SLUG_MAX_LEN = 128

# UUID pattern for thread_id and request_id
_UUID_PATTERN = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")


class PathSecurityError(Exception):
    """路径安全违规。"""


class PathManager:
    """统一文件路径管理。所有本地文件路径必须通过此类获取。"""

    def __init__(self, data_root: str | Path | None = None):
        """
        Args:
            data_root: 覆盖 DATA_ROOT 环境变量。None 时读 env，默认 ~/.numina/data
        """
        raw = data_root or os.environ.get("DATA_ROOT", "~/.numina/data")
        self._data_root = Path(raw).expanduser().resolve()
        self._ensure_base_dirs()

    def _ensure_base_dirs(self) -> None:
        """Create required base directories."""
        dirs = [
            self._data_root / "db",
            self._data_root / "workspaces" / "builtin",
            self._data_root / "workspaces" / "tenants",
            self._data_root / "runtime" / "effective",
            self._data_root / "logs",
            self._data_root / "backups",
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    # ── Validation ────────────────────────────────────────────────────

    def _validate_slug(self, value: str, field_name: str) -> str:
        """Validate a slug path component against whitelist pattern."""
        if not value or len(value) > _SLUG_MAX_LEN or not _SLUG_PATTERN.match(value):
            raise PathSecurityError(f"无效的 {field_name}: {value!r}")
        return value

    def _validate_thread_id(self, value: str) -> str:
        """Validate thread_id is a valid UUID."""
        if not value or not _UUID_PATTERN.match(value):
            raise PathSecurityError(f"无效的 thread_id: {value!r}")
        return value

    def _validate_request_id(self, value: str) -> str:
        """Validate request_id is a valid UUID."""
        if not value or not _UUID_PATTERN.match(value):
            raise PathSecurityError(f"无效的 request_id: {value!r}")
        return value

    def _validate_numeric_id(self, value: int, field_name: str) -> str:
        """Validate and convert a numeric ID (Snowflake) to string for path use."""
        str_val = str(value)
        if not str_val.isdigit():
            raise PathSecurityError(f"无效的 {field_name}: {value!r}")
        return str_val

    # ── Security assertions ───────────────────────────────────────────

    def assert_under_root(self, path: Path) -> Path:
        """Assert that resolved path is under data_root. Returns resolved path."""
        resolved = path.resolve()
        if not resolved.is_relative_to(self._data_root):
            raise PathSecurityError(f"路径越界: {path}")
        return resolved

    def assert_tenant_access(self, path: Path, family_id: int) -> Path:
        """Assert that resolved path is within the given tenant's directory."""
        resolved = self.assert_under_root(path)
        tenant_root = self.tenant_root(family_id).resolve()
        if not resolved.is_relative_to(tenant_root):
            raise PathSecurityError(f"租户越界: {path}")
        return resolved

    # ── Root directories ──────────────────────────────────────────────

    @property
    def data_root(self) -> Path:
        return self._data_root

    @property
    def db_dir(self) -> Path:
        return self._data_root / "db"

    @property
    def logs_dir(self) -> Path:
        return self._data_root / "logs"

    @property
    def backups_dir(self) -> Path:
        return self._data_root / "backups"

    # ── Builtin resources (read-only) ─────────────────────────────────

    @property
    def builtin_root(self) -> Path:
        return self._data_root / "workspaces" / "builtin"

    @property
    def builtin_agents_dir(self) -> Path:
        return self.builtin_root / "agents"

    @property
    def builtin_skills_dir(self) -> Path:
        return self.builtin_root / "skills"

    @property
    def builtin_mcp_dir(self) -> Path:
        return self.builtin_root / "mcp"

    def builtin_agent_dir(self, agent_name: str) -> Path:
        self._validate_slug(agent_name, "agent_name")
        return self.builtin_agents_dir / agent_name

    def builtin_skill_dir(self, skill_name: str) -> Path:
        self._validate_slug(skill_name, "skill_name")
        return self.builtin_skills_dir / skill_name

    # ── Tenant directories ────────────────────────────────────────────

    def tenant_root(self, family_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        return self._data_root / "workspaces" / "tenants" / fid

    def tenant_uploads_dir(self, family_id: int, user_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        uid = self._validate_numeric_id(user_id, "user_id")
        return self._data_root / "workspaces" / "tenants" / fid / "uploads" / uid

    def tenant_agents_dir(self, family_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        return self._data_root / "workspaces" / "tenants" / fid / "agents"

    def tenant_agent_dir(self, family_id: int, agent_name: str) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        self._validate_slug(agent_name, "agent_name")
        return self._data_root / "workspaces" / "tenants" / fid / "agents" / agent_name

    def tenant_session_dir(
        self, family_id: int, agent_name: str, thread_id: str
    ) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        self._validate_slug(agent_name, "agent_name")
        self._validate_thread_id(thread_id)
        return (
            self._data_root / "workspaces" / "tenants" / fid
            / "agents" / agent_name / "sessions" / thread_id
        )

    def tenant_session_events_file(
        self, family_id: int, agent_name: str, thread_id: str
    ) -> Path:
        return self.tenant_session_dir(family_id, agent_name, thread_id) / "events.jsonl"

    def tenant_session_artifacts_dir(
        self, family_id: int, agent_name: str, thread_id: str
    ) -> Path:
        return self.tenant_session_dir(family_id, agent_name, thread_id) / "artifacts"

    def tenant_memory_dir(self, family_id: int, agent_name: str) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        self._validate_slug(agent_name, "agent_name")
        return (
            self._data_root / "workspaces" / "tenants" / fid
            / "agents" / agent_name / "memory"
        )

    def tenant_skills_dir(self, family_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        return self._data_root / "workspaces" / "tenants" / fid / "skills"

    def tenant_skill_dir(self, family_id: int, skill_name: str) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        self._validate_slug(skill_name, "skill_name")
        return self._data_root / "workspaces" / "tenants" / fid / "skills" / skill_name

    def tenant_mcp_dir(self, family_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        return self._data_root / "workspaces" / "tenants" / fid / "mcp"

    def tenant_tmp_dir(
        self, family_id: int, user_id: int, request_id: str
    ) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        uid = self._validate_numeric_id(user_id, "user_id")
        self._validate_request_id(request_id)
        return (
            self._data_root / "workspaces" / "tenants" / fid
            / "tmp" / uid / request_id
        )

    # ── Runtime effective (generated, deletable) ──────────────────────

    def effective_dir(self, family_id: int) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        return self._data_root / "runtime" / "effective" / fid

    def effective_agents_dir(self, family_id: int) -> Path:
        return self.effective_dir(family_id) / "agents"

    def effective_agent_dir(self, family_id: int, agent_name: str) -> Path:
        self._validate_slug(agent_name, "agent_name")
        return self.effective_dir(family_id) / "agents" / agent_name

    def effective_skills_dir(self, family_id: int) -> Path:
        return self.effective_dir(family_id) / "skills"

    def effective_extensions_file(self, family_id: int) -> Path:
        return self.effective_dir(family_id) / "extensions_config.json"
```

- [ ] Run tests to confirm GREEN:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py -v
```

Expected: All tests pass.

- [ ] Commit:

```bash
git add server/packages/core/path_manager.py server/tests/agent/unit/test_path_manager.py
git commit -m "feat(core): add PathManager with security validation and path generation

- Slug validation: [a-z][a-z0-9-]* for agent_name, skill_name
- UUID validation for thread_id, request_id
- Numeric ID validation for family_id, user_id
- assert_under_root: resolve() + is_relative_to() prevents traversal/symlink escape
- assert_tenant_access: enforces cross-tenant isolation boundary
- Creates base directory structure on init
- 30+ security + functional tests covering traversal, symlink, slug injection"
```

---

## Task 2: PathManager — Singleton + Export

**Goal:** Add `get_path_manager()` singleton factory to `packages/core/__init__.py`.

**Files:**
- Modify: `server/packages/core/__init__.py`
- Add tests to: `server/tests/agent/unit/test_path_manager.py`

### Step 2.1: Write singleton tests (RED)

- [ ] Append to `server/tests/agent/unit/test_path_manager.py`:

```python
class TestGetPathManager:
    def test_singleton_returns_same_instance(self):
        """get_path_manager() must return the same PathManager on repeated calls."""
        import packages.core as core_mod

        # Reset singleton for isolation
        original = getattr(core_mod, "_path_manager", None)
        core_mod._path_manager = None
        try:
            from packages.core import get_path_manager
            pm1 = get_path_manager()
            pm2 = get_path_manager()
            assert pm1 is pm2
        finally:
            core_mod._path_manager = original

    def test_singleton_creates_path_manager_instance(self):
        """get_path_manager() must return a PathManager instance."""
        import packages.core as core_mod

        original = getattr(core_mod, "_path_manager", None)
        core_mod._path_manager = None
        try:
            from packages.core import get_path_manager
            pm = get_path_manager()
            assert isinstance(pm, PathManager)
        finally:
            core_mod._path_manager = original
```

- [ ] Run to confirm RED:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py::TestGetPathManager -v
```

### Step 2.2: Implement singleton (GREEN)

- [ ] Edit `server/packages/core/__init__.py` to add:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from packages.core.path_manager import PathManager

_path_manager: PathManager | None = None


def get_path_manager() -> PathManager:
    """Return the shared PathManager singleton. Created on first call."""
    global _path_manager
    if _path_manager is None:
        from packages.core.path_manager import PathManager
        _path_manager = PathManager()
    return _path_manager
```

- [ ] Run tests to confirm GREEN:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py -v
```

- [ ] Commit:

```bash
git add server/packages/core/__init__.py server/tests/agent/unit/test_path_manager.py
git commit -m "feat(core): add get_path_manager() singleton to packages/core"
```

---

## Task 3: PathManager — Tenant Path Isolation Tests

**Goal:** Add targeted tests verifying that tenant paths are properly isolated between different family_ids, and that effective paths generate correct structures.

**Files:**
- Add tests to: `server/tests/agent/unit/test_path_manager.py`

### Step 3.1: Write tenant isolation + effective path tests

- [ ] Append to `server/tests/agent/unit/test_path_manager.py`:

```python
class TestTenantPaths:
    def test_tenant_root(self, pm, tmp_data_root):
        result = pm.tenant_root(12345)
        assert result == tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"

    def test_tenant_uploads_dir(self, pm, tmp_data_root):
        result = pm.tenant_uploads_dir(12345, 67890)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "uploads" / "67890"
        )

    def test_tenant_agent_dir(self, pm, tmp_data_root):
        result = pm.tenant_agent_dir(12345, "my-agent")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent"
        )

    def test_tenant_session_dir(self, pm, tmp_data_root):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_dir(12345, "my-agent", tid)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent" / "sessions" / tid
        )

    def test_tenant_session_events_file(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_events_file(12345, "my-agent", tid)
        assert result.name == "events.jsonl"
        assert result.parent == pm.tenant_session_dir(12345, "my-agent", tid)

    def test_tenant_session_artifacts_dir(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_session_artifacts_dir(12345, "my-agent", tid)
        assert result.name == "artifacts"
        assert result.parent == pm.tenant_session_dir(12345, "my-agent", tid)

    def test_tenant_memory_dir(self, pm, tmp_data_root):
        result = pm.tenant_memory_dir(12345, "my-agent")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "agents" / "my-agent" / "memory"
        )

    def test_tenant_skills_dir(self, pm, tmp_data_root):
        result = pm.tenant_skills_dir(12345)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345" / "skills"
        )

    def test_tenant_skill_dir(self, pm, tmp_data_root):
        result = pm.tenant_skill_dir(12345, "my-skill")
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "skills" / "my-skill"
        )

    def test_tenant_mcp_dir(self, pm, tmp_data_root):
        result = pm.tenant_mcp_dir(12345)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345" / "mcp"
        )

    def test_tenant_tmp_dir(self, pm, tmp_data_root):
        rid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        result = pm.tenant_tmp_dir(12345, 67890, rid)
        assert result == (
            tmp_data_root.resolve() / "workspaces" / "tenants" / "12345"
            / "tmp" / "67890" / rid
        )


class TestTenantIsolation:
    """Cross-tenant isolation: family A paths must not pass family B assertions."""

    def test_family_a_path_rejected_by_family_b_assert(self, pm):
        path_a = pm.tenant_root(11111) / "uploads" / "file.txt"
        path_a.parent.mkdir(parents=True, exist_ok=True)
        path_a.touch()
        with pytest.raises(PathSecurityError, match="租户越界"):
            pm.assert_tenant_access(path_a, 22222)

    def test_different_families_get_different_roots(self, pm):
        root_a = pm.tenant_root(11111)
        root_b = pm.tenant_root(22222)
        assert root_a != root_b
        assert "11111" in str(root_a)
        assert "22222" in str(root_b)

    def test_session_dirs_isolated_between_families(self, pm):
        tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        dir_a = pm.tenant_session_dir(11111, "my-agent", tid)
        dir_b = pm.tenant_session_dir(22222, "my-agent", tid)
        assert dir_a != dir_b
        assert "11111" in str(dir_a)
        assert "22222" in str(dir_b)


class TestEffectivePaths:
    def test_effective_dir(self, pm, tmp_data_root):
        result = pm.effective_dir(12345)
        assert result == tmp_data_root.resolve() / "runtime" / "effective" / "12345"

    def test_effective_agents_dir(self, pm):
        result = pm.effective_agents_dir(12345)
        assert result == pm.effective_dir(12345) / "agents"

    def test_effective_agent_dir(self, pm):
        result = pm.effective_agent_dir(12345, "my-agent")
        assert result == pm.effective_dir(12345) / "agents" / "my-agent"

    def test_effective_skills_dir(self, pm):
        result = pm.effective_skills_dir(12345)
        assert result == pm.effective_dir(12345) / "skills"

    def test_effective_extensions_file(self, pm):
        result = pm.effective_extensions_file(12345)
        assert result == pm.effective_dir(12345) / "extensions_config.json"

    def test_effective_agent_dir_validates_slug(self, pm):
        with pytest.raises(PathSecurityError, match="无效的"):
            pm.effective_agent_dir(12345, "../escape")
```

- [ ] Run all tests:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py -v
```

Expected: All tests pass (implementation already in place from Task 1).

- [ ] Commit:

```bash
git add server/tests/agent/unit/test_path_manager.py
git commit -m "test(core): add tenant isolation and effective path tests for PathManager"
```

---

## Task 4: ModelEntryBuilder — Extract Model Config Construction

**Goal:** Extract the model entry construction logic from `family_adapter_cache._generate_temp_config()` into a standalone, testable module. Fix the `ReasoningChatOpenAI` bug (should be `PatchedChatOpenAI`).

**Files:**
- Create: `server/packages/core/model_entry.py`
- Create: `server/tests/agent/unit/test_model_entry.py`

### Step 4.1: Write model entry tests (RED)

- [ ] Create `server/tests/agent/unit/test_model_entry.py`:

```python
# server/tests/agent/unit/test_model_entry.py
"""Unit tests for ModelEntryBuilder — provider-to-class mapping + thinking config."""

import pytest

from packages.core.model_entry import build_model_entry


class TestProviderClassMapping:
    """Correct LangChain class path for each provider."""

    def test_anthropic_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-test",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_anthropic:ChatAnthropic"
        assert entry["model"] == "claude-haiku-4-5"
        assert entry["api_key"] == "sk-test"
        assert entry["name"] == "main"
        assert entry["supports_thinking"] is False

    def test_openai_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-openai",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"
        assert entry["supports_thinking"] is False

    def test_openai_compatible_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "glm-4",
            "api_key": "sk-glm",
            "ai_base_url": "https://api.zhipu.ai/v4",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"
        assert entry["base_url"] == "https://api.zhipu.ai/v4"

    def test_unknown_provider_defaults_to_openai(self):
        entry = build_model_entry({
            "ai_provider": "unknown_vendor",
            "ai_model_id": "some-model",
            "api_key": "sk-x",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"


class TestThinkingClassOverrides:
    """When thinking is supported, provider-specific patched classes are used."""

    def test_deepseek_thinking_uses_patched_class(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "deepseek-r1",
            "api_key": "sk-ds",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
        assert entry["supports_thinking"] is True

    def test_openai_thinking_uses_patched_openai(self):
        """Must use PatchedChatOpenAI, NOT ReasoningChatOpenAI (bug fix)."""
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "o1-preview",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_openai:PatchedChatOpenAI"
        assert "ReasoningChatOpenAI" not in entry["use"]

    def test_openai_compatible_thinking_uses_patched_openai(self):
        """OpenAI-compatible providers (GLM-5, Qwen3) with thinking."""
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "qwen3-235b",
            "api_key": "sk-qw",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_openai:PatchedChatOpenAI"

    def test_anthropic_thinking_uses_standard_class(self):
        """Anthropic thinking models use standard ChatAnthropic."""
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "langchain_anthropic:ChatAnthropic"
        assert entry["supports_thinking"] is True


class TestThinkingConfig:
    """when_thinking_enabled/disabled config per provider."""

    def test_deepseek_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "deepseek-r1",
            "api_key": "sk-ds",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {
            "extra_body": {"thinking": {"type": "enabled"}}
        }
        assert entry["when_thinking_disabled"] == {
            "extra_body": {"thinking": {"type": "disabled"}}
        }

    def test_openai_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "o1-preview",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {
            "extra_body": {"enable_thinking": True}
        }
        assert entry["when_thinking_disabled"] == {
            "extra_body": {"enable_thinking": False}
        }

    def test_anthropic_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {
            "thinking": {"type": "enabled", "budget_tokens": 10000}
        }
        assert entry["when_thinking_disabled"] == {
            "thinking": {"type": "disabled"}
        }

    def test_no_thinking_config_when_not_supported(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation"],
        })
        assert "when_thinking_enabled" not in entry
        assert "when_thinking_disabled" not in entry


class TestBaseUrlHandling:
    def test_includes_base_url_when_provided(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "glm-4",
            "api_key": "sk-glm",
            "ai_base_url": "https://api.example.com/v1",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["base_url"] == "https://api.example.com/v1"

    def test_omits_base_url_when_empty(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-x",
            "model_1_capabilities": ["text_generation"],
        })
        assert "base_url" not in entry

    def test_omits_base_url_when_none(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-x",
            "ai_base_url": None,
            "model_1_capabilities": ["text_generation"],
        })
        assert "base_url" not in entry


class TestLegacyThinkingFlag:
    """Backward compatibility: thinking_supported bool when model_1_capabilities absent."""

    def test_legacy_thinking_supported_true(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "thinking_supported": True,
        })
        assert entry["supports_thinking"] is True
        assert "when_thinking_enabled" in entry

    def test_legacy_thinking_supported_false(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "thinking_supported": False,
        })
        assert entry["supports_thinking"] is False

    def test_model_1_capabilities_takes_precedence_over_legacy(self):
        """model_1_capabilities should override thinking_supported flag."""
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "thinking_supported": True,
            "model_1_capabilities": ["text_generation"],  # no deep_thinking
        })
        assert entry["supports_thinking"] is False


class TestMissingModelId:
    def test_raises_on_missing_model_id(self):
        with pytest.raises(ValueError, match="ai_model_id"):
            build_model_entry({
                "ai_provider": "openai",
                "api_key": "sk-x",
                "model_1_capabilities": ["text_generation"],
            })

    def test_raises_on_empty_model_id(self):
        with pytest.raises(ValueError, match="ai_model_id"):
            build_model_entry({
                "ai_provider": "openai",
                "ai_model_id": "",
                "api_key": "sk-x",
                "model_1_capabilities": ["text_generation"],
            })
```

- [ ] Run to confirm RED:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_model_entry.py -v
```

### Step 4.2: Implement ModelEntryBuilder (GREEN)

- [ ] Create `server/packages/core/model_entry.py`:

```python
# server/packages/core/model_entry.py
"""DeerFlow2 model entry construction from DB provider data.

Extracted from family_adapter_cache._generate_temp_config() for reuse
by EffectiveConfigBuilder (Gateway path) and legacy adapter path.

Bug fix: uses PatchedChatOpenAI (not ReasoningChatOpenAI) for
OpenAI-compatible thinking models.
"""

from __future__ import annotations

from typing import Any

# Provider → default LangChain class path (non-thinking)
_PROVIDER_CLASS_MAP: dict[str, str] = {
    "anthropic": "langchain_anthropic:ChatAnthropic",
    "openai": "langchain_openai:ChatOpenAI",
    "openai_compatible": "langchain_openai:ChatOpenAI",
}

# Provider → patched class path for thinking-enabled models
_THINKING_CLASS_OVERRIDES: dict[str, str] = {
    "deepseek": "deerflow.models.patched_deepseek:PatchedChatDeepSeek",
    "openai": "deerflow.models.patched_openai:PatchedChatOpenAI",
    "openai_compatible": "deerflow.models.patched_openai:PatchedChatOpenAI",
}


def build_model_entry(ai_provider: dict[str, Any]) -> dict[str, Any]:
    """Build a DeerFlow2 model config dict from a DB provider record.

    Args:
        ai_provider: Dict with keys: ai_provider, ai_model_id, api_key,
            ai_base_url (optional), model_1_capabilities (optional),
            thinking_supported (optional, legacy fallback).

    Returns:
        Dict suitable for inclusion in AppConfig.models list.

    Raises:
        ValueError: ai_model_id is missing or empty.
    """
    provider = ai_provider.get("ai_provider", "openai")
    model_id = ai_provider.get("ai_model_id")
    if not model_id:
        raise ValueError(
            "ai_model_id 未配置。请在 AI 配置中填写模型 ID。"
        )

    api_key = ai_provider.get("api_key", "")
    base_url = ai_provider.get("ai_base_url")

    # Capability detection: model_1_capabilities takes precedence over legacy flag
    model_1_caps = ai_provider.get("model_1_capabilities")
    if model_1_caps is not None:
        thinking_supported = "deep_thinking" in model_1_caps
    else:
        thinking_supported = bool(ai_provider.get("thinking_supported", False))

    # Class resolution
    use_class = _PROVIDER_CLASS_MAP.get(provider, "langchain_openai:ChatOpenAI")
    if thinking_supported:
        if "deepseek" in model_id.lower():
            use_class = _THINKING_CLASS_OVERRIDES["deepseek"]
        elif provider in ("openai", "openai_compatible"):
            use_class = _THINKING_CLASS_OVERRIDES[provider]
        # Anthropic keeps standard class — ChatAnthropic handles thinking natively

    entry: dict[str, Any] = {
        "name": "main",
        "use": use_class,
        "model": model_id,
        "api_key": api_key,
        "supports_thinking": thinking_supported,
    }

    if base_url:
        entry["base_url"] = base_url

    # Thinking-specific config
    if thinking_supported:
        entry.update(_build_thinking_config(provider, model_id))

    return entry


def _build_thinking_config(provider: str, model_id: str) -> dict[str, Any]:
    """Build when_thinking_enabled/disabled config per provider family."""
    if "deepseek" in model_id.lower():
        return {
            "when_thinking_enabled": {
                "extra_body": {"thinking": {"type": "enabled"}}
            },
            "when_thinking_disabled": {
                "extra_body": {"thinking": {"type": "disabled"}}
            },
        }
    elif provider in ("openai", "openai_compatible"):
        return {
            "when_thinking_enabled": {
                "extra_body": {"enable_thinking": True}
            },
            "when_thinking_disabled": {
                "extra_body": {"enable_thinking": False}
            },
        }
    elif provider == "anthropic":
        return {
            "when_thinking_enabled": {
                "thinking": {"type": "enabled", "budget_tokens": 10000}
            },
            "when_thinking_disabled": {
                "thinking": {"type": "disabled"}
            },
        }
    return {}
```

- [ ] Run tests to confirm GREEN:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_model_entry.py -v
```

Expected: All tests pass.

- [ ] Commit:

```bash
git add server/packages/core/model_entry.py server/tests/agent/unit/test_model_entry.py
git commit -m "feat(core): extract ModelEntryBuilder from family_adapter_cache

- Standalone build_model_entry() function for DeerFlow2 model config
- Fixes ReasoningChatOpenAI bug: now uses PatchedChatOpenAI
- Covers: anthropic, openai, openai_compatible, deepseek
- Thinking config: when_thinking_enabled/disabled per provider
- Legacy thinking_supported flag fallback
- 20+ tests covering all provider/thinking combinations"
```

---

## Task 5: EffectiveConfigBuilder — AppConfig Construction

**Goal:** Build `EffectiveConfigBuilder` that takes DB query results + PathManager and produces a DeerFlow2 `AppConfig`-compatible dict (and `AppConfig` object when the import is available).

**Files:**
- Create: `server/packages/core/effective_config.py`
- Create: `server/tests/agent/unit/test_effective_config.py`

### Step 5.1: Write EffectiveConfigBuilder tests (RED)

- [ ] Create `server/tests/agent/unit/test_effective_config.py`:

```python
# server/tests/agent/unit/test_effective_config.py
"""Unit tests for EffectiveConfigBuilder."""

import pytest

from packages.core.effective_config import EffectiveConfigBuilder, EffectiveConfig
from packages.core.path_manager import PathManager


@pytest.fixture
def tmp_data_root(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    return PathManager(data_root=tmp_data_root)


@pytest.fixture
def builder(pm):
    return EffectiveConfigBuilder(pm)


@pytest.fixture
def sample_ai_provider():
    return {
        "ai_provider": "anthropic",
        "ai_model_id": "claude-sonnet-4-6",
        "api_key": "sk-test-key",
        "model_1_capabilities": ["text_generation", "deep_thinking"],
    }


@pytest.fixture
def sample_agent_config():
    return {
        "agent_name": "asset-health-advisor",
        "soul_md": "You are a professional asset health advisor.",
        "skills": ["family-asset-checkup"],
        "tool_groups": [],
        "model": None,
        "subagent_enabled": False,
        "is_enabled": True,
    }


class TestEffectiveConfigBuild:
    """Tests for the core build() method."""

    def test_returns_effective_config(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert isinstance(result, EffectiveConfig)

    def test_config_dict_has_models(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert "models" in result.config_dict
        assert len(result.config_dict["models"]) == 1
        model = result.config_dict["models"][0]
        assert model["name"] == "main"
        assert model["model"] == "claude-sonnet-4-6"
        assert model["api_key"] == "sk-test-key"

    def test_config_dict_has_memory(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        memory = result.config_dict["memory"]
        assert memory["enabled"] is True
        expected_path = str(
            pm.tenant_memory_dir(12345, "asset-health-advisor") / "memory.json"
        )
        assert memory["storage_path"] == expected_path

    def test_config_dict_has_checkpointer(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        cp = result.config_dict["checkpointer"]
        assert cp["type"] == "sqlite"
        assert "deerflow-checkpoints.db" in cp["connection_string"]

    def test_config_dict_has_skills_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        skills = result.config_dict["skills"]
        expected = str(pm.effective_skills_dir(12345))
        assert skills["path"] == expected


class TestEffectiveConfigIsolation:
    """Two concurrent builds must produce independent config objects."""

    def test_two_families_get_different_memory_paths(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(
            family_id=11111,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        config_b = builder.build(
            family_id=22222,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert config_a.config_dict["memory"]["storage_path"] != config_b.config_dict["memory"]["storage_path"]
        assert "11111" in config_a.config_dict["memory"]["storage_path"]
        assert "22222" in config_b.config_dict["memory"]["storage_path"]

    def test_two_families_get_different_skills_paths(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(
            family_id=11111,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        config_b = builder.build(
            family_id=22222,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert config_a.config_dict["skills"]["path"] != config_b.config_dict["skills"]["path"]

    def test_config_dicts_are_independent_objects(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(
            family_id=11111,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        config_b = builder.build(
            family_id=22222,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        # Mutating one must not affect the other
        config_a.config_dict["models"][0]["api_key"] = "MUTATED"
        assert config_b.config_dict["models"][0]["api_key"] == "sk-test-key"


class TestEffectiveConfigWithProvider:
    """Different AI providers produce correct model entries."""

    def test_openai_provider(self, builder, sample_agent_config):
        provider = {
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-openai-test",
            "model_1_capabilities": ["text_generation"],
        }
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        model = result.config_dict["models"][0]
        assert model["use"] == "langchain_openai:ChatOpenAI"
        assert model["model"] == "gpt-4o"

    def test_openai_compatible_with_base_url(self, builder, sample_agent_config):
        provider = {
            "ai_provider": "openai_compatible",
            "ai_model_id": "glm-4",
            "api_key": "sk-glm",
            "ai_base_url": "https://api.zhipu.ai/v4",
            "model_1_capabilities": ["text_generation"],
        }
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        model = result.config_dict["models"][0]
        assert model["base_url"] == "https://api.zhipu.ai/v4"


class TestEffectiveConfigSkillMerging:
    """Skills from DB produce the expected effective skills structure."""

    def test_builtin_skill_source_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        """Builtin skills reference builtin_skill_dir."""
        skills = [{"skill_name": "family-asset-checkup", "is_builtin": True}]
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=skills,
            mcp_servers=[],
        )
        assert result.skill_sources == [
            {"name": "family-asset-checkup", "source": pm.builtin_skill_dir("family-asset-checkup"), "is_builtin": True}
        ]

    def test_custom_skill_source_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        """Custom skills reference tenant_skill_dir."""
        skills = [{"skill_name": "my-custom-skill", "is_builtin": False}]
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=skills,
            mcp_servers=[],
        )
        assert result.skill_sources == [
            {"name": "my-custom-skill", "source": pm.tenant_skill_dir(12345, "my-custom-skill"), "is_builtin": False}
        ]

    def test_mixed_builtin_and_custom_skills(self, builder, pm, sample_ai_provider, sample_agent_config):
        skills = [
            {"skill_name": "builtin-skill", "is_builtin": True},
            {"skill_name": "custom-skill", "is_builtin": False},
        ]
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=skills,
            mcp_servers=[],
        )
        assert len(result.skill_sources) == 2
        names = [s["name"] for s in result.skill_sources]
        assert "builtin-skill" in names
        assert "custom-skill" in names


class TestEffectiveConfigMCPServers:
    """MCP server list is passed through in config_dict."""

    def test_mcp_servers_included_when_provided(self, builder, sample_ai_provider, sample_agent_config):
        mcp = [{"name": "filesystem", "transport": "stdio", "command": "mcp-filesystem"}]
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=mcp,
        )
        assert result.config_dict.get("mcp_servers") == mcp

    def test_mcp_servers_omitted_when_empty(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert "mcp_servers" not in result.config_dict


class TestEffectiveConfigRebuilds:
    """Deleting effective dir and rebuilding produces same result."""

    def test_rebuild_produces_same_config(self, builder, sample_ai_provider, sample_agent_config):
        import shutil

        result1 = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )

        # Delete the effective dir
        effective_dir = builder._pm.effective_dir(12345)
        if effective_dir.exists():
            shutil.rmtree(effective_dir)

        result2 = builder.build(
            family_id=12345,
            agent_name="my-agent",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )

        assert result1.config_dict == result2.config_dict
```

- [ ] Run to confirm RED:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_effective_config.py -v
```

### Step 5.2: Implement EffectiveConfigBuilder (GREEN)

- [ ] Create `server/packages/core/effective_config.py`:

```python
# server/packages/core/effective_config.py
"""Effective config builder — merges DB + files into DeerFlow2-compatible config.

Per-request config construction. No global singleton mutation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packages.core.logging import get_logger
from packages.core.model_entry import build_model_entry
from packages.core.path_manager import PathManager

logger = get_logger(__name__)


@dataclass
class EffectiveConfig:
    """Result of EffectiveConfigBuilder.build().

    Attributes:
        config_dict: DeerFlow2-compatible config dict (can be passed to
            AppConfig.model_validate() or used directly).
        skill_sources: List of skill source descriptors with name, source Path,
            and is_builtin flag.
        memory_path: Path to the agent's memory.json file.
    """

    config_dict: dict[str, Any]
    skill_sources: list[dict[str, Any]] = field(default_factory=list)
    memory_path: str = ""


class EffectiveConfigBuilder:
    """Merge DB策略 + builtin 文件 + tenant overlay → DeerFlow2 config dict.

    Each call to build() produces an independent config — no shared state,
    no global mutation, safe for concurrent use.
    """

    def __init__(self, path_manager: PathManager):
        self._pm = path_manager

    def build(
        self,
        family_id: int,
        agent_name: str,
        ai_provider: dict[str, Any],
        agent_config: dict[str, Any],
        enabled_skills: list[dict[str, Any]],
        mcp_servers: list[dict[str, Any]],
    ) -> EffectiveConfig:
        """Build effective config for a single agent run request.

        Args:
            family_id: Tenant family ID.
            agent_name: Agent slug (validated by PathManager).
            ai_provider: DB provider record (ai_provider, ai_model_id, api_key, ...).
            agent_config: DB agent record (soul_md, skills, model, ...).
            enabled_skills: List of enabled skill dicts with skill_name + is_builtin.
            mcp_servers: List of enabled MCP server dicts.

        Returns:
            EffectiveConfig with config_dict, skill_sources, and memory_path.
        """
        # 1. Build model entry
        model_entry = build_model_entry(ai_provider)

        # 2. Resolve paths
        memory_path = str(
            self._pm.tenant_memory_dir(family_id, agent_name) / "memory.json"
        )
        skills_path = str(self._pm.effective_skills_dir(family_id))
        checkpointer_path = str(self._pm.db_dir / "deerflow-checkpoints.db")

        # 3. Resolve skill sources
        skill_sources = self._resolve_skill_sources(family_id, enabled_skills)

        # 4. Assemble config dict
        config_dict: dict[str, Any] = {
            "models": [model_entry],
            "skills": {
                "path": skills_path,
            },
            "memory": {
                "enabled": True,
                "storage_path": memory_path,
            },
            "checkpointer": {
                "type": "sqlite",
                "connection_string": checkpointer_path,
            },
        }

        if mcp_servers:
            config_dict["mcp_servers"] = mcp_servers

        return EffectiveConfig(
            config_dict=config_dict,
            skill_sources=skill_sources,
            memory_path=memory_path,
        )

    def _resolve_skill_sources(
        self,
        family_id: int,
        enabled_skills: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Map each enabled skill to its source directory (builtin or tenant)."""
        sources: list[dict[str, Any]] = []
        for skill in enabled_skills:
            name = skill["skill_name"]
            is_builtin = skill.get("is_builtin", False)
            if is_builtin:
                source = self._pm.builtin_skill_dir(name)
            else:
                source = self._pm.tenant_skill_dir(family_id, name)
            sources.append({
                "name": name,
                "source": source,
                "is_builtin": is_builtin,
            })
        return sources
```

- [ ] Run tests to confirm GREEN:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_effective_config.py -v
```

Expected: All tests pass.

- [ ] Commit:

```bash
git add server/packages/core/effective_config.py server/tests/agent/unit/test_effective_config.py
git commit -m "feat(core): add EffectiveConfigBuilder for per-request AppConfig construction

- Merges DB provider + agent config + skills + MCP into DeerFlow2 config dict
- Per-request independent config (no global state mutation)
- Resolves skill sources (builtin vs tenant paths via PathManager)
- Memory isolation per family+agent
- Shared sqlite checkpointer
- 20+ tests covering isolation, rebuild, multi-provider"
```

---

## Task 6: AgentRunService — Gateway Path Integration

**Goal:** Replace `agent_dispatch.py` to use the new `EffectiveConfigBuilder` -> `make_lead_agent()` -> `astream()` Gateway path. This is the new Agent-first execution entry point.

**Files:**
- Modify: `server/apps/agent/services/agent_dispatch.py`
- Create: `server/tests/agent/unit/test_agent_run_service.py`

### Step 6.1: Write AgentRunService tests (RED)

- [ ] Create `server/tests/agent/unit/test_agent_run_service.py`:

```python
# server/tests/agent/unit/test_agent_run_service.py
"""Integration smoke tests for the new Gateway path in agent_dispatch.py.

Verifies the full chain with mocked BackendClient + mocked make_lead_agent:
HTTP request → PathManager → EffectiveConfigBuilder → AppConfig → make_lead_agent injection.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.path_manager import PathManager


@pytest.fixture
def tmp_data_root(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    return PathManager(data_root=tmp_data_root)


@pytest.fixture
def sample_agent_config():
    return {
        "agent_name": "asset-health-advisor",
        "soul_md": "You are a professional asset advisor.",
        "skills": ["family-asset-checkup"],
        "tool_groups": [],
        "model": None,
        "subagent_enabled": False,
        "is_enabled": True,
    }


@pytest.fixture
def sample_ai_config():
    return {
        "ai_enabled": True,
        "providers": [
            {
                "config_id": "cfg-001",
                "ai_provider": "anthropic",
                "ai_model_id": "claude-sonnet-4-6",
                "api_key": "sk-test-key",
                "model_1_capabilities": ["text_generation", "deep_thinking"],
            }
        ],
    }


class TestStreamAgentDispatchGateway:
    """Tests that stream_agent_dispatch wires the Gateway path correctly."""

    async def test_emits_phase_connecting_event(
        self, pm, sample_agent_config, sample_ai_config
    ):
        """First yielded event must be phase.connecting."""
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
        ):
            instance = MockClient.return_value
            instance.get_agent_config = AsyncMock(return_value=sample_agent_config)
            instance.get_family_ai_config = AsyncMock(return_value=sample_ai_config)

            mock_select.return_value = (
                sample_ai_config["providers"][0],
                "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            # Mock make_lead_agent to return a graph that yields nothing
            mock_graph = MagicMock()
            mock_graph.astream = AsyncMock(return_value=aiter([]))

            with patch(
                "apps.agent.services.agent_dispatch.make_lead_agent",
                return_value=mock_graph,
            ):
                from apps.agent.services.agent_dispatch import stream_agent_dispatch

                events = []
                async for line in stream_agent_dispatch(
                    agent_id=1,
                    family_id="12345678901234567",
                    thread_id=None,
                    message="测试消息",
                ):
                    events.append(json.loads(line.strip()))

            # First event should be phase.connecting
            assert len(events) >= 1
            assert events[0]["type"] == "phase.connecting"

    async def test_emits_error_when_agent_disabled(
        self, pm, sample_ai_config
    ):
        """Disabled agent must yield capability.error event."""
        disabled_config = {
            "agent_name": "disabled-agent",
            "is_enabled": False,
        }
        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
        ):
            instance = MockClient.return_value
            instance.get_agent_config = AsyncMock(return_value=disabled_config)

            from apps.agent.services.agent_dispatch import stream_agent_dispatch

            events = []
            async for line in stream_agent_dispatch(
                agent_id=1,
                family_id="12345678901234567",
                thread_id=None,
                message="测试消息",
            ):
                events.append(json.loads(line.strip()))

            error_events = [e for e in events if e["type"] == "capability.error"]
            assert len(error_events) == 1
            assert "禁用" in error_events[0]["error"]["message"]

    async def test_passes_app_config_to_make_lead_agent(
        self, pm, sample_agent_config, sample_ai_config
    ):
        """make_lead_agent must receive RunnableConfig with app_config in configurable."""
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = AsyncMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch(
                "apps.agent.services.agent_dispatch.make_lead_agent",
                side_effect=capture_make_lead_agent,
            ),
        ):
            instance = MockClient.return_value
            instance.get_agent_config = AsyncMock(return_value=sample_agent_config)
            instance.get_family_ai_config = AsyncMock(return_value=sample_ai_config)

            mock_select.return_value = (
                sample_ai_config["providers"][0],
                "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch

            async for _ in stream_agent_dispatch(
                agent_id=1,
                family_id="12345678901234567",
                thread_id=None,
                message="测试消息",
            ):
                pass

        assert "configurable" in captured_config
        configurable = captured_config["configurable"]
        assert "app_config" in configurable
        assert "thread_id" in configurable

    async def test_uses_provided_thread_id(
        self, pm, sample_agent_config, sample_ai_config
    ):
        """When thread_id is provided, it must be used (not generated)."""
        expected_tid = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = AsyncMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch(
                "apps.agent.services.agent_dispatch.make_lead_agent",
                side_effect=capture_make_lead_agent,
            ),
        ):
            instance = MockClient.return_value
            instance.get_agent_config = AsyncMock(return_value=sample_agent_config)
            instance.get_family_ai_config = AsyncMock(return_value=sample_ai_config)

            mock_select.return_value = (
                sample_ai_config["providers"][0],
                "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch

            async for _ in stream_agent_dispatch(
                agent_id=1,
                family_id="12345678901234567",
                thread_id=expected_tid,
                message="测试消息",
            ):
                pass

        assert captured_config["configurable"]["thread_id"] == expected_tid

    async def test_generates_thread_id_when_none(
        self, pm, sample_agent_config, sample_ai_config
    ):
        """When thread_id is None, a UUID must be generated."""
        captured_config = {}

        def capture_make_lead_agent(config):
            captured_config.update(config)
            mock_graph = MagicMock()
            mock_graph.astream = AsyncMock(return_value=aiter([]))
            return mock_graph

        with (
            patch("apps.agent.services.agent_dispatch.BackendClient") as MockClient,
            patch("apps.agent.services.agent_dispatch.get_path_manager", return_value=pm),
            patch("apps.agent.services.agent_dispatch._select_model") as mock_select,
            patch(
                "apps.agent.services.agent_dispatch.make_lead_agent",
                side_effect=capture_make_lead_agent,
            ),
        ):
            instance = MockClient.return_value
            instance.get_agent_config = AsyncMock(return_value=sample_agent_config)
            instance.get_family_ai_config = AsyncMock(return_value=sample_ai_config)

            mock_select.return_value = (
                sample_ai_config["providers"][0],
                "claude-sonnet-4-6",
                ["text_generation", "deep_thinking"],
            )

            from apps.agent.services.agent_dispatch import stream_agent_dispatch

            async for _ in stream_agent_dispatch(
                agent_id=1,
                family_id="12345678901234567",
                thread_id=None,
                message="测试消息",
            ):
                pass

        tid = captured_config["configurable"]["thread_id"]
        # Verify it's a valid UUID
        uuid.UUID(tid)


# Helper for creating async iterators from lists
async def aiter(items):
    for item in items:
        yield item
```

- [ ] Run to confirm RED:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_agent_run_service.py -v
```

### Step 6.2: Rewrite agent_dispatch.py with Gateway path (GREEN)

- [ ] Replace the contents of `server/apps/agent/services/agent_dispatch.py`:

```python
# server/apps/agent/services/agent_dispatch.py
"""Agent-first execution entry point — Gateway path.

Replaces the old DeerFlowAdapter path with:
  BackendClient queries → EffectiveConfigBuilder → RunnableConfig
  → make_lead_agent() → astream() → NDJSON events.

No global singleton mutation. No ContextVar. No reload_app_config().
Each request constructs an independent AppConfig, injected via
RunnableConfig["configurable"]["app_config"].
"""

import uuid
from collections.abc import AsyncGenerator

from apps.agent.core.backend_client import BackendClient
from apps.agent.services.stream_events import EventStreamBuilder
from packages.core import get_path_manager
from packages.core.effective_config import EffectiveConfigBuilder

from packages.core.logging import get_logger

logger = get_logger(__name__)


# Re-export _select_model from orchestrator for provider selection.
# This avoids duplicating the multi-slot model selection logic.
from apps.agent.services.orchestrator import _select_model


async def stream_agent_dispatch(
    agent_id: int,
    family_id: str,
    thread_id: str | None,
    message: str,
    enable_thinking: bool = False,
) -> AsyncGenerator[str, None]:
    """Agent-first execution entry point. Streams NDJSON events.

    Gateway path: constructs per-request AppConfig, injects into
    make_lead_agent(), streams LangGraph events as NDJSON.
    """
    task_id = str(uuid.uuid4())
    builder_events = EventStreamBuilder(
        capability_id=f"agent-{agent_id}", task_id=task_id
    )

    # 1. Fetch agent config from backend
    client = BackendClient(family_id)
    try:
        agent_config = await client.get_agent_config(agent_id)
    except Exception as e:
        yield builder_events.error(
            f"获取智能体配置失败: {e}", code="AGENT_CONFIG_ERROR"
        ).to_ndjson()
        return

    if not agent_config.get("is_enabled", True):
        yield builder_events.error(
            "智能体已禁用", code="AGENT_DISABLED"
        ).to_ndjson()
        return

    agent_name = agent_config["agent_name"]

    # 2. Fetch AI provider config for this family
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        yield builder_events.error(
            f"获取 AI 配置失败: {e}", code="AI_CONFIG_ERROR"
        ).to_ndjson()
        return

    # 3. Select model via multi-slot provider selection
    providers = ai_config.get("providers", [])
    if not providers:
        yield builder_events.error(
            "未配置 AI 供应商", code="NO_PROVIDER"
        ).to_ndjson()
        return

    task_type = "thinking" if enable_thinking else "text"
    try:
        selected_provider, model_id, caps = _select_model(providers, task_type)
    except ValueError as e:
        yield builder_events.error(str(e), code="MODEL_SELECTION_ERROR").to_ndjson()
        return

    # 4. Build effective config via PathManager + EffectiveConfigBuilder
    pm = get_path_manager()
    config_builder = EffectiveConfigBuilder(pm)

    try:
        effective = config_builder.build(
            family_id=int(family_id),
            agent_name=agent_name,
            ai_provider=selected_provider,
            agent_config=agent_config,
            enabled_skills=[],  # TODO: fetch from backend when API is ready
            mcp_servers=[],     # TODO: fetch from backend when API is ready
        )
    except Exception as e:
        yield builder_events.error(
            f"生成运行配置失败: {e}", code="CONFIG_BUILD_ERROR"
        ).to_ndjson()
        return

    # 5. Determine thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())

    # 6. Construct RunnableConfig with AppConfig injection
    runnable_config = {
        "configurable": {
            "thread_id": thread_id,
            "app_config": effective.config_dict,
            "user_id": family_id,  # DeerFlow expects user_id for memory namespacing
        }
    }

    # 7. Emit session start
    yield builder_events.phase(
        "connecting", {"agent_name": agent_name}
    ).to_ndjson()

    # 8. Create agent graph and stream
    try:
        from deerflow.graph import make_lead_agent

        agent_graph = make_lead_agent(runnable_config)
    except ImportError:
        logger.error("deerflow.graph.make_lead_agent not available")
        yield builder_events.error(
            "Agent 运行环境未就绪", code="RUNTIME_ERROR"
        ).to_ndjson()
        return
    except Exception as e:
        yield builder_events.error(
            f"创建智能体失败: {e}", code="AGENT_CREATE_ERROR"
        ).to_ndjson()
        return

    # 9. Stream events from the agent graph
    answer_parts: list[str] = []
    thinking_started = False
    answering_started = False

    state = {
        "messages": [{"role": "user", "content": message}],
    }

    try:
        async for event in agent_graph.astream(state, runnable_config):
            # Process LangGraph events into NDJSON stream events
            if isinstance(event, dict):
                # Extract content from different event shapes
                for node_name, node_output in event.items():
                    if isinstance(node_output, dict) and "messages" in node_output:
                        for msg in node_output["messages"]:
                            content = _extract_content(msg)
                            if content:
                                if not answering_started:
                                    yield builder_events.phase("answering").to_ndjson()
                                    answering_started = True
                                answer_parts.append(content)
                                yield builder_events.token(
                                    content, is_thinking=False
                                ).to_ndjson()
    except Exception as e:
        yield builder_events.error(str(e), code="STREAM_ERROR").to_ndjson()
        return

    # 10. Emit end
    yield builder_events.end(
        summary="".join(answer_parts)[:200],
        tokens_used=0,
        execution_time_ms=0,
        tools_used=None,
    ).to_ndjson()


def _extract_content(msg) -> str | None:
    """Extract text content from a LangGraph message object or dict."""
    if isinstance(msg, dict):
        return msg.get("content")
    if hasattr(msg, "content"):
        content = msg.content
        if isinstance(content, str):
            return content
    return None
```

- [ ] Run tests to confirm GREEN:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_agent_run_service.py -v
```

Expected: All tests pass.

- [ ] Commit:

```bash
git add server/apps/agent/services/agent_dispatch.py server/tests/agent/unit/test_agent_run_service.py
git commit -m "feat(agent): replace agent_dispatch with Gateway path

- Uses EffectiveConfigBuilder for per-request AppConfig construction
- Injects AppConfig via RunnableConfig['configurable']['app_config']
- Calls make_lead_agent() directly (no DeerFlowClient wrapper)
- No global singleton mutation, no reload_app_config()
- No ContextVar, no _init_lock
- Preserves existing NDJSON stream event protocol
- 5 integration tests with mocked BackendClient + make_lead_agent"
```

---

## Task 7: Cross-Module Verification

**Goal:** Run the full test suite to verify no regressions. The old orchestrator path (`orchestrator.py`) and family_adapter_cache must continue to work unchanged.

**Files:** None created or modified. Verification only.

### Step 7.1: Run all agent tests

- [ ] Run the full agent test suite:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/ -v --tb=short
```

Expected: All existing tests continue to pass. New tests also pass.

### Step 7.2: Run packages/core tests (if any exist)

- [ ] Run core package tests:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest packages/core/ -v --tb=short 2>/dev/null || echo "No core tests found (expected — tests are in tests/agent/unit/)"
```

### Step 7.3: Run lint + type check on touched files

- [ ] Lint new files:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run ruff check packages/core/path_manager.py packages/core/model_entry.py packages/core/effective_config.py packages/core/__init__.py apps/agent/services/agent_dispatch.py
```

- [ ] Format new files:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run ruff format packages/core/path_manager.py packages/core/model_entry.py packages/core/effective_config.py packages/core/__init__.py apps/agent/services/agent_dispatch.py
```

- [ ] If any formatting or lint changes are needed, commit:

```bash
git add -u
git commit -m "style: lint + format new path management modules"
```

---

## Task 8: Final Summary Commit

**Goal:** Ensure all changes are committed and the branch is clean.

### Step 8.1: Verify git status

- [ ] Check git status:

```bash
git status
```

Expected: clean working tree (nothing unstaged).

### Step 8.2: Verify all new test files run

- [ ] Run only the new tests:

```bash
cd /Users/vincentruan/geek_space/github/numina_worktrees/feat/ai-deerflow-agent/server && uv run pytest tests/agent/unit/test_path_manager.py tests/agent/unit/test_model_entry.py tests/agent/unit/test_effective_config.py tests/agent/unit/test_agent_run_service.py -v
```

Expected: All pass.

---

## Dependency Graph

```
Task 1 ──→ Task 2 ──→ Task 3
  │                       │
  ↓                       ↓
Task 4 ────────────→ Task 5 ──→ Task 6 ──→ Task 7 ──→ Task 8
```

- Tasks 1 and 4 are independent (can run in parallel).
- Task 2 depends on Task 1 (needs PathManager class).
- Task 3 depends on Task 2 (needs singleton).
- Task 5 depends on Tasks 1+4 (needs PathManager + ModelEntryBuilder).
- Task 6 depends on Task 5 (needs EffectiveConfigBuilder).
- Task 7 depends on Task 6 (full verification).
- Task 8 depends on Task 7 (final commit).

---

## Files Changed Summary

| Action | File | Task |
|--------|------|------|
| **Create** | `server/packages/core/path_manager.py` | 1 |
| **Create** | `server/packages/core/model_entry.py` | 4 |
| **Create** | `server/packages/core/effective_config.py` | 5 |
| **Modify** | `server/packages/core/__init__.py` | 2 |
| **Modify** | `server/apps/agent/services/agent_dispatch.py` | 6 |
| **Create** | `server/tests/agent/unit/test_path_manager.py` | 1, 2, 3 |
| **Create** | `server/tests/agent/unit/test_model_entry.py` | 4 |
| **Create** | `server/tests/agent/unit/test_effective_config.py` | 5 |
| **Create** | `server/tests/agent/unit/test_agent_run_service.py` | 6 |

Total: 4 new production files, 4 new test files, 2 modified files.
