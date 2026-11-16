"""Operation permission checks for per-family sandbox enforcement.

Checks whether a write operation is permitted for a given host path based on
the family's ``SandboxPolicy.read_only_paths``. Read operations are always
permitted — the policy only restricts writes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.agent.services.runtime.sandbox_path_validator import is_under_prefix
from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


@dataclass
class PermissionCheckResult:
    """Result of an operation permission check.

    Attributes:
        allowed: Whether the operation is permitted.
        reason: Human-readable reason when ``allowed`` is False.
    """

    allowed: bool
    reason: str = ""


def check_write_permission(
    host_target_path: Path,
    policy: SandboxPolicy,
) -> PermissionCheckResult:
    """Check whether a write to ``host_target_path`` is permitted.

    A write is denied when the path falls under any ``policy.read_only_paths``
    prefix. Reads are never checked by this function — callers invoke it only
    for write-shaped operations.

    Args:
        host_target_path: Host-absolute path being written.
        policy: The family's SandboxPolicy.

    Returns:
        PermissionCheckResult with allowed/reason.
    """
    for prefix in policy.read_only_paths:
        if is_under_prefix(host_target_path, prefix):
            return PermissionCheckResult(
                allowed=False,
                reason="Write operation not permitted on read-only path",
            )

    return PermissionCheckResult(allowed=True)
