"""JSONL session journal — append-only event log per AI Agent session.

One file per session: data/sessions/{family_id}/{session_id}.jsonl
Each line is a complete JSON event conforming to spec §7 common fields.

Design principles (mirrors DeerFlow JsonlRunEventStore):
- Append-only: events are never modified after writing.
- Silent failure: write errors are logged at WARNING, never raised.
- Path safety: family_id and session_id are validated against the same
  regex used by DeerFlow (_validate_id) to prevent path traversal.
- Visibility field: "public" | "internal" | "debug"
  - public:   user-visible (user_message, assistant_message, tool events)
  - internal: system events (tokens, phase transitions, session lifecycle)
  - debug:    verbose trace, excluded from API responses by default
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from apps.agent.app.config import settings

logger = logging.getLogger(__name__)

# Same pattern as DeerFlow's _validate_id — alphanumeric, dash, underscore only.
_SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]+$")


def _validate_id(value: str, label: str) -> str:
    if not value or not _SAFE_ID_PATTERN.match(value):
        raise ValueError(
            f"Invalid {label}: must be alphanumeric/dash/underscore, got {value!r}"
        )
    return value


def _make_event(
    event_type: str,
    *,
    session_id: str,
    family_id: str,
    user_id: str | None = None,
    actor: str = "system",
    visibility: str = "internal",
    payload: dict[str, Any] | None = None,
    schema_version: str = "1.0",
) -> dict[str, Any]:
    """Build a JSONL event dict with all common fields from spec §7."""
    return {
        "eventId": str(uuid.uuid4()),
        "sessionId": session_id,
        "familyId": family_id,
        "userId": user_id,
        "type": event_type,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
        "actor": actor,
        "visibility": visibility,
        "schemaVersion": schema_version,
        **(payload or {}),
    }


class SessionJournalService:
    """Append-only JSONL writer for AI Agent session events."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base_dir = Path(base_dir)
        # Maps (family_id, session_id) → resolved Path, set on
        # write_session_start. Allows orchestrator to pass a date-based
        # jsonl_path without changing every write_* method signature.
        # Keying on family_id is load-bearing: thread_id arrives from the
        # request body and a malicious or scripted client can reuse any
        # value, so a session_id-only key risks cross-tenant path bleed
        # where family A's writes redirect into family B's JSONL.
        self._path_cache: dict[tuple[str, str], Path] = {}

    def _session_path(self, family_id: str, session_id: str, capability: str = "_default", user_id: str = "_shared") -> Path:
        _validate_id(family_id, "family_id")
        _validate_id(session_id, "session_id")
        _validate_id(capability, "capability")
        _validate_id(user_id, "user_id")
        # Use cached path if available (set by write_session_start).
        # Cache key includes family_id to prevent cross-tenant collisions.
        cache_key = (family_id, session_id)
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        return self._base_dir / family_id / "agent" / capability / user_id / f"{session_id}.jsonl"

    def resolve_path(
        self,
        family_id: str,
        session_id: str,
        capability: str = "agent",
        user_id: str = "_shared",
    ) -> Path:
        """Public resolver for the jsonl path of a session.

        Used by ``agent_dispatch`` to compute the path string passed to
        ``write_session_start`` (and stored alongside ai_chat_sessions). Note
        ``capability`` is restricted by ``_validate_id``'s ``[A-Za-z0-9_\\-]+``
        regex — Chinese agent names like 数鸣 don't pass it, so callers must
        pin the segment to the literal ``"agent"`` token.
        """
        return self._session_path(family_id, session_id, capability=capability, user_id=user_id)

    def append_event(self, family_id: str, session_id: str, event: dict[str, Any]) -> None:
        """Append one event line. Failures are logged and swallowed."""
        path = self._session_path(family_id, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
        except Exception:
            logger.warning(
                "session_journal write failed session=%s family=%s",
                session_id,
                family_id,
            )

    def read_events(self, family_id: str, session_id: str, jsonl_path: str | None = None) -> list[dict[str, Any]]:
        """Read all events for a session. Malformed lines are skipped."""
        if jsonl_path:
            path = Path(jsonl_path)
        else:
            path = self._session_path(family_id, session_id)
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                logger.debug("session_journal skipping malformed line in %s", path)
        return events

    def iter_events(self, family_id: str, session_id: str, jsonl_path: str | None = None) -> Iterator[dict[str, Any]]:
        """Yield events one by one (streaming-friendly). Malformed lines skipped."""
        if jsonl_path:
            path = Path(jsonl_path)
        else:
            path = self._session_path(family_id, session_id)
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    logger.debug("session_journal skipping malformed line in %s", path)

    # ── Convenience event constructors ────────────────────────────────────────

    def write_session_start(
        self,
        *,
        family_id: str,
        session_id: str,
        user_id: str | None,
        capability: str,
        model_name: str | None,
        jsonl_path: str,
    ) -> None:
        # Cache the resolved path so all subsequent writes for this session
        # use the date-based directory structure set by the orchestrator.
        # Cache key is (family_id, session_id) — see __init__ for rationale.
        resolved = Path(jsonl_path)
        self._path_cache[(family_id, session_id)] = resolved
        event = _make_event(
            "session.start",
            session_id=session_id,
            family_id=family_id,
            user_id=user_id,
            actor="system",
            visibility="internal",
            payload={
                "capability": capability,
                "modelName": model_name,
                "jsonlPath": jsonl_path,
            },
        )
        self.append_event(family_id, session_id, event)

    def write_user_message(
        self,
        *,
        family_id: str,
        session_id: str,
        user_id: str | None,
        content: str,
    ) -> None:
        event = _make_event(
            "user.message",
            session_id=session_id,
            family_id=family_id,
            user_id=user_id,
            actor="user",
            visibility="public",
            payload={"content": content},
        )
        self.append_event(family_id, session_id, event)

    def write_assistant_message(
        self,
        *,
        family_id: str,
        session_id: str,
        content: str,
        model_name: str | None = None,
    ) -> None:
        event = _make_event(
            "assistant.message",
            session_id=session_id,
            family_id=family_id,
            actor="assistant",
            visibility="public",
            payload={"content": content, "modelName": model_name},
        )
        self.append_event(family_id, session_id, event)

    def write_tool_call(
        self,
        *,
        family_id: str,
        session_id: str,
        tool_name: str,
        tool_id: str,
        arguments: dict[str, Any],
    ) -> None:
        event = _make_event(
            "tool.call",
            session_id=session_id,
            family_id=family_id,
            actor="assistant",
            visibility="public",
            payload={"tool": {"id": tool_id, "name": tool_name, "display_name": tool_name, "icon": "tool", "arguments": arguments}},
        )
        self.append_event(family_id, session_id, event)

    def write_tool_result(
        self,
        *,
        family_id: str,
        session_id: str,
        tool_id: str,
        success: bool,
        execution_time_ms: int,
        error: str | None = None,
    ) -> None:
        event = _make_event(
            "tool.result",
            session_id=session_id,
            family_id=family_id,
            actor="tool",
            visibility="public",
            payload={
                "tool_id": tool_id,
                "result": {
                    "success": success,
                    "execution_time_ms": execution_time_ms,
                    "error": error,
                },
            },
        )
        self.append_event(family_id, session_id, event)

    def write_plan_update(
        self,
        *,
        family_id: str,
        session_id: str,
        todos: list[dict[str, Any]],
    ) -> None:
        """Write plan.update event for DeerFlow todo/plan progress.

        Called when DeerFlow's write_todos tool updates ThreadState.todos.
        Each todo has: id, content, status (pending/active/done/error).

        Args:
            family_id: Family identifier
            session_id: Session identifier
            todos: List of todo items from DeerFlow ThreadState.todos
        """
        event = _make_event(
            "plan.update",
            session_id=session_id,
            family_id=family_id,
            actor="assistant",
            visibility="public",
            payload={"todos": todos},
        )
        self.append_event(family_id, session_id, event)

    def write_subagent_update(
        self,
        *,
        family_id: str,
        session_id: str,
        task_id: str,
        status: str,
        title: str | None = None,
        description: str | None = None,
        result: str | None = None,
        error: str | None = None,
    ) -> None:
        """Write subagent.update event for DeerFlow task delegation progress.

        Mirrors DeerFlow's StreamWriter custom events (task_started, task_running,
        task_completed, task_failed, task_cancelled, task_timed_out) consolidated
        into a single event type for JSONL replay simplicity.

        Args:
            family_id: Family identifier
            session_id: Session identifier
            task_id: Unique task identifier from DeerFlow task delegation
            status: "running" | "done" | "failed" | "cancelled" | "timed_out"
            title: Human-readable task title
            description: Progress description (shown during running state)
            result: Final result text (shown when status=done)
            error: Error message (shown when status=failed/cancelled/timed_out)
        """
        event = _make_event(
            "subagent.update",
            session_id=session_id,
            family_id=family_id,
            actor="assistant",
            visibility="public",
            payload={
                "subagent": {
                    "taskId": task_id,
                    "status": status,
                    "title": title,
                    "description": description,
                    "result": result,
                    "error": error,
                },
            },
        )
        self.append_event(family_id, session_id, event)

    def write_session_end(
        self,
        *,
        family_id: str,
        session_id: str,
        success: bool,
        duration_ms: int,
        tokens_used: int = 0,
    ) -> None:
        event = _make_event(
            "session.end",
            session_id=session_id,
            family_id=family_id,
            actor="system",
            visibility="public",
            payload={
                "success": success,
                "durationMs": duration_ms,
                "tokensUsed": tokens_used,
            },
        )
        self.append_event(family_id, session_id, event)


# Module-level singleton — initialized from settings at import time.
session_journal = SessionJournalService(settings.SESSIONS_DATA_DIR)
