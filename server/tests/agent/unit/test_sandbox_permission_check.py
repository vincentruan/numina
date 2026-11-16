"""Unit tests for operation permission checks.

Tests cover:
- Write to read-only path → blocked with "Write operation not permitted..."
- Write to writable path → allowed
- Read from read-only path → allowed (no permission check applied)
- Multiple read-only prefixes
"""

from pathlib import Path

from apps.agent.services.runtime.sandbox_permission_check import (
    PermissionCheckResult,
    check_write_permission,
)
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


class TestWritePermission:
    """Tests for check_write_permission()."""

    def test_write_to_read_only_path_blocked(self, tmp_path: Path) -> None:
        """Write to a read-only prefix is blocked."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = check_write_permission(config_dir / "settings.json", policy)

        assert result.allowed is False
        assert result.reason == "Write operation not permitted on read-only path"

    def test_write_to_writable_path_allowed(self, tmp_path: Path) -> None:
        """Write outside read-only prefixes is allowed."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = check_write_permission(tmp_path / "report.txt", policy)

        assert result.allowed is True
        assert result.reason == ""

    def test_no_read_only_paths_allows_all_writes(self, tmp_path: Path) -> None:
        """Empty read_only_paths permits any write."""
        policy = SandboxPolicy.default_policy()

        result = check_write_permission(tmp_path / "anything.bin", policy)

        assert result.allowed is True

    def test_multiple_read_only_prefixes(self, tmp_path: Path) -> None:
        """Write under any one read-only prefix is blocked."""
        config_dir = tmp_path / "config"
        secrets_dir = tmp_path / "secrets"
        config_dir.mkdir()
        secrets_dir.mkdir()
        policy = SandboxPolicy(
            read_only_paths=[str(config_dir), str(secrets_dir)]
        )

        assert check_write_permission(config_dir / "a.json", policy).allowed is False
        assert check_write_permission(secrets_dir / "b.json", policy).allowed is False

    def test_prefix_collision_not_matched(self, tmp_path: Path) -> None:
        """A sibling directory sharing a string prefix is not treated as inside."""
        config_dir = tmp_path / "config"
        config_like = tmp_path / "config-backup"
        config_dir.mkdir()
        config_like.mkdir()
        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = check_write_permission(config_like / "file.json", policy)

        assert result.allowed is True


class TestReturnShape:
    """Tests for the returned result object."""

    def test_returns_permission_check_result(self, tmp_path: Path) -> None:
        """Returns a PermissionCheckResult."""
        policy = SandboxPolicy.default_policy()

        result = check_write_permission(tmp_path / "f.txt", policy)

        assert isinstance(result, PermissionCheckResult)
