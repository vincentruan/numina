"""Resource limit checks for per-family sandbox enforcement.

Validates file writes against a ``SandboxPolicy``'s resource limits:
- File size check: extracted from ``tool_input["content"]`` length
- Cumulative disk quota check: computed at check time by walking the family
  sandbox root (not from in-memory counters)

The quota walk is deliberately uncached. Caching widens the check-to-write gap
under concurrency; the walk is best-effort and permits bounded overshoot of up
to one ``max_file_size_bytes`` per concurrent request. Hard enforcement comes
from OS-level container quotas in the container tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apps.agent.services.runtime.sandbox_policy import SandboxPolicy
from packages.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ResourceCheckResult:
    """Result of a resource limit check.

    Attributes:
        allowed: Whether the operation is within limits.
        reason: Human-readable reason when ``allowed`` is False.
    """

    allowed: bool
    reason: str = ""


def check_file_size(
    content: str | bytes | None,
    policy: SandboxPolicy,
) -> ResourceCheckResult:
    """Check content size against ``policy.max_file_size_bytes``.

    Args:
        content: The content being written (str or bytes). ``None``/empty
            means no content to check (e.g. ``read_file`` or ``str_replace``).
        policy: The family's SandboxPolicy.

    Returns:
        ResourceCheckResult with allowed/reason.
    """
    if content is None:
        return ResourceCheckResult(allowed=True)

    size = len(content.encode("utf-8")) if isinstance(content, str) else len(content)

    if size > policy.max_file_size_bytes:
        return ResourceCheckResult(
            allowed=False,
            reason=(
                f"File size {_human_size(size)} exceeds policy limit "
                f"{_human_size(policy.max_file_size_bytes)}"
            ),
        )

    return ResourceCheckResult(allowed=True)


def check_cumulative_quota(
    sandbox_root: Path,
    policy: SandboxPolicy,
) -> ResourceCheckResult:
    """Check cumulative disk usage of the family sandbox root against the quota.

    Walks ``sandbox_root`` recursively and sums file sizes. Missing or
    unreadable directories are treated as zero usage for that subtree —
    a partially readable sandbox must not block every write.

    Args:
        sandbox_root: Host-absolute sandbox root for the family/thread.
        policy: The family's SandboxPolicy.

    Returns:
        ResourceCheckResult with allowed/reason.
    """
    usage = _measure_usage(sandbox_root)

    if usage > policy.max_total_quota_bytes:
        return ResourceCheckResult(
            allowed=False,
            reason=(
                f"Disk quota exceeded: {_human_size(usage)} used, "
                f"limit {_human_size(policy.max_total_quota_bytes)}"
            ),
        )

    return ResourceCheckResult(allowed=True)


def _measure_usage(root: Path) -> int:
    """Sum file sizes under ``root``; tolerate missing/unreadable entries.

    Unreadable entries are logged at WARNING so operators can detect partial
    filesystem failures that might hide real quota usage.
    """
    if not root.exists():
        return 0

    total = 0
    try:
        for entry in root.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError as e:
                logger.warning(
                    "[sandbox_quota] partial read: could not stat %s: %s",
                    entry,
                    e,
                )
                continue
    except OSError as e:
        logger.warning(
            "[sandbox_quota] partial read: rglob failed under %s: %s",
            root,
            e,
        )
        return total
    return total


def _human_size(size: int) -> str:
    """Format a byte count for error messages."""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)}B"
            return f"{value:.0f}{unit}"
        value /= 1024
    return f"{value:.0f}GB"
