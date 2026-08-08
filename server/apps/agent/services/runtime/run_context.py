"""Read-only facade over the 5 per-run tenant ContextVars.

Provides a consolidated snapshot of the run context for assertions and
diagnostics.  The 5 ContextVars remain independently set at their current
lifecycle points (async caller vs executor thread); this module only adds
a unified *read* view.

**Why a facade, not full consolidation?**
The 5 ContextVars are set at 2 different lifecycle points with different
reset semantics:

- ``sandbox_family_id``, ``caller_user_id``, ``active_skill_name``,
  ``original_user_content`` — set in the async caller, propagated via
  ``copy_context()`` into the executor thread.
- ``extensions_config_path`` — set in the executor thread (tied to the
  DeerFlow AppConfig push/pop lifecycle inside ``_family_config_context``).

Consolidating into a single frozen dataclass would require coordinating all
set points or using a mutable dataclass (losing atomicity).  The facade
provides the consolidated view for assertions without the coordination cost.

DeerFlow's own architecture has a similar duality: ``_current_user``
(ContextVar) and ``runtime.context`` (dict) coexist as two channels serving
different purposes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RunContext:
    """Read-only snapshot of all per-run tenant ContextVars.

    Constructed via :meth:`from_contextvars` which reads each ContextVar at
    call time — no caching, no staleness.
    """

    family_id: str | None
    caller_user_id: str | None
    extensions_config_path: str | None
    active_skill_name: str | None
    original_user_content: str | None

    @classmethod
    def from_contextvars(cls) -> RunContext:
        """Read all 5 ContextVars and return a frozen snapshot."""
        from apps.agent.services.deerflow_adapter.active_skill_context import (
            get_active_skill,
        )
        from apps.agent.services.deerflow_adapter.original_user_content_context import (
            get_original_user_content,
        )
        from apps.agent.services.runtime.sandbox_provider import (
            get_caller_user_id_context,
            get_extensions_config_path,
            get_family_sandbox_context,
        )

        return cls(
            family_id=get_family_sandbox_context(),
            caller_user_id=get_caller_user_id_context(),
            extensions_config_path=get_extensions_config_path(),
            active_skill_name=get_active_skill(),
            original_user_content=get_original_user_content(),
        )

    @property
    def has_mandatory_context(self) -> bool:
        """Return True if all mandatory ContextVars are set.

        Only ``family_id`` is truly mandatory — the others have legitimate
        None states (``extensions_config_path`` is None in global-config
        mode, ``caller_user_id`` is None for internal dispatch,
        ``active_skill_name`` is None for non-skill dispatch,
        ``original_user_content`` is None for non-chat dispatch).
        """
        return self.family_id is not None


def assert_run_context_complete(stage: str) -> None:
    """Fail-fast if mandatory tenant ContextVars are unset.

    Replaces the older ``assert_mcp_context_complete`` in sandbox_provider.py
    (kept as a thin alias for backward compat).  Uses :class:`RunContext` to
    read all 5 ContextVars in a single snapshot, so the error message can
    report exactly which ones are missing.

    .. warning:: When adding a new ContextVar, it MUST be added to BOTH
       set-points (async caller in ``worker.py`` and executor thread in
       ``sync_tool_patch.py``) and to :class:`RunContext`.  A ContextVar
       that only gets set at one lifecycle point will silently be ``None``
       at the other — repeating the F2 sandbox fail-open bug.

    Raises :class:`RuntimeError` with a diagnostic message — replacing the
    silent "all records empty" / "MCP tools: 0" failure mode.
    """
    ctx = RunContext.from_contextvars()
    if not ctx.has_mandatory_context:
        raise RuntimeError(
            f"MCP context incomplete at {stage}: "
            f"missing sandbox_family_id. "
            f"This indicates a ContextVar propagation failure — "
            f"check set_family_sandbox_context() was called before dispatch."
        )
