"""Original user content ContextVar for slash-skill activation.

DeerFlow's ``SkillActivationMiddleware`` reads ``ORIGINAL_USER_CONTENT_KEY`` from
the HumanMessage's ``additional_kwargs`` to get the raw user text (before JSON
wrapping). Numina's adapter wraps user text as JSON context, so without this
key, ``parse_slash_skill_reference`` fails on the JSON's leading ``{``.

This module provides a ContextVar that the adapter sets before calling
``DeerFlowClient.stream()``. A patch in ``sync_tool_patch.py`` reads the
ContextVar and merges it into the HumanMessage's ``additional_kwargs`` at
construction time, so DeerFlow's middleware sees the raw user text.

The ContextVar propagates into the DeerFlow executor thread via
``_run_in_executor_with_context`` (which uses ``contextvars.copy_context()``),
so the value set in the adapter's async context is visible inside
``DeerFlowClient.stream()``.
"""

from __future__ import annotations

import contextvars

# The raw user text (before JSON wrapping). Set by the adapter before calling
# stream(); read by the HumanMessage patch in sync_tool_patch.py. None means
# "no original content" — DeerFlow falls back to the message content text.
_original_user_content: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "numina_original_user_content", default=None
)


def set_original_user_content(text: str | None) -> contextvars.Token[str | None]:
    """Set the original user content for the current context. Returns a reset token."""
    return _original_user_content.set(text)


def reset_original_user_content(token: contextvars.Token[str | None]) -> None:
    """Reset the original user content to its prior value using the token from set."""
    _original_user_content.reset(token)


def get_original_user_content() -> str | None:
    """Return the original user content for the current context, or None."""
    return _original_user_content.get()
