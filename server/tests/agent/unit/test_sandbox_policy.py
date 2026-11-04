"""Unit tests for SandboxPolicy — per-family resource limits and path-pattern policies.

Tests cover:
- Default policy has expected values (50KB file size, 1GB quota, 512MB memory, 1 CPU)
- from_config() correctly deserializes a config dict with custom values
- Validation rejects relative paths
- Validation rejects non-positive numeric limits
- Default policy values are sensible
- from_config with None or empty dict returns default policy
"""

import pytest
from pydantic import ValidationError

from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


class TestDefaultPolicy:
    """Tests for SandboxPolicy.default_policy()."""

    def test_default_file_size(self) -> None:
        """Default max_file_size_bytes is 50KB."""
        policy = SandboxPolicy.default_policy()
        assert policy.max_file_size_bytes == 50 * 1024

    def test_default_quota(self) -> None:
        """Default max_total_quota_bytes is 1GB."""
        policy = SandboxPolicy.default_policy()
        assert policy.max_total_quota_bytes == 1 * 1024 * 1024 * 1024

    def test_default_memory(self) -> None:
        """Default max_memory_mb is 512."""
        policy = SandboxPolicy.default_policy()
        assert policy.max_memory_mb == 512

    def test_default_cpu(self) -> None:
        """Default max_cpu_count is 1."""
        policy = SandboxPolicy.default_policy()
        assert policy.max_cpu_count == 1

    def test_default_paths_empty(self) -> None:
        """Default allowed_paths and read_only_paths are empty lists."""
        policy = SandboxPolicy.default_policy()
        assert policy.allowed_paths == []
        assert policy.read_only_paths == []


class TestFromConfig:
    """Tests for SandboxPolicy.from_config()."""

    def test_from_config_with_custom_values(self) -> None:
        """from_config correctly deserializes custom values."""
        config = {
            "allowed_paths": ["/data/users/family-A/workspace"],
            "read_only_paths": ["/data/users/family-A/config"],
            "max_file_size_bytes": 100_000,
            "max_total_quota_bytes": 2_000_000_000,
            "max_memory_mb": 1024,
            "max_cpu_count": 2,
        }
        policy = SandboxPolicy.from_config(config)
        assert policy.allowed_paths == ["/data/users/family-A/workspace"]
        assert policy.read_only_paths == ["/data/users/family-A/config"]
        assert policy.max_file_size_bytes == 100_000
        assert policy.max_total_quota_bytes == 2_000_000_000
        assert policy.max_memory_mb == 1024
        assert policy.max_cpu_count == 2

    def test_from_config_none_returns_default(self) -> None:
        """from_config(None) returns the default policy."""
        policy = SandboxPolicy.from_config(None)
        default = SandboxPolicy.default_policy()
        assert policy.max_file_size_bytes == default.max_file_size_bytes
        assert policy.max_total_quota_bytes == default.max_total_quota_bytes
        assert policy.max_memory_mb == default.max_memory_mb
        assert policy.max_cpu_count == default.max_cpu_count

    def test_from_config_empty_dict_returns_default(self) -> None:
        """from_config({}) returns the default policy."""
        policy = SandboxPolicy.from_config({})
        default = SandboxPolicy.default_policy()
        assert policy.max_file_size_bytes == default.max_file_size_bytes

    def test_from_config_partial_dict(self) -> None:
        """from_config with partial dict uses defaults for missing fields."""
        config = {"max_file_size_bytes": 25_000}
        policy = SandboxPolicy.from_config(config)
        assert policy.max_file_size_bytes == 25_000
        # Other fields use defaults
        assert policy.max_total_quota_bytes == 1 * 1024 * 1024 * 1024
        assert policy.max_memory_mb == 512


class TestValidation:
    """Tests for Pydantic validation."""

    def test_rejects_relative_allowed_path(self) -> None:
        """Relative path in allowed_paths raises ValidationError."""
        with pytest.raises(ValidationError, match="absolute"):
            SandboxPolicy(allowed_paths=["relative/path"])

    def test_rejects_relative_read_only_path(self) -> None:
        """Relative path in read_only_paths raises ValidationError."""
        with pytest.raises(ValidationError, match="absolute"):
            SandboxPolicy(read_only_paths=["config/secret"])

    def test_rejects_zero_file_size(self) -> None:
        """Zero max_file_size_bytes raises ValidationError."""
        with pytest.raises(ValidationError, match="positive"):
            SandboxPolicy(max_file_size_bytes=0)

    def test_rejects_negative_quota(self) -> None:
        """Negative max_total_quota_bytes raises ValidationError."""
        with pytest.raises(ValidationError, match="positive"):
            SandboxPolicy(max_total_quota_bytes=-1)

    def test_rejects_zero_memory(self) -> None:
        """Zero max_memory_mb raises ValidationError."""
        with pytest.raises(ValidationError, match="positive"):
            SandboxPolicy(max_memory_mb=0)

    def test_rejects_negative_cpu(self) -> None:
        """Negative max_cpu_count raises ValidationError."""
        with pytest.raises(ValidationError, match="positive"):
            SandboxPolicy(max_cpu_count=-1)

    def test_accepts_absolute_paths(self) -> None:
        """Absolute paths pass validation."""
        policy = SandboxPolicy(
            allowed_paths=["/data/users/family-A/workspace"],
            read_only_paths=["/data/users/family-A/config"],
        )
        assert policy.allowed_paths == ["/data/users/family-A/workspace"]
        assert policy.read_only_paths == ["/data/users/family-A/config"]




class TestFrozenModel:
    """Tests for immutable model behavior."""

    def test_cannot_modify_after_creation(self) -> None:
        """Frozen model raises on attribute assignment."""
        policy = SandboxPolicy.default_policy()
        with pytest.raises(ValidationError):
            policy.max_file_size_bytes = 999  # type: ignore[misc]


class TestForbidExtra:
    """SandboxPolicy rejects unknown keys (extra='forbid')."""

    def test_typo_key_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            SandboxPolicy.from_config({"max_file_size_byte": 1024})

    def test_unknown_dict_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            SandboxPolicy.from_config({"allowed_paths": [], "read_only_prefixes": []})

    def test_valid_config_still_works(self) -> None:
        policy = SandboxPolicy.from_config(
            {"max_file_size_bytes": 2048, "allowed_paths": []}
        )
        assert policy.max_file_size_bytes == 2048
