"""ToolProgressMiddleware — tool execution health tracking.

Tracks each tool execution through a state machine (ACTIVE → WARNED → BLOCKED)
based on elapsed time.  Emits ``tool_progress`` events on state transitions so
the frontend can display tool execution health.

Activation: config-driven via ``tool_progress.enabled: true`` in the per-family
DeerFlow temp config (injected by ``family_adapter_cache``).

LangGraph integration: extends ``AgentMiddleware`` and implements
``wrap_tool_call`` to time each tool execution through the LangGraph
middleware chain.  The existing ``before_tool_call`` / ``after_tool_call``
methods remain available for direct (non-chain) usage.

Thread safety: ``_tool_states`` is guarded by ``_lock`` (threading.Lock).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from packages.core.logging import get_logger

logger = get_logger(__name__)


class ToolStatus(StrEnum):
    """Tool execution health status."""

    ACTIVE = "active"
    WARNED = "warned"
    BLOCKED = "blocked"


@dataclass
class _ToolState:
    """Internal tracking state for a single tool execution."""

    tool_call_id: str
    tool_name: str
    start_time: float
    status: ToolStatus = ToolStatus.ACTIVE


@dataclass
class ToolProgressEvent:
    """Emitted when a tool transitions between states.

    Attributes:
        tool_call_id: Unique identifier for this tool invocation.
        tool_name: Name of the tool.
        status: Current status (ACTIVE / WARNED / BLOCKED).
        elapsed_seconds: Time since the tool started.
        message: Human-readable progress message.
    """

    tool_call_id: str
    tool_name: str
    status: ToolStatus
    elapsed_seconds: float
    message: str = ""


class ToolProgressMiddleware:
    """Tool execution health tracker with ACTIVE → WARNED → BLOCKED states.

    Configuration (injected via ``family_adapter_cache._inject_tool_progress``):

    .. code-block:: yaml

        tool_progress:
          enabled: true
          warn_threshold_seconds: 30.0
          hard_stop_threshold_seconds: 120.0
    """

    def __init__(
        self,
        warn_threshold_seconds: float = 30.0,
        hard_stop_threshold_seconds: float = 120.0,
    ) -> None:
        """Initialize the middleware.

        Args:
            warn_threshold_seconds: Duration after which a tool is WARNED.
            hard_stop_threshold_seconds: Duration after which a tool is BLOCKED.
        """
        self._warn_threshold = warn_threshold_seconds
        self._hard_stop_threshold = hard_stop_threshold_seconds
        self._tool_states: dict[str, _ToolState] = {}
        self._lock = threading.Lock()

        logger.debug(
            "[tool_progress] initialized: warn=%.1fs hard_stop=%.1fs",
            warn_threshold_seconds,
            hard_stop_threshold_seconds,
        )

    # -- Hooks ---------------------------------------------------------------

    def before_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
    ) -> ToolProgressEvent | None:
        """Record tool execution start.

        Returns:
            A ToolProgressEvent with ACTIVE status, or None on error.
        """
        with self._lock:
            self._tool_states[tool_call_id] = _ToolState(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                start_time=time.monotonic(),
            )

        event = ToolProgressEvent(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=ToolStatus.ACTIVE,
            elapsed_seconds=0.0,
            message=f"Tool '{tool_name}' started",
        )
        logger.debug(
            "[tool_progress] started: tool=%s call_id=%s",
            tool_name,
            tool_call_id,
        )
        return event

    def after_tool_call(
        self,
        tool_call_id: str,
        tool_name: str,
        success: bool = True,
    ) -> ToolProgressEvent | None:
        """Record tool execution completion and compute final status.

        Returns:
            A ToolProgressEvent with the final status (ACTIVE / WARNED / BLOCKED),
            or None if the tool_call_id was not tracked.
        """
        with self._lock:
            state = self._tool_states.pop(tool_call_id, None)

        if state is None:
            logger.debug(
                "[tool_progress] after_tool_call: unknown call_id=%s (may have started before middleware)",
                tool_call_id,
            )
            return None

        elapsed = time.monotonic() - state.start_time
        status = self._compute_status(elapsed)

        event = ToolProgressEvent(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            status=status,
            elapsed_seconds=round(elapsed, 2),
            message=self._build_message(tool_name, status, elapsed, success),
        )

        if status == ToolStatus.BLOCKED:
            logger.warning(
                "[tool_progress] BLOCKED: tool=%s call_id=%s elapsed=%.1fs threshold=%.1fs",
                tool_name,
                tool_call_id,
                elapsed,
                self._hard_stop_threshold,
            )
        elif status == ToolStatus.WARNED:
            logger.info(
                "[tool_progress] WARNED: tool=%s call_id=%s elapsed=%.1fs threshold=%.1fs",
                tool_name,
                tool_call_id,
                elapsed,
                self._warn_threshold,
            )
        else:
            logger.debug(
                "[tool_progress] completed: tool=%s call_id=%s elapsed=%.1fs status=%s",
                tool_name,
                tool_call_id,
                elapsed,
                status.value,
            )

        return event

    # -- LangGraph AgentMiddleware integration ---------------------------------

    def wrap_tool_call(
        self,
        request: Any,
        handler: Callable,
    ) -> Any:
        """Track tool execution timing through the LangGraph middleware chain.

        Delegates to ``before_tool_call`` / ``after_tool_call`` for timing.
        Does NOT block — the upstream ``ToolProgressMiddleware`` handles
        result-quality blocking; this middleware provides wall-clock timing
        for frontend display.
        """
        tool_call_id = str(request.tool_call.get("id", ""))
        tool_name = str(request.tool_call.get("name", ""))
        self.before_tool_call(tool_call_id, tool_name)
        try:
            result = handler(request)
        except Exception:
            self.after_tool_call(tool_call_id, tool_name, success=False)
            raise
        self.after_tool_call(tool_call_id, tool_name, success=True)
        return result

    async def awrap_tool_call(
        self,
        request: Any,
        handler: Callable,
    ) -> Any:
        """Async variant of :meth:`wrap_tool_call`."""
        tool_call_id = str(request.tool_call.get("id", ""))
        tool_name = str(request.tool_call.get("name", ""))
        self.before_tool_call(tool_call_id, tool_name)
        try:
            result = await handler(request)
        except Exception:
            self.after_tool_call(tool_call_id, tool_name, success=False)
            raise
        self.after_tool_call(tool_call_id, tool_name, success=True)
        return result

    # -- Introspection -------------------------------------------------------

    def get_active_tools(self) -> list[dict[str, Any]]:
        """Return a snapshot of currently tracked tools."""
        now = time.monotonic()
        with self._lock:
            return [
                {
                    "tool_call_id": s.tool_call_id,
                    "tool_name": s.tool_name,
                    "status": s.status.value,
                    "elapsed_seconds": round(now - s.start_time, 2),
                }
                for s in self._tool_states.values()
            ]

    @property
    def active_count(self) -> int:
        """Return the number of currently tracked tool executions."""
        with self._lock:
            return len(self._tool_states)

    # -- Internals -----------------------------------------------------------

    def _compute_status(self, elapsed: float) -> ToolStatus:
        """Compute status from elapsed time."""
        if elapsed >= self._hard_stop_threshold:
            return ToolStatus.BLOCKED
        if elapsed >= self._warn_threshold:
            return ToolStatus.WARNED
        return ToolStatus.ACTIVE

    @staticmethod
    def _build_message(
        tool_name: str,
        status: ToolStatus,
        elapsed: float,
        success: bool,
    ) -> str:
        """Build a human-readable progress message."""
        outcome = "completed" if success else "failed"
        if status == ToolStatus.BLOCKED:
            return (
                f"Tool '{tool_name}' {outcome} after {elapsed:.1f}s "
                f"(exceeded hard stop threshold)"
            )
        if status == ToolStatus.WARNED:
            return (
                f"Tool '{tool_name}' {outcome} after {elapsed:.1f}s "
                f"(exceeded warn threshold)"
            )
        return f"Tool '{tool_name}' {outcome} in {elapsed:.1f}s"
