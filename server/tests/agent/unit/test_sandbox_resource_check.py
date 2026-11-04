"""Unit tests for resource limit checks.

Tests cover:
- File size exceeding max_file_size_bytes → blocked with descriptive reason
- File size within limits → allowed
- nil/empty content → allowed (no size to check)
- Cumulative quota exceeded → blocked
- Cumulative quota within limits → allowed
- Empty sandbox root → zero usage, check passes
"""

from pathlib import Path

import pytest

from apps.agent.services.runtime.sandbox_policy import SandboxPolicy
from apps.agent.services.runtime.sandbox_resource_check import (
    ResourceCheckResult,
    check_cumulative_quota,
    check_file_size,
)


class TestFileSizeCheck:
    """Tests for check_file_size()."""

    def test_content_exceeding_limit_blocked(self) -> None:
        """File size over the limit is blocked with a descriptive reason."""
        policy = SandboxPolicy(max_file_size_bytes=50 * 1024)
        content = "x" * (60 * 1024)  # 60KB

        result = check_file_size(content, policy)

        assert result.allowed is False
        assert "exceeds policy limit" in result.reason
        assert "60KB" in result.reason
        assert "50KB" in result.reason

    def test_content_within_limit_allowed(self) -> None:
        """Content under the limit is allowed."""
        policy = SandboxPolicy(max_file_size_bytes=50 * 1024)
        content = "x" * 1024  # 1KB

        result = check_file_size(content, policy)

        assert result.allowed is True
        assert result.reason == ""

    def test_content_at_exact_limit_allowed(self) -> None:
        """Content exactly at the limit is allowed (limit is inclusive)."""
        policy = SandboxPolicy(max_file_size_bytes=1024)

        result = check_file_size("x" * 1024, policy)

        assert result.allowed is True

    def test_none_content_allowed(self) -> None:
        """None content (read/str_replace) skips the size check."""
        policy = SandboxPolicy(max_file_size_bytes=1024)

        result = check_file_size(None, policy)

        assert result.allowed is True

    def test_bytes_content_measured_by_bytes(self) -> None:
        """Bytes content is measured by length directly."""
        policy = SandboxPolicy(max_file_size_bytes=1024)

        result = check_file_size(b"x" * 2048, policy)

        assert result.allowed is False

    def test_multibyte_str_measured_as_utf8(self) -> None:
        """Multi-byte characters count by their UTF-8 byte length, not char count."""
        policy = SandboxPolicy(max_file_size_bytes=1024)
        # 400 CJK chars = 1200 UTF-8 bytes, though only 400 characters
        content = "中" * 400

        result = check_file_size(content, policy)

        assert result.allowed is False


class TestCumulativeQuota:
    """Tests for check_cumulative_quota()."""

    def test_quota_exceeded_blocked(self, tmp_path: Path) -> None:
        """Cumulative usage over the quota is blocked."""
        (tmp_path / "big.bin").write_bytes(b"x" * 2048)
        policy = SandboxPolicy(max_total_quota_bytes=1024)

        result = check_cumulative_quota(tmp_path, policy)

        assert result.allowed is False
        assert "Disk quota exceeded" in result.reason

    def test_quota_within_limit_allowed(self, tmp_path: Path) -> None:
        """Cumulative usage under the quota is allowed."""
        (tmp_path / "small.bin").write_bytes(b"x" * 512)
        policy = SandboxPolicy(max_total_quota_bytes=1024)

        result = check_cumulative_quota(tmp_path, policy)

        assert result.allowed is True
        assert result.reason == ""

    def test_empty_sandbox_root_passes(self, tmp_path: Path) -> None:
        """Empty sandbox root has zero usage and passes."""
        policy = SandboxPolicy(max_total_quota_bytes=1024)

        result = check_cumulative_quota(tmp_path, policy)

        assert result.allowed is True

    def test_missing_sandbox_root_passes(self, tmp_path: Path) -> None:
        """A nonexistent sandbox root measures zero usage and passes."""
        missing = tmp_path / "does-not-exist"
        policy = SandboxPolicy(max_total_quota_bytes=1024)

        result = check_cumulative_quota(missing, policy)

        assert result.allowed is True

    def test_nested_directories_counted(self, tmp_path: Path) -> None:
        """Usage in nested subdirectories is included in the total."""
        nested = tmp_path / "a" / "b" / "c"
        nested.mkdir(parents=True)
        (nested / "deep.bin").write_bytes(b"x" * 2048)
        policy = SandboxPolicy(max_total_quota_bytes=1024)

        result = check_cumulative_quota(tmp_path, policy)

        assert result.allowed is False

    def test_directories_not_counted_as_files(self, tmp_path: Path) -> None:
        """Directory entries contribute no size of their own."""
        (tmp_path / "empty-dir").mkdir()
        policy = SandboxPolicy(max_total_quota_bytes=1)

        result = check_cumulative_quota(tmp_path, policy)

        assert result.allowed is True


class TestReturnShape:
    """Tests for the returned result object."""

    def test_returns_resource_check_result(self, tmp_path: Path) -> None:
        """Both checks return ResourceCheckResult."""
        policy = SandboxPolicy.default_policy()

        assert isinstance(check_file_size("x", policy), ResourceCheckResult)
        assert isinstance(check_cumulative_quota(tmp_path, policy), ResourceCheckResult)


class TestMeasureUsagePartialFailure:
    """_measure_usage tolerates but logs partial filesystem failures."""

    def test_nonexistent_root_returns_zero(self, tmp_path: Path) -> None:
        from apps.agent.services.runtime.sandbox_resource_check import _measure_usage

        assert _measure_usage(tmp_path / "nonexistent") == 0

    def test_empty_root_returns_zero(self, tmp_path: Path) -> None:
        from apps.agent.services.runtime.sandbox_resource_check import _measure_usage

        root = tmp_path / "empty_sandbox"
        root.mkdir()
        assert _measure_usage(root) == 0

    def test_counts_files_under_root(self, tmp_path: Path) -> None:
        from apps.agent.services.runtime.sandbox_resource_check import _measure_usage

        root = tmp_path / "sandbox"
        root.mkdir()
        (root / "a.txt").write_bytes(b"hello")
        (root / "b.txt").write_bytes(b"world!!")
        assert _measure_usage(root) == 5 + 7

    def test_partial_read_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unreadable files are tolerated but logged at WARNING."""
        import logging
        import os
        from apps.agent.services.runtime.sandbox_resource_check import _measure_usage

        root = tmp_path / "sandbox"
        root.mkdir()
        (root / "readable.txt").write_bytes(b"data")
        (root / "unreadable.txt").write_bytes(b"secret")

        # Make stat() raise OSError for the unreadable file by patching
        # os.stat for that specific path.
        _original_stat = os.stat

        def _patched_stat(path, **kwargs):
            path_str = str(path)
            if "unreadable.txt" in path_str:
                raise OSError(13, "Permission denied", path_str)
            return _original_stat(path, **kwargs)

        monkeypatch.setattr(os, "stat", _patched_stat)

        with caplog.at_level(logging.WARNING, logger="apps.agent.services.runtime.sandbox_resource_check"):
            total = _measure_usage(root)

        # The readable file should be counted; the unreadable is skipped.
        assert total == 4  # len("data")
        assert any("partial read" in rec.message for rec in caplog.records)
