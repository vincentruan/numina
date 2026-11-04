"""SandboxPolicy — per-family resource limits and path-pattern policies.

Defines the ``SandboxPolicy`` Pydantic model that captures resource limits
(max file size, cumulative disk quota) and path-pattern policies
(``allowed_paths``, ``read_only_paths``) for per-family sandbox enforcement.

T18 (software gate) uses this model for pre-execution validation via
``SandboxGate``. T22 (container isolation) reuses the same schema to derive
container resource limits and mount configuration.

Design decisions (see plan KTD1-KTD3):
- ``max_execution_time_seconds`` and ``deny_execute_paths`` are deliberately
  excluded — not enforceable via the current guardrail protocol (no post-hook,
  and ``allow_host_bash: false`` means no tool triggers the execute axis).
- Cumulative quota is computed at check time from the filesystem (KTD3),
  not from in-memory counters — survives restarts, reflects deletions.
- Container-oriented fields (``max_memory_mb``, ``max_cpu_count``) are included
  so the schema drives both T18 software enforcement and T22 container config.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# Default values
_DEFAULT_MAX_FILE_SIZE_BYTES = 50 * 1024  # 50KB (within DeerFlow's 80KB write cap)
_DEFAULT_MAX_TOTAL_QUOTA_BYTES = 1 * 1024 * 1024 * 1024  # 1GB
_DEFAULT_MAX_MEMORY_MB = 512
_DEFAULT_MAX_CPU_COUNT = 1


class SandboxPolicy(BaseModel):
    """Per-family sandbox policy for resource limits and path-pattern enforcement.

    Attributes:
        allowed_paths: Host-absolute path prefixes where operations are permitted.
            Empty list means "family sandbox root" (deferred to sandbox-root check
            at evaluation time). Each entry must be an absolute path.
        read_only_paths: Host-absolute path prefixes where writes are denied.
            Reads are always permitted. Each entry must be an absolute path.
        max_file_size_bytes: Maximum size of a single file write (bytes).
            Must be positive. Default: 50KB (within DeerFlow's 80KB write cap).
        max_total_quota_bytes: Maximum cumulative disk usage for the family
            sandbox root (bytes). Must be positive. Default: 1GB.
        max_memory_mb: Container memory limit (MB). Used by T22 container config.
            Must be positive. Default: 512.
        max_cpu_count: Container CPU count. Used by T22 container config.
            Must be positive. Default: 1.
    """

    model_config = ConfigDict(frozen=True)

    allowed_paths: list[str] = []
    read_only_paths: list[str] = []
    max_file_size_bytes: int = _DEFAULT_MAX_FILE_SIZE_BYTES
    max_total_quota_bytes: int = _DEFAULT_MAX_TOTAL_QUOTA_BYTES
    max_memory_mb: int = _DEFAULT_MAX_MEMORY_MB
    max_cpu_count: int = _DEFAULT_MAX_CPU_COUNT

    @field_validator("allowed_paths", "read_only_paths")
    @classmethod
    def validate_path_prefixes(cls, v: list[str]) -> list[str]:
        """All path prefixes must be absolute."""
        for p in v:
            if not Path(p).is_absolute():
                msg = f"Path prefix must be absolute, got relative path: {p!r}"
                raise ValueError(msg)
        return v

    @field_validator("max_file_size_bytes", "max_total_quota_bytes")
    @classmethod
    def validate_positive_size(cls, v: int, info: Any) -> int:
        """Size limits must be positive."""
        if v <= 0:
            msg = f"{info.field_name} must be positive, got {v}"
            raise ValueError(msg)
        return v

    @field_validator("max_memory_mb", "max_cpu_count")
    @classmethod
    def validate_positive_resource(cls, v: int, info: Any) -> int:
        """Resource limits must be positive."""
        if v <= 0:
            msg = f"{info.field_name} must be positive, got {v}"
            raise ValueError(msg)
        return v

    @classmethod
    def default_policy(cls) -> SandboxPolicy:
        """Return a SandboxPolicy with sensible defaults.

        Default values:
        - allowed_paths: [] (empty = family sandbox root)
        - read_only_paths: [] (no read-only restrictions)
        - max_file_size_bytes: 50KB
        - max_total_quota_bytes: 1GB
        - max_memory_mb: 512
        - max_cpu_count: 1
        """
        return cls()

    @classmethod
    def from_config(cls, config: dict[str, Any] | None) -> SandboxPolicy:
        """Deserialize from a YAML-safe config dict.

        Args:
            config: Dict with policy fields. ``None`` or empty dict returns
                the default policy.

        Returns:
            A validated ``SandboxPolicy`` instance.

        Raises:
            pydantic.ValidationError: If config contains invalid values.
        """
        if not config:
            return cls.default_policy()
        return cls.model_validate(config)

    def to_container_config(self) -> dict[str, Any]:
        """Return a dict suitable for T22 AioSandboxProvider overlay.

        Translates policy fields into container resource limit keys that
        ``LocalContainerBackend._start_container`` reads from environment
        variables (``DEER_FLOW_SANDBOX_MEMORY``, ``DEER_FLOW_SANDBOX_CPUS``).
        """
        return {
            "memory": f"{self.max_memory_mb}m",
            "cpus": str(self.max_cpu_count),
        }
