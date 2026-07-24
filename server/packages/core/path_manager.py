"""统一文件路径管理。"""
from __future__ import annotations

import os
import re
from pathlib import Path

from packages.core.logging import get_logger

logger = get_logger(__name__)

_SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
_SLUG_MAX_LEN = 128
_UUID_PATTERN = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$")

# DeerFlow virtual sandbox output prefix (used in artifact paths)
DEERFLOW_SANDBOX_OUTPUT_PREFIX = "/mnt/user-data/outputs/"
# DeerFlow virtual sandbox skills prefix (read-only builtin skills)
DEERFLOW_SANDBOX_SKILLS_PREFIX = "/mnt/skills/"


class PathSecurityError(Exception):
    """路径安全违规。"""


class PathManager:
    def __init__(self, data_root: str | Path | None = None):
        raw = data_root or os.environ.get("DATA_ROOT", "~/.numina/data")
        self._data_root = Path(raw).expanduser().resolve()
        self._ensure_base_dirs()

    def _ensure_base_dirs(self) -> None:
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

    # Validation
    def _validate_slug(self, value: str, field_name: str) -> str:
        if not value or len(value) > _SLUG_MAX_LEN or not _SLUG_PATTERN.match(value):
            raise PathSecurityError(f"无效的 {field_name}: {value!r}")
        return value

    def _validate_thread_id(self, value: str) -> str:
        if not value or not _UUID_PATTERN.match(value):
            raise PathSecurityError(f"无效的 thread_id: {value!r}")
        return value

    def _validate_request_id(self, value: str) -> str:
        if not value or not _UUID_PATTERN.match(value):
            raise PathSecurityError(f"无效的 request_id: {value!r}")
        return value

    def _validate_numeric_id(self, value: int, field_name: str) -> str:
        str_val = str(value)
        if not str_val.isdigit():
            raise PathSecurityError(f"无效的 {field_name}: {value!r}")
        return str_val

    # Security assertions
    def assert_under_root(self, path: Path) -> Path:
        resolved = path.resolve()
        if not resolved.is_relative_to(self._data_root):
            raise PathSecurityError(f"路径越界: {path}")
        return resolved

    def assert_tenant_access(self, path: Path, family_id: int) -> Path:
        resolved = self.assert_under_root(path)
        tenant_root = self.tenant_root(family_id).resolve()
        if not resolved.is_relative_to(tenant_root):
            raise PathSecurityError(f"租户越界: {path}")
        return resolved

    # Root directories
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

    # Builtin resources (read-only)
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

    # Tenant directories
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

    def tenant_session_dir(self, family_id: int, agent_name: str, thread_id: str) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        self._validate_slug(agent_name, "agent_name")
        self._validate_thread_id(thread_id)
        return (
            self._data_root / "workspaces" / "tenants" / fid
            / "agents" / agent_name / "sessions" / thread_id
        )

    def tenant_session_events_file(self, family_id: int, agent_name: str, thread_id: str) -> Path:
        return self.tenant_session_dir(family_id, agent_name, thread_id) / "events.jsonl"

    def tenant_session_artifacts_dir(self, family_id: int, agent_name: str, thread_id: str) -> Path:
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

    def tenant_tmp_dir(self, family_id: int, user_id: int, request_id: str) -> Path:
        fid = self._validate_numeric_id(family_id, "family_id")
        uid = self._validate_numeric_id(user_id, "user_id")
        self._validate_request_id(request_id)
        return (
            self._data_root / "workspaces" / "tenants" / fid
            / "tmp" / uid / request_id
        )

    # Report storage (agent-generated markdown reports)
    _REPORT_FILENAME_PATTERN = re.compile(r'^report_[a-zA-Z0-9_-]+\.md$')

    def tenant_report_dir(self, family_id: int) -> Path:
        """Get tenant's report storage directory.

        Creates the directory if it doesn't exist.
        """
        fid = self._validate_numeric_id(family_id, "family_id")
        path = self._data_root / "workspaces" / "tenants" / fid / "reports"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def tenant_report_file(self, family_id: int, filename: str) -> Path:
        """Get full path for a report file with validation.

        Args:
            family_id: Tenant family ID
            filename: Report filename (must match pattern: report_*.md)

        Returns:
            Full validated path under tenant's reports directory

        Raises:
            PathSecurityError: If filename doesn't match expected pattern
        """
        if not self._REPORT_FILENAME_PATTERN.match(filename):
            raise PathSecurityError(
                f"Invalid report filename: {filename!r}. "
                f"Expected pattern: report_[alphanumeric_-].md"
            )
        return self.tenant_report_dir(family_id) / filename

    # ── Per-thread report paths (aligned with sandbox outputs) ──────────

    def thread_report_dir(self, family_id: int, thread_id: str, create: bool = True) -> Path:
        """Get per-thread report storage directory.

        Aligned with NuminaLocalSandboxProvider's outputs mapping:
        ``{DATA_ROOT}/workspaces/{family_id}/sandboxes/{thread_id}/outputs/``

        When thread_id is available, MCP tools write here instead of the
        tenant-level directory, achieving per-thread isolation consistent
        with DeerFlow's sandbox path mappings.

        Args:
            create: If True (default), create the directory. If False, return
                    the path without creating it (for read-only operations).
        """
        fid = self._validate_numeric_id(family_id, "family_id")
        tid = self._validate_thread_id(thread_id)
        path = self._data_root / "workspaces" / fid / "sandboxes" / tid / "outputs"
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def thread_report_file(self, family_id: int, thread_id: str, filename: str, create: bool = True) -> Path:
        """Get full path for a per-thread report file with validation.

        Args:
            create: If True (default), create the parent directory. If False,
                    return the path without creating it (for read-only operations).
        """
        if not self._REPORT_FILENAME_PATTERN.match(filename):
            raise PathSecurityError(
                f"Invalid report filename: {filename!r}. "
                f"Expected pattern: report_[alphanumeric_-].md"
            )
        return self.thread_report_dir(family_id, thread_id, create=create) / filename

    # Runtime effective (generated, deletable)
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
