"""Path policy validator for per-family sandbox enforcement.

Validates file operation paths against a ``SandboxPolicy``'s path-pattern rules:
- Join the virtual path (from tool_input) onto the family's host sandbox root
- Check the resolved path against ``allowed_paths`` prefixes
- Mark paths under ``read_only_paths`` prefixes as read-only

This module does NOT prevent path traversal — DeerFlow's upstream
``validate_local_tool_path`` and ``_resolve_path_with_mapping`` handle that.
T18's additive value is per-family policy patterns, not raw traversal prevention.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.agent.services.runtime.sandbox_policy import SandboxPolicy


@dataclass
class PathPolicyResult:
    """Result of a path policy check.

    Attributes:
        allowed: Whether the path is permitted for the operation.
        is_read_only: Whether the path falls under a read-only prefix.
        resolved_path: The host-absolute resolved path (after symlink resolution).
        reason: Human-readable reason when ``allowed`` is False.
    """

    allowed: bool
    is_read_only: bool
    resolved_path: Path
    reason: str = ""


def validate_path_against_policy(
    virtual_path: str,
    sandbox_root: Path,
    policy: SandboxPolicy,
) -> PathPolicyResult:
    """Validate a virtual path against the family's sandbox policy.

    The ``virtual_path`` is the raw path from ``tool_input["path"]``
    (e.g. ``"workspace/report.txt"``). The ``sandbox_root`` is the
    already-computed host path from
    ``get_paths().host_sandbox_work_dir(thread_id, user_id=family_id)``.

    Steps:
    1. Join ``virtual_path`` onto ``sandbox_root`` to get the host target path.
    2. Resolve via ``pathlib.Path.resolve()`` to handle symlinks.
    3. Check that resolved path is still relative to ``sandbox_root``
       (defense-in-depth with upstream traversal validation).
    4. If ``policy.allowed_paths`` is non-empty, check the resolved path
       starts with at least one allowed prefix.
    5. If path is under any ``policy.read_only_paths`` prefix, mark as read-only.

    Args:
        virtual_path: Raw path from tool_input (relative to thread workspace).
        sandbox_root: Host-absolute sandbox root for the family/thread.
        policy: The family's SandboxPolicy.

    Returns:
        PathPolicyResult with allowed/is_read_only/resolved_path/reason.
    """
    # 1. Join virtual path onto sandbox root
    host_target = sandbox_root / virtual_path

    # 2. Resolve symlinks
    try:
        resolved = host_target.resolve()
    except (OSError, ValueError):
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=host_target,
            reason=f"Cannot resolve path: {virtual_path!r}",
        )

    # Also resolve the sandbox_root for comparison
    try:
        resolved_root = sandbox_root.resolve()
    except (OSError, ValueError):
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=resolved,
            reason=f"Cannot resolve sandbox root: {sandbox_root!s}",
        )

    # 3. Defense-in-depth: resolved path must still be under sandbox root
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=resolved,
            reason="Path escapes sandbox root directory",
        )

    # 4. Check allowed_paths (if configured)
    if policy.allowed_paths:
        under_allowed = any(
            _is_under_prefix(resolved, prefix) for prefix in policy.allowed_paths
        )
        if not under_allowed:
            return PathPolicyResult(
                allowed=False,
                is_read_only=False,
                resolved_path=resolved,
                reason="Path outside allowed directories",
            )

    # 5. Check read_only_paths
    is_read_only = any(
        _is_under_prefix(resolved, prefix) for prefix in policy.read_only_paths
    )

    return PathPolicyResult(
        allowed=True,
        is_read_only=is_read_only,
        resolved_path=resolved,
    )


def _is_under_prefix(path: Path, prefix: str) -> bool:
    """Check if ``path`` is under the given absolute prefix string."""
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False
