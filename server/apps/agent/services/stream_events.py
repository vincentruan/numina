"""Structured NDJSON stream events for Agent chat."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class StreamEvent:
    id: str
    type: str
    timestamp: float
    capability_id: str
    task_id: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "timestamp": self.timestamp,
            "capability_id": self.capability_id,
            "task_id": self.task_id,
            **self.payload,
        }

    def to_ndjson(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":")) + "\n"


class EventStreamBuilder:
    def __init__(self, capability_id: str, task_id: str):
        self.capability_id = capability_id
        self.task_id = task_id
        self._event_id = 0
        self._tool_id = 0

    def _next_event_id(self) -> str:
        self._event_id += 1
        return f"{self.task_id}-{self._event_id:04d}"

    def _next_tool_id(self) -> str:
        self._tool_id += 1
        return f"{self.task_id}-tool-{self._tool_id:04d}"

    def _event(self, event_type: str, payload: dict[str, Any]) -> StreamEvent:
        return StreamEvent(
            id=self._next_event_id(),
            type=event_type,
            timestamp=time.time(),
            capability_id=self.capability_id,
            task_id=self.task_id,
            payload=payload,
        )

    def phase(self, phase: str, metadata: dict[str, Any] | None = None) -> StreamEvent:
        return self._event(f"phase.{phase}", {"phase": phase, "metadata": metadata or {}})

    def token(self, token: str, is_thinking: bool) -> StreamEvent:
        return self._event("token.stream", {"token": token, "is_thinking": is_thinking})

    def tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        display_name: str | None = None,
        icon: str | None = None,
    ) -> StreamEvent:
        return self._event(
            "tool.call",
            {
                "tool": {
                    "id": self._next_tool_id(),
                    "name": tool_name,
                    "display_name": display_name or tool_name,
                    "icon": icon or "tool",
                    "arguments": arguments,
                }
            },
        )

    def tool_result(
        self,
        tool_id: str,
        success: bool,
        execution_time_ms: int,
        data: Any | None = None,
        error: str | None = None,
    ) -> StreamEvent:
        return self._event(
            "tool.result",
            {
                "tool_id": tool_id,
                "result": {
                    "success": success,
                    "data": data,
                    "error": error,
                    "execution_time_ms": execution_time_ms,
                },
            },
        )

    def end(
        self,
        summary: str,
        tokens_used: int = 0,
        execution_time_ms: int = 0,
        tools_used: list[str] | None = None,
    ) -> StreamEvent:
        return self._event(
            "capability.end",
            {
                "result": {
                    "summary": summary,
                    "tokens_used": tokens_used,
                    "execution_time_ms": execution_time_ms,
                    "tools_used": tools_used or [],
                }
            },
        )

    def error(self, message: str, code: str = "stream_error") -> StreamEvent:
        return self._event("capability.error", {"error": {"message": message, "code": code}})
