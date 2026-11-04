"""Unit tests for path policy validation.

Tests cover:
- DeerFlow's absolute virtual form (/mnt/user-data/...) and bare relative form
- Path under allowed prefix → allowed
- Path outside allowed prefixes → blocked with "Path outside allowed directories"
- Path under read-only prefix → marked read-only (caller decides)
- Empty allowed_paths → deferred to sandbox-root check
- Path escaping the family tree → blocked
"""

from pathlib import Path

import pytest

from apps.agent.services.runtime.sandbox_path_validator import (
    PathPolicyResult,
    resolve_virtual_path,
    validate_path_against_policy,
)
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


@pytest.fixture
def user_data_root(tmp_path: Path) -> Path:
    """Host user-data root holding the workspace/uploads/outputs mounts."""
    root = tmp_path / "users" / "family-A" / "threads" / "t1" / "user-data"
    (root / "workspace").mkdir(parents=True)
    (root / "uploads").mkdir()
    (root / "outputs").mkdir()
    return root


class TestResolveVirtualPath:
    """Tests for translating tool paths into the host tree."""

    def test_absolute_virtual_workspace_path(self, user_data_root: Path) -> None:
        """/mnt/user-data/workspace/x maps under the user-data root."""
        result = resolve_virtual_path(
            "/mnt/user-data/workspace/report.txt", user_data_root
        )
        assert result == user_data_root / "workspace" / "report.txt"

    def test_absolute_virtual_uploads_path(self, user_data_root: Path) -> None:
        """/mnt/user-data/uploads/x maps under the user-data root."""
        result = resolve_virtual_path("/mnt/user-data/uploads/in.pdf", user_data_root)
        assert result == user_data_root / "uploads" / "in.pdf"

    def test_bare_virtual_root(self, user_data_root: Path) -> None:
        """/mnt/user-data alone maps to the root itself."""
        assert resolve_virtual_path("/mnt/user-data", user_data_root) == user_data_root

    def test_relative_form_accepted(self, user_data_root: Path) -> None:
        """Bare relative form is joined onto the root."""
        result = resolve_virtual_path("workspace/report.txt", user_data_root)
        assert result == user_data_root / "workspace" / "report.txt"

    def test_absolute_host_path_rejected(self, user_data_root: Path) -> None:
        """An absolute host path is refused, not silently re-rooted."""
        with pytest.raises(ValueError, match="Absolute path outside"):
            resolve_virtual_path("/etc/passwd", user_data_root)


class TestAllowedPaths:
    """Tests for allowed_paths prefix checking."""

    def test_path_under_allowed_prefix(self, user_data_root: Path) -> None:
        """Path under an allowed prefix is allowed."""
        workspace = user_data_root / "workspace"
        policy = SandboxPolicy(allowed_paths=[str(workspace)])

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/report.txt", user_data_root, policy
        )

        assert result.allowed is True
        assert result.reason == ""
        assert result.resolved_path == (workspace / "report.txt").resolve()

    def test_path_outside_allowed_prefixes(self, user_data_root: Path) -> None:
        """Path outside all allowed prefixes is blocked."""
        public_dir = user_data_root / "workspace" / "public"
        public_dir.mkdir()
        policy = SandboxPolicy(allowed_paths=[str(public_dir)])

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/report.txt", user_data_root, policy
        )

        assert result.allowed is False
        assert result.reason == "Path outside allowed directories"

    def test_empty_allowed_paths_defers_to_sandbox_root(
        self, user_data_root: Path
    ) -> None:
        """Empty allowed_paths means any path under the root is allowed."""
        policy = SandboxPolicy(allowed_paths=[])

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/any/nested/file.txt", user_data_root, policy
        )

        assert result.allowed is True

    def test_multiple_allowed_prefixes(self, user_data_root: Path) -> None:
        """Path matching any one of several allowed prefixes is allowed."""
        policy = SandboxPolicy(
            allowed_paths=[
                str(user_data_root / "workspace" / "dir-a"),
                str(user_data_root / "workspace" / "dir-b"),
            ]
        )

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/dir-b/file.txt", user_data_root, policy
        )
        assert result.allowed is True


class TestReadOnlyPaths:
    """Tests for read_only_paths marking."""

    def test_path_under_read_only_prefix(self, user_data_root: Path) -> None:
        """Path under read-only prefix is marked read-only but allowed."""
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/config/settings.json", user_data_root, policy
        )

        assert result.allowed is True
        assert result.is_read_only is True

    def test_path_not_under_read_only(self, user_data_root: Path) -> None:
        """Path outside read-only prefix is not marked read-only."""
        config_dir = user_data_root / "workspace" / "config"
        config_dir.mkdir()
        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/report.txt", user_data_root, policy
        )

        assert result.allowed is True
        assert result.is_read_only is False


class TestSandboxRootContainment:
    """Tests for defense-in-depth sandbox root containment."""

    def test_traversal_escape_blocked(self, user_data_root: Path) -> None:
        """Path escaping the root is blocked."""
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "../../etc/passwd", user_data_root, policy
        )

        assert result.allowed is False
        assert "escapes sandbox root" in result.reason

    def test_absolute_escape_blocked(self, user_data_root: Path) -> None:
        """An absolute foreign path is blocked at translation."""
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "/etc/passwd", user_data_root, policy
        )

        assert result.allowed is False

    def test_prefix_collision_not_matched(self, user_data_root: Path) -> None:
        """Sibling directory with a shared prefix is not treated as under it."""
        (user_data_root / "workspace" / "public").mkdir()
        (user_data_root / "workspace" / "public-secret").mkdir()
        policy = SandboxPolicy(
            allowed_paths=[str(user_data_root / "workspace" / "public")]
        )

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/public-secret/leak.txt",
            user_data_root,
            policy,
        )

        assert result.allowed is False
        assert result.reason == "Path outside allowed directories"

    def test_cross_family_path_blocked(self, tmp_path: Path) -> None:
        """A sibling family's tree is outside this family's root."""
        own = tmp_path / "users" / "family-A"
        other = tmp_path / "users" / "family-B"
        own.mkdir(parents=True)
        other.mkdir(parents=True)
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(str(other / "private.json"), own, policy)

        assert result.allowed is False


class TestReturnShape:
    """Tests for the returned result object."""

    def test_returns_path_policy_result(self, user_data_root: Path) -> None:
        """Returns a PathPolicyResult with resolved host path."""
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/report.txt", user_data_root, policy
        )

        assert isinstance(result, PathPolicyResult)
        assert result.resolved_path == (
            user_data_root / "workspace" / "report.txt"
        ).resolve()

    def test_reason_empty_when_allowed(self, user_data_root: Path) -> None:
        """Reason is empty on an allowed result."""
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "/mnt/user-data/workspace/file.txt", user_data_root, policy
        )

        assert result.allowed is True
        assert result.reason == ""
