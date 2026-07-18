"""Multi-tenant local sandbox provider for Numina.

Extends DeerFlow's ``LocalSandboxProvider`` with family_id-scoped sandbox IDs
and path mappings, ensuring different families get isolated sandbox environments
even when they share the same thread_id.

# [Integrated with Numina Multi-Tenant] — family_id in sandbox ID and paths
"""

from __future__ import annotations

import contextvars
import hashlib
import logging
import threading
from pathlib import Path

from deerflow.sandbox.local.local_sandbox import PathMapping
from deerflow.sandbox.local.local_sandbox_provider import LocalSandboxProvider

from apps.agent.app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Coroutine-safe family_id context
# ---------------------------------------------------------------------------

# Use contextvars.ContextVar instead of threading.local so the value is
# correctly isolated per asyncio coroutine (not just per OS thread).
# Multiple coroutines on the same event loop thread can interleave at
# await points — threading.local would leak the family_id across tenants.
_family_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "sandbox_family_id", default=None
)


def set_family_sandbox_context(family_id: str) -> None:
    """Set the current family_id for sandbox path resolution.

    Must be called before ``acquire(thread_id)`` in the same coroutine.
    """
    _family_id_context.set(family_id)


def get_family_sandbox_context() -> str | None:
    """Return the current coroutine's family_id, or ``None`` if not set."""
    return _family_id_context.get()


# ---------------------------------------------------------------------------
# NuminaLocalSandboxProvider
# ---------------------------------------------------------------------------


class NuminaLocalSandboxProvider(LocalSandboxProvider):
    """``LocalSandboxProvider`` variant with family_id-scoped sandbox IDs and paths.

    Overrides two static methods from the parent class:
    - ``_deterministic_sandbox_id`` — mixes ``family_id`` into the hash so two
      families with the same ``thread_id`` get different sandbox IDs.
    - ``_build_thread_path_mappings`` — resolves directories under
      ``settings.AGENT_DATA_DIR / family_id / sandboxes / thread_id/``.
    """

    # [Integrated with Numina Multi-Tenant]
    # DeerFlow uses: sha256(thread_id)[:8]
    # Numina uses:  sha256(f"family-{family_id}-thread-{thread_id}")[:8]
    @staticmethod
    def _deterministic_sandbox_id(thread_id: str) -> str:
        """Generate a deterministic sandbox ID incorporating family_id.

        This ensures two families with the same thread_id UUID get different
        sandbox IDs and therefore different containers / path scopes.
        """
        family_id = get_family_sandbox_context() or "unknown"
        composite = f"family-{family_id}-thread-{thread_id}"
        return hashlib.sha256(composite.encode()).hexdigest()[:8]

    # [Integrated with Numina Multi-Tenant]
    # DeerFlow uses: get_paths().sandbox_work_dir(thread_id, user_id)
    # Numina uses:  settings.AGENT_DATA_DIR / family_id / sandboxes / thread_id/
    #
    # harness rev >=10890e10: parent ``_build_thread_path_mappings`` gained a
    # keyword-only ``user_id`` param (local_sandbox_provider.py:234), and
    # ``acquire`` passes it (L363). Numina's multi-tenant isolation is by
    # ``family_id`` (ContextVar), NOT by harness ``user_id`` — so we accept
    # ``user_id`` for signature compatibility but ignore it, keeping paths
    # scoped to family_id. NOTE: ``acquire`` (L370) now builds sandbox IDs via
    # ``_sandbox_id_for_thread(thread_id, effective_user_id)`` and bypasses the
    # ``_deterministic_sandbox_id`` override below — family_id no longer enters
    # the sandbox ID, a separate tenant-isolation regression to track.
    @staticmethod
    def _build_thread_path_mappings(
        thread_id: str, *, user_id: str | None = None
    ) -> list[PathMapping]:
        """Build per-thread path mappings scoped to family_id.

        Directories are created lazily under:
        ``{AGENT_DATA_DIR}/{family_id}/sandboxes/{thread_id}/{workspace,uploads,outputs}``

        ``user_id`` is accepted for signature compatibility with the parent
        class (harness rev >=10890e10) but ignored — Numina isolates by
        ``family_id`` via the coroutine-scoped ContextVar, not by user_id.
        """
        family_id = get_family_sandbox_context()
        if not family_id:
            return []

        base = Path(settings.AGENT_DATA_DIR) / family_id / "sandboxes" / thread_id
        workspace = base / "workspace"
        uploads = base / "uploads"
        outputs = base / "outputs"
        workspace.mkdir(parents=True, exist_ok=True)
        uploads.mkdir(parents=True, exist_ok=True)
        outputs.mkdir(parents=True, exist_ok=True)

        return [
            PathMapping(
                container_path="/mnt/user-data",
                local_path=str(base),
                read_only=False,
            ),
            PathMapping(
                container_path="/mnt/user-data/workspace",
                local_path=str(workspace),
                read_only=False,
            ),
            PathMapping(
                container_path="/mnt/user-data/uploads",
                local_path=str(uploads),
                read_only=False,
            ),
            PathMapping(
                container_path="/mnt/user-data/outputs",
                local_path=str(outputs),
                read_only=False,
            ),
        ]


# ---------------------------------------------------------------------------
# Singleton accessor (mirrors DeerFlow's _singleton pattern)
# ---------------------------------------------------------------------------

_numina_sandbox_provider: NuminaLocalSandboxProvider | None = None
_sandbox_lock = threading.Lock()


def get_sandbox_provider() -> NuminaLocalSandboxProvider:
    """Return the singleton ``NuminaLocalSandboxProvider`` instance."""
    global _numina_sandbox_provider
    if _numina_sandbox_provider is None:
        with _sandbox_lock:
            if _numina_sandbox_provider is None:
                _numina_sandbox_provider = NuminaLocalSandboxProvider()
    return _numina_sandbox_provider


def acquire_family_sandbox(family_id: str, thread_id: str) -> str:
    """Acquire a sandbox scoped to ``(family_id, thread_id)``.

    Sets the coroutine-safe family context, acquires from the singleton provider,
    and returns the sandbox ID.
    """
    set_family_sandbox_context(family_id)
    return get_sandbox_provider().acquire(thread_id)
