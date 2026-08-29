"""Multi-tenant sandbox context for Numina.

Provides ContextVar-based family_id isolation for DeerFlow sandbox operations.
Multi-tenant isolation works by setting DeerFlow's ``_current_user`` via
``set_current_user`` so ``get_effective_user_id()`` returns the family_id —
the parent ``LocalSandboxProvider`` picks this up automatically through its
``_effective_acquire_user_id`` chain (no method overrides needed).

# [Integrated with Numina Multi-Tenant] — family_id as DeerFlow effective user
"""

from __future__ import annotations

import contextvars
import logging
import threading
from types import SimpleNamespace

from deerflow.sandbox.local.local_sandbox_provider import LocalSandboxProvider

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

# Token for resetting the DeerFlow _current_user ContextVar so the family_id
# override does not leak past the run that set it.
_current_user_token: contextvars.ContextVar[object | None] = contextvars.ContextVar(
    "numina_current_user_token", default=None
)

# Caller user_id for MCP SSE auth (mcp_internal.py requires X-Caller-User-Id).
# The worker sets this alongside family_id; the MCP httpx factory patch reads it to
# inject X-Caller-User-Id into the MCP SSE connection headers (the MCP client
# reads from extensions_config file which has no runtime caller user_id).
_caller_user_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "numina_caller_user_id", default=None
)

# Per-run extensions_config.json path for MCP tool loading.
#
# DeerFlow's ``ExtensionsConfig.from_file()`` resolves the MCP server config
# file via the process-global ``DEER_FLOW_EXTENSIONS_CONFIG_PATH`` env var
# (see ``ExtensionsConfig.resolve_config_path``). Setting that env var per run
# is NOT safe under multi-family concurrency: it is a single process-wide slot,
# so two interleaved family runs overwrite each other's value, and a run whose
# MCP tools load late (e.g. during a context switch) reads the OTHER family's
# path — leaking family-A's MCP SSE URL (which embeds family-A's id) into
# family-B's run, 403-ing, and loading zero MCP tools.
#
# This ContextVar replaces the env var. The adapter sets it per run (alongside
# family_id), and the patched ``resolve_config_path`` reads it and passes it
# explicitly to ``ExtensionsConfig.from_file(config_path=...)``, which bypasses
# lookup entirely (resolve_config_path priority 1 = explicit param). ContextVars
# are coroutine-scoped and propagated into the deerflow executor thread + the
# sync tool-executor pool (via _run_in_executor_with_context + the
# make_sync_tool_wrapper contextvar patch), so each run sees its own path with
# no cross-family leakage.
_extensions_config_path_context: contextvars.ContextVar[str | None] = (
    contextvars.ContextVar("numina_extensions_config_path", default=None)
)


def set_family_sandbox_context(
    family_id: str, caller_user_id: str | None = None
) -> None:
    """Set the current family_id for sandbox path resolution + DeerFlow user.

    Must be called before ``acquire(thread_id)`` in the same coroutine.

    This sets BOTH:
    - Numina's ``sandbox_family_id`` ContextVar (read by other modules like
      ``run_context`` and ``sync_tool_patch`` for tenant-scoped operations).
    - DeerFlow's ``_current_user`` ContextVar (via ``set_current_user``) so
      ``get_effective_user_id()`` returns ``family_id`` everywhere — this is
      the unified-tenant-isolation contract: ``thread_data_middleware`` (which
      view_image / path resolution use), ``write_file`` reverse-resolve, and
      ``LocalSandboxProvider.acquire`` all read the same effective user and
      resolve paths to the same DeerFlow layout
      ``{DEER_FLOW_HOME}/users/{family_id}/threads/{thread_id}/user-data/...``.
      Without setting ``_current_user``, those DeerFlow paths would resolve
      with ``user_id="default"`` and land in a shared ``users/default/`` tree,
      breaking family isolation and mismatching the sandbox path mappings.
    """
    _family_id_context.set(family_id)
    _caller_user_id_context.set(caller_user_id)
    try:
        from deerflow.runtime.user_context import set_current_user

        token = set_current_user(SimpleNamespace(id=family_id))
        _current_user_token.set(token)
    except Exception:
        logger.debug(
            "[sandbox] set_current_user failed (deerflow user_context unavailable)",
            exc_info=True,
        )


def get_caller_user_id_context() -> str | None:
    """Return the current coroutine's caller user_id (for MCP SSE auth), or None."""
    return _caller_user_id_context.get()


def set_extensions_config_path(path: str | None) -> None:
    """Set the per-run extensions_config.json path (MCP server config source).

    Replaces the process-global ``DEER_FLOW_EXTENSIONS_CONFIG_PATH`` env var.
    See ``_extensions_config_path_context`` for the multi-family leak rationale.
    """
    _extensions_config_path_context.set(path)


def get_extensions_config_path() -> str | None:
    """Return the current run's extensions_config.json path, or ``None``.

    ``None`` means "no per-run override" — ``ExtensionsConfig.from_file(None)``
    then falls back to DeerFlow's default resolution (env var / project search),
    which is correct for global-config-mode runs that have no family config.
    """
    return _extensions_config_path_context.get()


def reset_family_sandbox_context() -> None:
    """Reset the family_id context + DeerFlow user token (mirrors set order).

    Called at run end to prevent the family_id / DeerFlow user from leaking
    into a subsequent run in the same coroutine (e.g. a reused worker task).
    """
    _family_id_context.set(None)
    _caller_user_id_context.set(None)
    _extensions_config_path_context.set(None)
    token = _current_user_token.get()
    if token is not None:
        try:
            from deerflow.runtime.user_context import reset_current_user

            reset_current_user(token)  # type: ignore[arg-type]
        except Exception:
            logger.debug("[sandbox] reset_current_user failed", exc_info=True)
        _current_user_token.set(None)


def get_family_sandbox_context() -> str | None:
    """Return the current coroutine's family_id, or ``None`` if not set."""
    return _family_id_context.get()


def assert_mcp_context_complete(stage: str) -> None:
    """Fail-fast if critical tenant ContextVars are unset.

    Thin wrapper around :func:`run_context.assert_run_context_complete`.
    Kept for backward compatibility — callers that imported from this
    module continue to work.
    """
    from apps.agent.services.runtime.run_context import assert_run_context_complete

    assert_run_context_complete(stage)


# ---------------------------------------------------------------------------
# NuminaLocalSandboxProvider
# ---------------------------------------------------------------------------


class NuminaLocalSandboxProvider(LocalSandboxProvider):
    """``LocalSandboxProvider`` subclass used as the DeerFlow sandbox in Numina.

    The class exists so DeerFlow's ``config.yaml`` ``sandbox.use`` entry points
    at a Numina-owned type (integration tests and config generators reference
    ``apps.agent.services.runtime.sandbox_provider:NuminaLocalSandboxProvider``).

    Multi-tenant isolation relies on two mechanisms:

    1. ``set_family_sandbox_context`` sets DeerFlow's ``_current_user`` so
       ``get_effective_user_id()`` returns the family_id — the parent class's
       ``_effective_acquire_user_id`` → ``_build_thread_path_mappings`` →
       ``acquire`` chain picks this up when no explicit ``user_id`` is supplied.

    2. The ``acquire`` override below is the **defense-in-depth** layer. The
       DeerFlow harness calls ``provider.acquire(thread_id,
       user_id=resolve_runtime_user_id(runtime))`` where
       ``resolve_runtime_user_id`` returns ``"default"`` (Numina has no
       DeerFlow server_info / langgraph_auth).  Without this override the
       explicit ``user_id="default"`` would take precedence over the family
       ContextVar, collapsing the cache key to ``("default", thread_id)`` and
       causing cross-tenant path resolution (P2 #13 regression; e2e found
       2026-07-19: view_image "file not found" because a stale cached sandbox
       mapped uploads/ to a different family's path).
    """

    def acquire(
        self, thread_id: str | None = None, *, user_id: str | None = None
    ) -> str:
        family_id = get_family_sandbox_context()
        # Family context is the tenant truth — override any harness-supplied
        # user_id (Numina uses family_id as DeerFlow's effective user). When no
        # family context is set (legacy/script paths), defer to caller/default.
        effective_user_id = family_id if family_id is not None else user_id
        return str(super().acquire(thread_id, user_id=effective_user_id))


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
    return str(get_sandbox_provider().acquire(thread_id))
