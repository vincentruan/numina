"""Run event store — structured event persistence for agent runs.

Records run lifecycle events (start/end, LLM responses, tool results) to
local JSONL files, queryable by thread_id and family_id. One file per
family_id under {SESSIONS_DATA_DIR}/run_events/{family_id}.jsonl.

Replaces the no-op session_journal stub for structured event recording.
"""

from __future__ import annotations

import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from packages.core.logging import get_logger

logger = get_logger(__name__)

# Defense-in-depth: family_id comes from the JWT `fid` claim (server-issued
# snowflake ID), so it is trusted in practice. But the value becomes a
# filename, so a forged token with separators could escape the base directory.
# Snowflake IDs are numeric; allow alphanumeric + `_` / `-` for flexibility.
_FAMILY_ID_RE = re.compile(r"^[A-Za-z0-9_\-]+$")


class RunEvent(BaseModel):
    """A single run lifecycle event."""

    model_config = ConfigDict(extra="allow")

    event_type: str  # run.start, run.end, llm.ai.response, llm.tool.result, middleware:*
    run_id: str
    thread_id: str
    family_id: str
    timestamp: str  # ISO 8601 UTC
    data: dict[str, Any] = Field(default_factory=dict)


class RunEventStore:
    """Append-only JSONL event store, one file per family_id.

    Thread-safe via a module-level lock (agent runs are few and concurrent
    writes to the same family file are rare but possible).
    """

    def __init__(self, sessions_data_dir: str | Path) -> None:
        self._base_dir = Path(sessions_data_dir) / "run_events"
        self._lock = threading.Lock()

    def _file_for_family(self, family_id: str) -> Path:
        """Resolve the JSONL file path for a family_id.

        Raises ``ValueError`` when the family_id contains characters that could
        escape the base directory (defense-in-depth: the caller should always
        supply a server-issued snowflake ID, but the filename boundary is a
        trust boundary of its own).
        """
        if not _FAMILY_ID_RE.match(family_id):
            raise ValueError(f"Invalid family_id: {family_id!r}")
        return self._base_dir / f"{family_id}.jsonl"

    def record(self, event: RunEvent) -> None:
        """Append an event to the family's JSONL file."""
        path = self._file_for_family(event.family_id)
        line = event.model_dump_json()
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        logger.debug(
            "run_event recorded: %s run=%s thread=%s",
            event.event_type,
            event.run_id,
            event.thread_id,
        )

    def record_raw(
        self,
        event_type: str,
        run_id: str,
        thread_id: str,
        family_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Convenience: build a RunEvent with current timestamp and record it."""
        event = RunEvent(
            event_type=event_type,
            run_id=run_id,
            thread_id=thread_id,
            family_id=family_id,
            timestamp=datetime.now(UTC).isoformat(),
            data=data or {},
        )
        self.record(event)

    def query_by_thread(self, thread_id: str, *, family_id: str | None = None) -> list[RunEvent]:
        """Return events for a thread, ordered by timestamp.

        If family_id is given, only that family's file is scanned.
        Otherwise all family files are scanned (slower but supports
        cross-family thread lookup).
        """
        if family_id:
            files = [self._file_for_family(family_id)]
        else:
            files = sorted(self._base_dir.glob("*.jsonl")) if self._base_dir.exists() else []

        events: list[RunEvent] = []
        for path in files:
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = RunEvent.model_validate_json(line)
                        if ev.thread_id == thread_id:
                            events.append(ev)
                    except Exception:
                        logger.warning("run_event_store: skipping malformed line in %s", path)
        events.sort(key=lambda e: e.timestamp)
        return events

    def query_by_family(self, family_id: str, *, limit: int = 100, offset: int = 0) -> list[RunEvent]:
        """Return events for a family, ordered by timestamp, with pagination."""
        path = self._file_for_family(family_id)
        if not path.exists():
            return []

        events: list[RunEvent] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(RunEvent.model_validate_json(line))
                except Exception:
                    logger.warning("run_event_store: skipping malformed line in %s", path)
        events.sort(key=lambda e: e.timestamp)
        return events[offset : offset + limit]


# ---------------------------------------------------------------------------
# Module-level lazy singleton — avoids import-time config access
# ---------------------------------------------------------------------------

_event_store: RunEventStore | None = None


def _get_event_store() -> RunEventStore:
    """Lazy-init the run event store (avoids import-time config access)."""
    global _event_store  # noqa: PLW0603
    if _event_store is None:
        from apps.agent.app.config import settings

        _event_store = RunEventStore(settings.SESSIONS_DATA_DIR)
    return _event_store
