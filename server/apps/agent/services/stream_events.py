"""Structured NDJSON stream events for Agent chat."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Sensitive field keys that must be redacted before streaming to frontend.
# Uses exact case-insensitive matching to avoid false positives (e.g., "keyboard").
SENSITIVE_KEYS: frozenset[str] = frozenset([
    "api_key",
    "apikey",
    "key",  # catch standalone "key" but not "keyboard" (exact match)
    "password",
    "pwd",
    "pass",  # catch standalone "pass" but not "compass" (exact match)
    "token",
    "access_token",
    "auth_token",
    "secret",
    "secret_key",
    "credential",
    "credentials",
    "private_key",
    "private",
])

# Known-safe field names that should NOT be redacted even if they contain sensitive substrings.
# This whitelist prevents false positives like "keyboard", "keypress", "passenger".
SENSITIVE_KEY_WHITELIST: frozenset[str] = frozenset([
    "keyboard",
    "keypress",
    "keybinding",
    "passenger",
    "compass",
    "passport",  # travel document, not auth
    "bypass",
    "gateway",
])


def redact_sensitive_fields(obj: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Redact sensitive fields from a dict before streaming to frontend.

    Args:
        obj: The dict to redact (tool arguments, config, etc.)
        depth: Current recursion depth (limit 5 to prevent infinite loops)

    Returns:
        A new dict with sensitive values replaced by "***REDACTED***"

    Security note: This is the primary protection layer. Frontend redaction
    (aiEventRedactor.ts) is defense-in-depth only.
    """
    if depth > 5:
        logger.warning("[stream_events] redaction depth limit reached at depth=%d", depth)
        return {"_truncated": "..."}

    result: dict[str, Any] = {}
    for key, value in obj.items():
        lower_key = key.lower()

        # Check whitelist first (known-safe fields never redacted)
        if lower_key in SENSITIVE_KEY_WHITELIST:
            result[key] = value
            continue

        # Check exact match against sensitive keys
        if lower_key in SENSITIVE_KEYS:
            result[key] = "***REDACTED***"
            logger.debug("[stream_events] redacted field: %s", key)
            continue

        # Recursively redact nested dicts
        if isinstance(value, dict) and value:
            result[key] = redact_sensitive_fields(value, depth + 1)
        else:
            result[key] = value

    return result


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
        tool_type: str | None = None,
    ) -> StreamEvent:
        # Redact sensitive fields before streaming (primary protection layer)
        redacted_args = redact_sensitive_fields(arguments)
        return self._event(
            "tool.call",
            {
                "tool": {
                    "id": self._next_tool_id(),
                    "name": tool_name,
                    "tool_type": tool_type or "unknown",
                    "display_name": display_name or tool_name,
                    "icon": icon or "tool",
                    "arguments": redacted_args,
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
        suggestions: list[str] | None = None,
    ) -> StreamEvent:
        result: dict = {
            "summary": summary,
            "tokens_used": tokens_used,
            "execution_time_ms": execution_time_ms,
            "tools_used": tools_used or [],
        }
        if suggestions:
            result["suggestions"] = suggestions
        return self._event("capability.end", {"result": result})

    def plan_update(self, todos: list[dict]) -> StreamEvent:
        normalized = [
            {
                "id": f"plan-{i}",
                "content": todo.get("content", ""),
                "status": todo.get("status", "pending"),
            }
            for i, todo in enumerate(todos)
        ]
        return self._event("plan.update", {"todos": normalized})

    def tool_progress(self, tool_id: str, message: str) -> StreamEvent:
        return self._event("tool.progress", {"tool_id": tool_id, "message": message})

    def error(self, message: str, code: str = "stream_error") -> StreamEvent:
        return self._event("capability.error", {"error": {"message": message, "code": code}})
