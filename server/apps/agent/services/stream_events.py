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
    # Prompt 相关字段
    "system_prompt",
    "user_context",
    "internal_context",
    "task_description",
    "developer_prompt",
    "original_prompt",
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
        # Recursively redact arrays of objects
        elif isinstance(value, list) and value:
            result[key] = [
                redact_sensitive_fields(item, depth + 1) if isinstance(item, dict) else item
                for item in value
            ]
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
        display_key: str | None = None,
    ) -> StreamEvent:
        # Redact sensitive fields before streaming (primary protection layer)
        redacted_args = redact_sensitive_fields(arguments)
        tool_payload = {
            "id": self._next_tool_id(),
            "name": tool_name,
            "tool_type": tool_type or "unknown",
            "display_name": display_name or tool_name,
            "icon": icon or "tool",
            "arguments": redacted_args,
        }
        # Include i18n key for frontend translation when available
        if display_key:
            tool_payload["display_key"] = display_key
        return self._event("tool.call", {"tool": tool_payload})

    def tool_result(
        self,
        tool_id: str,
        success: bool,
        execution_time_ms: int,
        data: Any | None = None,
        error: str | None = None,
    ) -> StreamEvent:
        # Redact sensitive fields from tool result data before streaming.
        # This is the primary protection layer (spec R6) - tools may return
        # data from external APIs/MCP servers that could contain credentials.
        redacted_data: Any = data
        if isinstance(data, dict) and data:
            redacted_data = redact_sensitive_fields(data)
        elif isinstance(data, list) and data:
            redacted_data = [
                redact_sensitive_fields(item) if isinstance(item, dict) else item
                for item in data
            ]

        return self._event(
            "tool.result",
            {
                "tool_id": tool_id,
                "result": {
                    "success": success,
                    "data": redacted_data,
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

    def subagent_update(
        self,
        task_id: str,
        status: str,
        title: str | None = None,
        description: str | None = None,
        result: str | None = None,
        error: str | None = None,
    ) -> StreamEvent:
        """Emit subagent.update event for DeerFlow task delegation progress.

        Mirrors DeerFlow's StreamWriter custom events (task_started, task_running,
        task_completed, task_failed) but consolidated into a single subagent.update
        type for frontend normalization simplicity.

        Args:
            task_id: Unique task identifier from DeerFlow task delegation
            status: "running" | "done" | "failed"
            title: Human-readable task title
            description: Progress description (shown during running state)
            result: Final result text (shown when status=done)
            error: Error message (shown when status=failed)
        """
        return self._event(
            "subagent.update",
            {
                "subagent": {
                    "taskId": task_id,
                    "status": status,
                    "title": title,
                    "description": description,
                    "result": result,
                    "error": error,
                }
            },
        )

    def tool_progress(self, tool_id: str, message: str) -> StreamEvent:
        return self._event("tool.progress", {"tool_id": tool_id, "message": message})

    def error(self, message: str, code: str = "stream_error") -> StreamEvent:
        return self._event("capability.error", {"error": {"message": message, "code": code}})
