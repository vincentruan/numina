"""SubagentLimitMiddleware — per-family subagent concurrency limiter.

Prevents runaway subagent task spawning by checking the active task count
against a configured maximum before each subagent spawn.  Reads from
``FamilySubagentRegistry`` so no duplicate bookkeeping is needed.

Activation: config-driven via ``subagent_limit.enabled: true`` in the
per-family DeerFlow temp config (injected by ``family_adapter_cache``).

LangGraph integration: extends ``AgentMiddleware`` and implements
``wrap_tool_call`` to intercept ``task`` tool calls before they execute.
When the per-family concurrency limit is reached, the middleware returns
a denial ``ToolMessage`` instead of delegating to the handler.

Thread safety: delegates to ``FamilySubagentRegistry`` which uses its own
lock for all reads.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class SubagentDecision:
    """Result of a subagent spawn check.

    Attributes:
        allowed: Whether the spawn is permitted.
        reason: Human-readable reason (empty when allowed).
    """

    allowed: bool
    reason: str = ""


def _make_denial_message(request: Any, reason: str) -> Any:
    """Build a ToolMessage denial for a blocked task tool call."""
    from langchain_core.messages import ToolMessage

    return ToolMessage(
        content=f"[SUBAGENT_LIMIT] {reason}",
        tool_call_id=str(request.tool_call.get("id", "")),
        name="task",
        status="error",
    )


def _make_agent_middleware_base() -> type:
    """Lazy-import AgentMiddleware base class.

    Returns a no-op base when langchain is unavailable (keeps unit tests
    that don't exercise wrap_tool_call working without the full dep chain).
    """
    try:
        from langchain.agents.middleware import AgentMiddleware

        return AgentMiddleware
    except ImportError:
        return object


class SubagentLimitMiddleware(_make_agent_middleware_base()):  # type: ignore[misc]
    """Per-family subagent concurrency limiter.

    Queries ``FamilySubagentRegistry.count_active_for_family(family_id)`` before
    each spawn and denies the request when the active count meets or exceeds
    ``max_concurrent``.

    LangGraph AgentMiddleware integration: ``wrap_tool_call`` intercepts
    ``task`` tool calls and returns a denial ``ToolMessage`` when the limit
    is reached.  Non-task tools pass through to the handler unchanged.

    Configuration (injected via ``family_adapter_cache._inject_subagent_limit``):

    .. code-block:: yaml

        subagent_limit:
          enabled: true
          max_concurrent: 3
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        family_id: str | None = None,
    ) -> None:
        """Initialize the middleware.

        Args:
            max_concurrent: Maximum concurrent subagent tasks per family.
            family_id: Family ID scope.  When ``None``, the middleware reads
                the family_id from the sandbox ContextVar at check time.
        """
        # Guard super().__init__() — only valid when real AgentMiddleware base
        base = _make_agent_middleware_base()
        if base is not object:
            super().__init__()
        self._max_concurrent = max_concurrent
        self._family_id = family_id
        self._lock = threading.Lock()
        logger.debug(
            "[subagent_limit] initialized: max_concurrent=%s family_id=%s",
            max_concurrent,
            family_id or "<from-context>",
        )

    def check_subagent_spawn(
        self,
        family_id: str | None = None,
    ) -> SubagentDecision:
        """Check whether a new subagent spawn is permitted.

        Called before each subagent task creation.

        Args:
            family_id: Override family_id (takes precedence over init-time value).

        Returns:
            SubagentDecision with allowed=True/False and reason.
        """
        effective_family = family_id or self._family_id
        if effective_family is None:
            # Deferred import to avoid circular dependency with sandbox_provider
            from apps.agent.services.runtime.sandbox_provider import (
                get_family_sandbox_context,
            )

            effective_family = get_family_sandbox_context()

        if effective_family is None:
            logger.warning("[subagent_limit] no family_id available — denying spawn")
            return SubagentDecision(
                allowed=False,
                reason="No family_id context available",
            )

        try:
            # Deferred import to avoid circular dependency with subagent_registry
            from apps.agent.services.runtime.subagent_registry import (
                FamilySubagentRegistry,
            )

            active_count = FamilySubagentRegistry.count_active_for_family(
                effective_family
            )
        except Exception as e:
            logger.warning(
                "[subagent_limit] registry read failed (fail-closed): family=%s error=%s",
                effective_family,
                e,
            )
            return SubagentDecision(
                allowed=False,
                reason=f"Subagent registry read failed: {e}",
            )

        if active_count >= self._max_concurrent:
            logger.info(
                "[subagent_limit] denied: family=%s active=%d max=%d",
                effective_family,
                active_count,
                self._max_concurrent,
            )
            return SubagentDecision(
                allowed=False,
                reason=(
                    f"Subagent limit reached: {active_count}/{self._max_concurrent} "
                    f"concurrent tasks for family {effective_family}"
                ),
            )

        logger.debug(
            "[subagent_limit] allowed: family=%s active=%d max=%d",
            effective_family,
            active_count,
            self._max_concurrent,
        )
        return SubagentDecision(allowed=True, reason="")

    # -- LangGraph AgentMiddleware integration ---------------------------------

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable,
    ) -> Any:
        """Intercept ``task`` tool calls to enforce per-family subagent limit.

        Non-task tools pass through to the handler unchanged.  When the
        family's active subagent count meets or exceeds ``max_concurrent``,
        returns a denial ``ToolMessage`` instead of delegating.
        """
        tool_name = request.tool_call.get("name", "")
        if tool_name != "task":
            return handler(request)

        decision = self.check_subagent_spawn()
        if not decision.allowed:
            logger.info(
                "[subagent_limit] wrap_tool_call denied: %s",
                decision.reason,
            )
            return _make_denial_message(request, decision.reason)

        return handler(request)

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable,
    ) -> Any:
        """Async variant of :meth:`wrap_tool_call`."""
        tool_name = request.tool_call.get("name", "")
        if tool_name != "task":
            return await handler(request)

        decision = self.check_subagent_spawn()
        if not decision.allowed:
            logger.info(
                "[subagent_limit] awrap_tool_call denied: %s",
                decision.reason,
            )
            return _make_denial_message(request, decision.reason)

        return await handler(request)

    # -- Properties ----------------------------------------------------------

    @property
    def max_concurrent(self) -> int:
        """Return the configured maximum concurrent tasks."""
        return self._max_concurrent

    @property
    def family_id(self) -> str | None:
        """Return the init-time family_id (may be None)."""
        return self._family_id
