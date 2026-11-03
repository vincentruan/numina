"""Run event store — structured event persistence for agent runs.

Records run lifecycle events (start/end, LLM responses, tool results) to
local JSONL files, queryable by thread_id and family_id. One file per
family_id under {SESSIONS_DATA_DIR}/run_events/{family_id}.jsonl.

Replaces the no-op session_journal stub for structured event recording.
"""

from __future__ import annotations

import hashlib
import json
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

# T27: Empty hash for the first event in a chain (64 zeros)
_EMPTY_HASH = "0" * 64


def _compute_event_hash(prev_hash: str, event_data: dict[str, Any]) -> str:
    """Compute SHA-256 hash for an event.

    Hash is computed over prev_hash + canonical JSON of event data (excluding
    hash chain fields). Canonical JSON sorts keys and removes whitespace
    for deterministic hashing.
    """
    # Exclude hash chain fields from computation to avoid circular dependency
    data_for_hash = {
        k: v for k, v in event_data.items() if k not in ("hash", "prev_hash")
    }
    canonical = json.dumps(data_for_hash, sort_keys=True, separators=(",", ":"))
    hash_input = prev_hash + canonical
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


class RunEvent(BaseModel):
    """A single run lifecycle event."""

    model_config = ConfigDict(extra="allow")

    event_type: (
        str  # run.start, run.end, llm.ai.response, llm.tool.result, middleware:*
    )
    run_id: str
    thread_id: str
    family_id: str
    timestamp: str  # ISO 8601 UTC
    data: dict[str, Any] = Field(default_factory=dict)
    # T27: Hash chain for tamper-evidence
    prev_hash: str | None = None  # Hash of previous event (None for legacy events)
    hash: str | None = None  # Hash of this event (None for legacy events)


class RunEventStore:
    """Append-only JSONL event store, one file per family_id.

    Thread-safe via a module-level lock (agent runs are few and concurrent
    writes to the same family file are rare but possible).

    T27: Maintains a hash chain for tamper-evidence. Each event includes
    prev_hash (hash of previous event) and hash (hash of current event).
    The last hash per family_id is cached to avoid re-reading the file.
    """

    def __init__(self, sessions_data_dir: str | Path) -> None:
        self._base_dir = Path(sessions_data_dir) / "run_events"
        self._lock = threading.Lock()
        # T27: Cache last hash per family_id to avoid file reads on every write
        self._last_hash_cache: dict[str, str] = {}

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

    def _get_last_hash(self, family_id: str, path: Path) -> str:
        """Get the last hash for a family, from cache or by reading the file.

        Returns _EMPTY_HASH if the file doesn't exist or has no hashed events.
        """
        # Check cache first
        if family_id in self._last_hash_cache:
            return self._last_hash_cache[family_id]

        # Cache miss: read the last event from the file
        if not path.exists():
            return _EMPTY_HASH

        last_hash = _EMPTY_HASH
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event_data = json.loads(line)
                        event_hash = event_data.get("hash")
                        if event_hash:
                            last_hash = event_hash
                    except Exception:
                        # Skip malformed lines
                        continue
        except Exception:
            logger.warning("run_event_store: failed to read last hash from %s", path)
            return _EMPTY_HASH

        # Cache the result
        self._last_hash_cache[family_id] = last_hash
        return last_hash

    def record(self, event: RunEvent) -> None:
        """Append an event to the family's JSONL file.

        T27: Computes hash chain (prev_hash + hash) before writing.

        Chain computation, the cache update, and the file append all happen
        under the same lock. Splitting them would let two concurrent writers
        chain from the same prev_hash and fork the chain.
        """
        path = self._file_for_family(event.family_id)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            # T27: Compute hash chain
            prev_hash = self._get_last_hash(event.family_id, path)
            event_data = event.model_dump()
            event_hash = _compute_event_hash(prev_hash, event_data)
            event.prev_hash = prev_hash
            event.hash = event_hash

            # Update cache with new hash
            self._last_hash_cache[event.family_id] = event_hash

            # Write event to file
            line = event.model_dump_json()
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

        logger.debug(
            "run_event recorded: %s run=%s thread=%s hash=%s",
            event.event_type,
            event.run_id,
            event.thread_id,
            event_hash[:16],
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

    def query_by_thread(
        self, thread_id: str, *, family_id: str | None = None
    ) -> list[RunEvent]:
        """Return events for a thread, ordered by timestamp.

        If family_id is given, only that family's file is scanned.
        Otherwise all family files are scanned (slower but supports
        cross-family thread lookup).
        """
        if family_id:
            files = [self._file_for_family(family_id)]
        else:
            files = (
                sorted(self._base_dir.glob("*.jsonl"))
                if self._base_dir.exists()
                else []
            )

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
                        logger.warning(
                            "run_event_store: skipping malformed line in %s", path
                        )
        events.sort(key=lambda e: e.timestamp)
        return events

    def query_by_family(
        self, family_id: str, *, limit: int = 100, offset: int = 0
    ) -> list[RunEvent]:
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
                    logger.warning(
                        "run_event_store: skipping malformed line in %s", path
                    )
        events.sort(key=lambda e: e.timestamp)
        return events[offset : offset + limit]

    def verify_events(
        self, family_id: str, run_id: str | None = None
    ) -> dict[str, Any]:
        """Verify hash chain integrity for a family's events.

        T27: Returns verification result with status and any tampered event index.

        Args:
            family_id: Family whose event file to verify
            run_id: Optional. If provided, only count events for this run_id in the result,
                    but still verify the entire chain (since events chain across runs).

        Returns:
            dict with:
            - verified: bool | "unverified" (True if all hashes match, False if tampered, "unverified" if legacy)
            - event_count: int (events checked; if run_id provided, only events for that run)
            - tampered_event_index: int | None (index of first tampered event, if any)
            - reason: str | None (explanation for unverified or failure)
        """
        path = self._file_for_family(family_id)
        if not path.exists():
            return {
                "verified": True,
                "event_count": 0,
                "tampered_event_index": None,
                "reason": None,
            }

        events: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except Exception:
                    logger.warning(
                        "run_event_store: skipping malformed line in %s", path
                    )

        if not events:
            return {
                "verified": True,
                "event_count": 0,
                "tampered_event_index": None,
                "reason": None,
            }

        # Check if any events have hashes (new format) vs all legacy (no hashes)
        has_any_hash = any(e.get("hash") for e in events)
        if not has_any_hash:
            # Count events matching run_id if provided
            count = (
                len(events)
                if run_id is None
                else sum(1 for e in events if e.get("run_id") == run_id)
            )
            return {
                "verified": "unverified",
                "event_count": count,
                "tampered_event_index": None,
                "reason": "all events predate hash-chaining",
            }

        # Verify hash chain (must traverse all events to validate prev_hash linkage)
        prev_hash = _EMPTY_HASH
        matching_count = 0
        for idx, event_data in enumerate(events):
            event_hash = event_data.get("hash")
            event_prev_hash = event_data.get("prev_hash")

            # Count events matching run_id if provided
            if run_id is None or event_data.get("run_id") == run_id:
                matching_count += 1

            # Legacy event (no hash) in a chain with hashed events
            if not event_hash:
                # Skip verification for this event, but continue chain.
                # Valid mixed files have all legacy events first, then all hashed.
                # The first hashed event's prev_hash is _EMPTY_HASH because
                # record() fell back to it when the prior event had no hash.
                continue

            # Verify prev_hash matches expected
            if event_prev_hash != prev_hash:
                return {
                    "verified": False,
                    "event_count": matching_count,
                    "tampered_event_index": idx,
                    "reason": f"prev_hash mismatch at index {idx}",
                }

            # Recompute hash and verify
            expected_hash = _compute_event_hash(
                event_prev_hash or _EMPTY_HASH, event_data
            )
            if event_hash != expected_hash:
                return {
                    "verified": False,
                    "event_count": matching_count,
                    "tampered_event_index": idx,
                    "reason": f"hash mismatch at index {idx}",
                }

            # Update prev_hash for next iteration
            prev_hash = event_hash

        return {
            "verified": True,
            "event_count": matching_count,
            "tampered_event_index": None,
            "reason": None,
        }


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
