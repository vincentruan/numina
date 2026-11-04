"""Unit tests for path policy validation.

Tests cover:
- Path under allowed prefix → allowed
- Path outside allowed prefixes → blocked with "Path outside allowed directories"
- Path under read-only prefix → marked read-only (caller decides)
- Empty allowed_paths → deferred to sandbox-root check
- Path escaping sandbox root → blocked
"""

from pathlib import Path

from apps.agent.services.runtime.sandbox_path_validator import (
    PathPolicyResult,
    validate_path_against_policy,
)
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


class TestAllowedPaths:
    """Tests for allowed_paths prefix checking."""

    def test_path_under_allowed_prefix(self, tmp_path: Path) -> None:
        """Path under an allowed prefix is allowed."""
        workspace = tmp_path / "family-A" / "workspace"
        workspace.mkdir(parents=True)
        policy = SandboxPolicy(allowed_paths=[str(workspace)])

        result = validate_path_against_policy(
            "report.txt", sandbox_root=workspace, policy=policy
        )

        assert result.allowed is True
        assert result.reason == ""
        assert result.resolved_path == workspace / "report.txt"

    def test_path_outside_allowed_prefixes(self, tmp_path: Path) -> None:
        """Path outside all allowed prefixes is blocked."""
        sandbox_root = tmp_path / "family-A" / "workspace"
        sandbox_root.mkdir(parents=True)
        public_dir = sandbox_root / "public"
        public_dir.mkdir()

        policy = SandboxPolicy(allowed_paths=[str(public_dir)])

        # Write to workspace root (not under public/) — blocked
        result = validate_path_against_policy(
            "report.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is False
        assert result.reason == "Path outside allowed directories"

    def test_empty_allowed_paths_defers_to_sandbox_root(self, tmp_path: Path) -> None:
        """Empty allowed_paths means any path under sandbox root is allowed."""
        sandbox_root = tmp_path / "family-A" / "workspace"
        sandbox_root.mkdir(parents=True)
        policy = SandboxPolicy(allowed_paths=[])

        result = validate_path_against_policy(
            "any/nested/file.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is True

    def test_multiple_allowed_prefixes(self, tmp_path: Path) -> None:
        """Path matching any one of several allowed prefixes is allowed."""
        sandbox_root = tmp_path / "workspace"
        sandbox_root.mkdir()
        (sandbox_root / "dir-a").mkdir()
        (sandbox_root / "dir-b").mkdir()

        policy = SandboxPolicy(
            allowed_paths=[
                str(sandbox_root / "dir-a"),
                str(sandbox_root / "dir-b"),
            ]
        )

        result = validate_path_against_policy(
            "dir-b/file.txt", sandbox_root=sandbox_root, policy=policy
        )
        assert result.allowed is True


class TestReadOnlyPaths:
    """Tests for read_only_paths marking."""

    def test_path_under_read_only_prefix(self, tmp_path: Path) -> None:
        """Path under read-only prefix is marked read-only but allowed."""
        sandbox_root = tmp_path / "workspace"
        config_dir = sandbox_root / "config"
        config_dir.mkdir(parents=True)

        policy = SandboxPolicy(read_only_paths=[str(config_dir)])

        result = validate_path_against_policy(
            "config/settings.json", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is True
        assert result.is_read_only is True

    def test_path_not_under_read_only(self, tmp_path: Path) -> None:
        """Path outside read-only prefix is not marked read-only."""
        sandbox_root = tmp_path / "workspace"
        sandbox_root.mkdir()
        (sandbox_root / "config").mkdir()

        policy = SandboxPolicy(read_only_paths=[str(sandbox_root / "config")])

        result = validate_path_against_policy(
            "report.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is True
        assert result.is_read_only is False


class TestSandboxRootContainment:
    """Tests for defense-in-depth sandbox root containment."""

    def test_traversal_escape_blocked(self, tmp_path: Path) -> None:
        """Path escaping the sandbox root is blocked."""
        sandbox_root = tmp_path / "family-A" / "workspace"
        sandbox_root.mkdir(parents=True)
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "../../../etc/passwd", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is False
        assert "escapes sandbox root" in result.reason

    def test_prefix_collision_not_matched(self, tmp_path: Path) -> None:
        """Sibling directory with a shared prefix is not treated as under it."""
        sandbox_root = tmp_path / "workspace"
        sandbox_root.mkdir()
        (sandbox_root / "public").mkdir()
        (sandbox_root / "public-secret").mkdir()

        policy = SandboxPolicy(allowed_paths=[str(sandbox_root / "public")])

        result = validate_path_against_policy(
            "public-secret/leak.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is False
        assert result.reason == "Path outside allowed directories"


class TestReturnShape:
    """Tests for the returned result object."""

    def test_returns_path_policy_result(self, tmp_path: Path) -> None:
        """Returns a PathPolicyResult with resolved host path."""
        sandbox_root = tmp_path / "workspace"
        sandbox_root.mkdir()
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "workspace/report.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert isinstance(result, PathPolicyResult)
        assert result.resolved_path == (sandbox_root / "workspace" / "report.txt").resolve()

    def test_reason_empty_when_allowed(self, tmp_path: Path) -> None:
        """Reason is empty on an allowed result."""
        sandbox_root = tmp_path / "workspace"
        sandbox_root.mkdir()
        policy = SandboxPolicy.default_policy()

        result = validate_path_against_policy(
            "file.txt", sandbox_root=sandbox_root, policy=policy
        )

        assert result.allowed is True
        assert result.reason == ""
