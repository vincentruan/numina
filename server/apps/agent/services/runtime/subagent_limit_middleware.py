"""SubagentLimitMiddleware — per-family subagent concurrency limiter.

Prevents runaway subagent task spawning by checking the active task count
against a configured maximum before each subagent spawn.  Reads from
``FamilySubagentRegistry`` so no duplicate bookkeeping is needed.

Activation: config-driven via ``subagent_limit.enabled: true`` in the
per-family DeerFlow temp config (injected by ``family_adapter_cache``).

Thread safety: delegates to ``FamilySubagentRegistry`` which uses its own
lock for all reads.
"""

from __future__ import annotations

from dataclasses import dataclass

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


class SubagentLimitMiddleware:
    """Per-family subagent concurrency limiter.

    Queries ``FamilySubagentRegistry.count_active_for_family(family_id)`` before
    each spawn and denies the request when the active count meets or exceeds
    ``max_concurrent``.

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
        self._max_concurrent = max_concurrent
        self._family_id = family_id
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
            logger.warning(
                "[subagent_limit] no family_id available — denying spawn"
            )
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

    # -- Properties ----------------------------------------------------------

    @property
    def max_concurrent(self) -> int:
        """Return the configured maximum concurrent tasks."""
        return self._max_concurrent

    @property
    def family_id(self) -> str | None:
        """Return the init-time family_id (may be None)."""
        return self._family_id
