"""NuminaGuardrailProvider — tool execution safety guardrails for DeerFlow.

This provider implements DeerFlow's GuardrailMiddleware provider interface to
enforce per-family tool allow/deny lists. It integrates with Numina's existing
CapabilityPolicy system for family-level access control.

Design:
- Allowlist takes precedence: if allowlist is non-empty, only listed tools execute
- Denylist overrides allowlist: explicitly denied tools never execute
- Fail-closed: on provider errors, tool calls are denied (configurable)
- Per-family configurable via ai_config guardrails section

Relationship to PolicyGuard:
- PolicyGuard: pre-dispatch gate (checks skill/capability access before LLM call)
- NuminaGuardrailProvider: tool execution gate (checks individual tool calls during LLM run)
Both are active simultaneously — PolicyGuard gates dispatch, this provider gates tools.
"""

from dataclasses import dataclass
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class GuardrailDecision:
    """Result of a guardrail check.

    Attributes:
        allowed: Whether the tool call is permitted
        reason: Human-readable reason for the decision (empty if allowed)
    """

    allowed: bool
    reason: str = ""


class NuminaGuardrailProvider:
    """Per-family tool execution guardrail provider.

    Checks tool calls against configured allow/deny lists. Integrates with
    DeerFlow's GuardrailMiddleware which calls ``check_tool_call`` before
    each tool execution.

    Configuration (injected via family_adapter_cache._inject_guardrail):
        guardrails:
            enabled: true
            fail_closed: true  # deny on error
            allowlist:         # empty = all allowed (subject to denylist)
                - get_assets
                - get_liabilities
            denylist:          # explicit denials override allowlist
                - bash
                - execute_code

    Thread safety: This class is stateless after init — safe for concurrent use.
    """

    def __init__(
        self,
        allowlist: list[str] | None = None,
        denylist: list[str] | None = None,
        fail_closed: bool = True,
    ) -> None:
        """Initialize the guardrail provider.

        Args:
            allowlist: Tools explicitly allowed. Empty/None = all allowed (except denylist).
            denylist: Tools explicitly denied. Overrides allowlist.
            fail_closed: If True, deny tool calls on provider errors. If False, allow.

        Raises:
            TypeError: If allowlist or denylist is not a list (when provided).
        """
        # Validate types — a string would be split into characters by set()
        if allowlist is not None and not isinstance(allowlist, list):
            raise TypeError(
                f"allowlist must be a list, got {type(allowlist).__name__}"
            )
        if denylist is not None and not isinstance(denylist, list):
            raise TypeError(
                f"denylist must be a list, got {type(denylist).__name__}"
            )

        self._allowlist = set(allowlist) if allowlist else set()
        self._denylist = set(denylist) if denylist else set()
        self._fail_closed = fail_closed

        logger.debug(
            "[guardrail] initialized: allowlist=%s denylist=%s fail_closed=%s",
            self._allowlist or "<all>",
            self._denylist or "<none>",
            self._fail_closed,
        )

    def check_tool_call(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,  # reserved for arg-level checks
        context: dict[str, Any] | None = None,  # reserved for context-aware checks
    ) -> GuardrailDecision:
        """Check if a tool call is permitted.

        Called by DeerFlow's GuardrailMiddleware before each tool execution.

        Args:
            tool_name: Name of the tool being called
            tool_args: Tool arguments (reserved for future arg-level checks)
            context: Execution context (family_id, thread_id, etc.)

        Returns:
            GuardrailDecision with allowed=True/False and reason
        """
        del tool_args  # unused — reserved for future argument-level checks
        del context  # unused — reserved for future context-aware checks
        try:
            return self._check_internal(tool_name)
        except Exception as e:
            # Fail-closed: deny on error (default)
            # Fail-open: allow on error (explicit opt-in)
            if self._fail_closed:
                logger.warning(
                    "[guardrail] check failed (fail-closed): tool=%s error=%s",
                    tool_name,
                    e,
                )
                return GuardrailDecision(
                    allowed=False,
                    reason=f"Guardrail check failed: {e}",
                )
            else:
                logger.warning(
                    "[guardrail] check failed (fail-open): tool=%s error=%s",
                    tool_name,
                    e,
                )
                return GuardrailDecision(allowed=True, reason="")

    def _check_internal(self, tool_name: str) -> GuardrailDecision:
        """Internal check logic — pure function, no exception handling.

        Priority order:
        1. Denylist check (highest priority — explicit denial always wins)
        2. Allowlist check (if non-empty, tool must be listed)
        3. Default allow (if no lists configured)
        """
        # 1. Denylist — explicit denial overrides everything
        if tool_name in self._denylist:
            logger.debug("[guardrail] denied (denylist): tool=%s", tool_name)
            return GuardrailDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is explicitly denied",
            )

        # 2. Allowlist — if configured, tool must be listed
        if self._allowlist and tool_name not in self._allowlist:
            logger.debug("[guardrail] denied (not in allowlist): tool=%s", tool_name)
            return GuardrailDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is not in the allowed list",
            )

        # 3. Default allow
        logger.debug("[guardrail] allowed: tool=%s", tool_name)
        return GuardrailDecision(allowed=True, reason="")

    @property
    def allowlist(self) -> frozenset[str]:
        """Return the configured allowlist (read-only)."""
        return frozenset(self._allowlist)

    @property
    def denylist(self) -> frozenset[str]:
        """Return the configured denylist (read-only)."""
        return frozenset(self._denylist)

    @property
    def fail_closed(self) -> bool:
        """Return whether the provider fails closed on errors."""
        return self._fail_closed


def create_provider_from_config(config: dict[str, Any]) -> NuminaGuardrailProvider:
    """Factory: create a NuminaGuardrailProvider from a config dict.

    Expected config structure (from family_adapter_cache._inject_guardrail):
        {
            "enabled": True,
            "fail_closed": True,
            "allowlist": ["get_assets", "get_liabilities"],
            "denylist": ["bash"],
        }

    Args:
        config: Guardrail configuration dict

    Returns:
        Configured NuminaGuardrailProvider instance
    """
    return NuminaGuardrailProvider(
        allowlist=config.get("allowlist"),
        denylist=config.get("denylist"),
        fail_closed=config.get("fail_closed", True),
    )
