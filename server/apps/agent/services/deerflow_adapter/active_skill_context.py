"""Active-skill ContextVar for runtime tool filtering.

Numina's worker pre-selects a single skill per chat run (``chat`` or
``chat-search`` in ``worker.py``) and dispatches it. DeerFlow's native
``SkillToolPolicyMiddleware`` only filters tools when a skill is slash-activated
or loaded into ``skill_context`` via ``read_file`` — neither happens in Numina's
no-slash flow, so the middleware stays passive (allow-all).

This module bridges that gap: the worker sets the active skill name here before
dispatch, and ``sync_tool_patch._patched_get_available_tools`` reads it to call
``filter_tools_by_skill_allowed_tools`` with that single skill, restricting the
LLM's tool set to the skill's declared ``allowed-tools`` plus framework builtins.

The ContextVar propagates into the DeerFlow sync tool thread via the upstream
``make_sync_tool_wrapper`` (which captures ``contextvars.copy_context()`` at
call time as of harness 2.1.0), so the active skill set in the worker's
thread is visible inside ``get_available_tools``.
"""

from __future__ import annotations

import contextvars

# The skill name selected for this run (e.g. "chat", "chat-search"). None means
# "no active skill" — tool filtering is skipped (legacy allow-all behavior),
# e.g. for trigger-based feature dispatch which loads tools via enable_tools.
_active_skill_name: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "numina_active_skill_name", default=None
)


def set_active_skill(name: str | None) -> contextvars.Token[str | None]:
    """Set the active skill name for the current context. Returns a reset token."""
    return _active_skill_name.set(name)


def reset_active_skill(token: contextvars.Token[str | None]) -> None:
    """Reset the active skill name to its prior value using the token from set."""
    _active_skill_name.reset(token)


def get_active_skill() -> str | None:
    """Return the active skill name for the current context, or None."""
    return _active_skill_name.get()
