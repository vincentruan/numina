"""Path policy validator for per-family sandbox enforcement.

Validates file operation paths against a ``SandboxPolicy``'s path-pattern rules:
- Translate the virtual path (from tool_input) into the family's host sandbox tree
- Check the resolved path against ``allowed_paths`` prefixes
- Mark paths under ``read_only_paths`` prefixes as read-only

This module does NOT prevent path traversal — DeerFlow's upstream
``validate_local_tool_path`` and ``_resolve_path_with_mapping`` handle that.
T18's additive value is per-family policy patterns, not raw traversal prevention.

Virtual path forms accepted (see :func:`resolve_virtual_path`):

* ``/mnt/user-data/workspace/x`` — DeerFlow's canonical absolute virtual form,
  which is what the file tools actually receive.
* ``/mnt/user-data/uploads/x`` / ``/mnt/user-data/outputs/x`` — sibling mounts.
* ``workspace/x`` — bare relative form, also accepted.

Absolute paths outside the virtual prefix and outside the family tree are
rejected rather than silently re-rooted.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deerflow.config.paths import VIRTUAL_PATH_PREFIX

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


def resolve_virtual_path(virtual_path: str, sandbox_root: Path | str) -> Path:
    """Translate a tool's virtual path into a host path under ``sandbox_root``.

    ``sandbox_root`` is the family's host **user-data** root
    (``get_paths().host_sandbox_user_data_dir(thread_id, user_id=family_id)``),
    which holds the ``workspace``, ``uploads``, and ``outputs`` mounts.

    Args:
        virtual_path: Path as supplied by the model, e.g.
            ``/mnt/user-data/workspace/report.txt`` or ``workspace/report.txt``.
        sandbox_root: Host-absolute user-data root for the family/thread.

    Returns:
        The joined host path (not yet resolved/validated).

    Raises:
        ValueError: If the path is absolute but outside the virtual prefix.
    """
    sandbox_root = Path(sandbox_root)
    if virtual_path == VIRTUAL_PATH_PREFIX:
        return sandbox_root

    if virtual_path.startswith(f"{VIRTUAL_PATH_PREFIX}/"):
        return sandbox_root / virtual_path[len(VIRTUAL_PATH_PREFIX) + 1 :]

    if Path(virtual_path).is_absolute():
        # An absolute host-style path is not a path the sandbox tools should
        # ever hand us. Joining it onto the root would discard the root
        # entirely, so refuse instead of silently re-rooting.
        msg = f"Absolute path outside {VIRTUAL_PATH_PREFIX}: {virtual_path!r}"
        raise ValueError(msg)

    return sandbox_root / virtual_path


def validate_path_against_policy(
    virtual_path: str,
    sandbox_root: Path | str,
    policy: SandboxPolicy,
) -> PathPolicyResult:
    """Validate a tool-supplied path against the family's sandbox policy.

    Steps:
    1. Translate ``virtual_path`` into the family's host tree.
    2. Resolve via ``pathlib.Path.resolve()`` to handle symlinks.
    3. Check that the resolved path is still under ``sandbox_root``
       (defense-in-depth with upstream traversal validation).
    4. If ``policy.allowed_paths`` is non-empty, check the resolved path
       starts with at least one allowed prefix.
    5. If the path is under any ``policy.read_only_paths`` prefix, mark read-only.

    Args:
        virtual_path: Path from tool_input.
        sandbox_root: Host-absolute user-data root for the family/thread.
        policy: The family's SandboxPolicy.

    Returns:
        PathPolicyResult with allowed/is_read_only/resolved_path/reason.
    """
    sandbox_root = Path(sandbox_root)

    # 1. Translate to a host path
    try:
        host_target = resolve_virtual_path(virtual_path, sandbox_root)
    except ValueError as e:
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=sandbox_root,
            reason=str(e),
        )

    # 2. Resolve symlinks
    try:
        resolved = host_target.resolve()
        resolved_root = sandbox_root.resolve()
    except (OSError, ValueError):
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=host_target,
            reason=f"Cannot resolve path: {virtual_path!r}",
        )

    # 3. Defense-in-depth: resolved path must still be under the family tree
    if not is_under_prefix(resolved, str(resolved_root)):
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=resolved,
            reason="Path escapes sandbox root directory",
        )

    # 4. Check allowed_paths (if configured)
    if policy.allowed_paths and not any(
        is_under_prefix(resolved, prefix) for prefix in policy.allowed_paths
    ):
        return PathPolicyResult(
            allowed=False,
            is_read_only=False,
            resolved_path=resolved,
            reason="Path outside allowed directories",
        )

    # 5. Check read_only_paths
    is_read_only = any(
        is_under_prefix(resolved, prefix) for prefix in policy.read_only_paths
    )

    return PathPolicyResult(
        allowed=True,
        is_read_only=is_read_only,
        resolved_path=resolved,
    )


def is_under_prefix(path: Path, prefix: str | Path) -> bool:
    """Check if ``path`` is under the given absolute prefix, on segment bounds."""
    try:
        path.relative_to(prefix)
        return True
    except ValueError:
        return False
