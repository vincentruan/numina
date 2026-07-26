"""Stream events builder - stub implementation.

This module was removed but is still referenced by agent_dispatch.py.
Provides minimal implementation to maintain backward compatibility.
"""

import json
from typing import Any


class EventStreamBuilder:
    """Stub event stream builder."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize with no-op."""
        self._current_event: dict[str, Any] | None = None

    def phase(self, phase_name: str, metadata: dict | None = None) -> "EventStreamBuilder":
        """Create phase event."""
        self._current_event = {
            "type": f"phase.{phase_name}",
            "data": metadata or {}
        }
        return self

    def tool_call(self, *args: Any, **kwargs: Any) -> "EventStreamBuilder":
        """Create tool call event."""
        self._current_event = {
            "type": "tool.call",
            "data": {}
        }
        return self

    def tool_result(self, *args: Any, **kwargs: Any) -> "EventStreamBuilder":
        """Create tool result event."""
        self._current_event = {
            "type": "tool.result",
            "data": {}
        }
        return self

    def token(self, *args: Any, **kwargs: Any) -> "EventStreamBuilder":
        """Create token event."""
        self._current_event = {
            "type": "token",
            "data": {}
        }
        return self

    def error(self, message: str, code: str = "ERROR") -> "EventStreamBuilder":
        """Create error event."""
        self._current_event = {
            "type": "capability.error",
            "error": {"message": message, "code": code}
        }
        return self

    def end(self, *args: Any, **kwargs: Any) -> "EventStreamBuilder":
        """Create end event."""
        # Extract execution_time_ms from kwargs if provided
        execution_time = kwargs.get("execution_time_ms", 0)
        self._current_event = {
            "type": "capability.end",
            "result": {"execution_time_ms": execution_time}
        }
        return self

    def to_ndjson(self) -> str:
        """Return NDJSON line for current event."""
        if self._current_event is None:
            return ""
        event = self._current_event
        self._current_event = None
        return json.dumps(event) + "\n"

    @property
    def payload(self) -> dict[str, Any]:
        """Return the current event payload for caller mutation."""
        if self._current_event is None:
            self._current_event = {"type": "unknown", "data": {}}
        return self._current_event
