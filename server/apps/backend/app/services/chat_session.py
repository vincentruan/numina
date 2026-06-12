"""Chat session service — JSONL file operations for conversation history."""

import asyncio
import hashlib
import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from filelock import FileLock
from filelock import Timeout as FileLockTimeout
from sqlalchemy.orm import Session

from apps.backend.app.config import settings
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.storage_backend import StorageBackend
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)

# UUID validation regex (36 chars: 8-4-4-4-12 hex digits with hyphens)
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)
# Snowflake ID pattern (numeric string, 15-19 digits)
SNOWFLAKE_PATTERN = re.compile(r"^\d{15,19}$")


def _validate_id(value: str | int, name: str) -> str:
    """Validate that a value is a valid UUID or Snowflake ID format (path traversal protection).
    Returns the string representation."""
    value = str(value)
    if not (UUID_PATTERN.match(value) or SNOWFLAKE_PATTERN.match(value)):
        raise ValueError(f"{name} must be a valid UUID or Snowflake ID, got: {value}")
    return value


def _resolve_and_validate_path(family_id: str | int, session_id: str | int) -> Path:
    """Construct and validate JSONL file path under workspaces/tenants/{fid}/chat/.

    Returns the absolute resolved path if valid.
    Raises ValueError if path is invalid or outside CHAT_DIR.
    """
    family_id = _validate_id(family_id, "family_id")
    session_id = _validate_id(session_id, "session_id")

    chat_dir_resolved = Path(settings.CHAT_DIR).resolve()
    # New path structure: workspaces/tenants/{family_id}/chat/{session_id}.jsonl
    target_path = chat_dir_resolved / "tenants" / family_id / "chat" / f"{session_id}.jsonl"
    target_resolved = target_path.resolve()

    # Verify the resolved path is under CHAT_DIR
    try:
        target_resolved.relative_to(chat_dir_resolved)
    except ValueError as e:
        raise ValueError(
            f"Invalid path: {target_path} resolves outside CHAT_DIR"
        ) from e

    return target_resolved


def _compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def _sync_append_message(
    file_path: Path,
    lock_path: Path,
    role: str,
    content: str,
) -> tuple[str, str]:
    """Synchronous file append with locking (runs in executor).

    This function ONLY does file I/O (thread-safe):
    1. Acquires file lock
    2. Appends message to JSONL file
    3. Returns message_id and timestamp for db update

    Returns (message_id, timestamp) so caller can update db in main thread.
    """
    with FileLock(str(lock_path), timeout=10):
        # Append message to JSONL file
        message_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"
        message_line = json.dumps({
            "message_id": message_id,
            "role": role,
            "content": content,
            "timestamp": timestamp,
        }, ensure_ascii=False) + "\n"

        with open(file_path, "a", encoding="utf-8") as f:
            f.write(message_line)

        return message_id, timestamp


class ChatSessionService:
    """Service for managing chat sessions and JSONL file operations."""

    @staticmethod
    async def create_session(
        family_id: int,
        user_id: int,
        db: Session,
        agent_id: int | None = None,
    ) -> AIChatSession:
        """Create a new chat session with empty JSONL file.

        Raises:
            ValueError: If family_id is not a valid Snowflake ID or path is invalid
        """
        _validate_id(family_id, "family_id")

        session_id = next_id()
        jsonl_path_relative = f"tenants/{family_id}/chat/{session_id}.jsonl"

        # Validate and create file path
        file_path = _resolve_and_validate_path(family_id, session_id)

        # Create directory if not exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Create empty JSONL file
        file_path.touch()

        # Create session record
        session = AIChatSession(
            id=session_id,
            family_id=family_id,
            user_id=user_id,
            agent_id=agent_id,
            jsonl_path=jsonl_path_relative,
            message_count=0,
            cached_file_id=None,  # Will be set on first append
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        return session

    @staticmethod
    def get_session(
        session_id: int | str,
        family_id: int | str,
        db: Session,
    ) -> AIChatSession | None:
        """Fetch an existing session by ID, scoped to the family."""
        return (
            db.query(AIChatSession)
            .filter(
                AIChatSession.id == session_id,
                AIChatSession.family_id == int(family_id),
            )
            .first()
        )

    @staticmethod
    async def append_message(
        session: AIChatSession,
        role: str,
        content: str,
        user: User,
        db: Session,
    ) -> None:
        """Append a message to the session's JSONL file.

        Architecture (thread-safe):
        1. Executor: ONLY file I/O (append to JSONL, return message_id/timestamp)
        2. Main thread: DB updates using existing session/db

        Args:
            session: AIChatSession instance
            role: "user" or "assistant"
            content: Message content
            user: User instance (for CachedFile.user_id)
            db: Database session (used ONLY in main thread)

        Raises:
            ValueError: If path validation fails
            FileLockTimeout: If file lock cannot be acquired within 10 seconds
        """
        file_path = _resolve_and_validate_path(session.family_id, session.id)
        lock_path = file_path.with_suffix(".lock")

        # Run sync file I/O in executor (thread-safe)
        try:
            loop = asyncio.get_running_loop()
            message_id, timestamp = await loop.run_in_executor(
                None,
                _sync_append_message,
                file_path,
                lock_path,
                role,
                content,
            )
        except FileLockTimeout as e:
            raise FileLockTimeout(
                f"Could not acquire lock for session {session.id} — another operation is in progress"
            ) from e

        # DB updates happen in main thread (using existing session/db)
        session.message_count += 1
        if role == "assistant":
            session.last_preview = content[:100]
        session.updated_at = datetime.utcnow()

        # Recompute SHA256 and update CachedFile
        sha256 = _compute_sha256(file_path)
        size_bytes = file_path.stat().st_size

        if session.cached_file_id is None:
            # First append — create CachedFile
            cached_file = CachedFile(
                family_id=session.family_id,
                user_id=user.id,
                sha256=sha256,
                local_path=str(file_path),
                original_filename=f"{session.id}.jsonl",
                mime_type="application/x-ndjson",
                size_bytes=size_bytes,
                date_dir=datetime.now().strftime("%Y%m%d"),
            )
            db.add(cached_file)
            db.flush()
            session.cached_file_id = cached_file.id

            # Queue for remote sync if enabled
            if settings.CHAT_ENABLE_REMOTE_SYNC:
                default_backend = (
                    db.query(StorageBackend)
                    .filter_by(is_default=True, is_active=True)
                    .first()
                )
                if default_backend:
                    remote_loc = FileRemoteLocation(
                        file_id=cached_file.id,
                        backend_id=default_backend.id,
                        remote_path=f"chat/{session.family_id}/{session.id}.jsonl",
                        sync_status="pending",
                    )
                    db.add(remote_loc)
        else:
            # Subsequent append — update existing CachedFile
            cached_file = db.query(CachedFile).filter_by(id=session.cached_file_id).first()
            if cached_file:
                cached_file.sha256 = sha256
                cached_file.size_bytes = size_bytes

        db.commit()

    @staticmethod
    async def read_messages(session: AIChatSession) -> list[dict[str, Any]]:
        """Read all messages from the session's JSONL file.

        Args:
            session: AIChatSession instance

        Returns:
            List of message dicts in ascending order by timestamp

        Raises:
            ValueError: If path validation fails
        """
        file_path = _resolve_and_validate_path(session.family_id, session.id)

        if not file_path.exists():
            return []

        messages = []
        with open(file_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                    messages.append(message)
                except json.JSONDecodeError:
                    # Skip partial/corrupted lines
                    continue

        return messages

    @staticmethod
    async def fork_session(
        session: AIChatSession,
        fork_from_message_id: str,
        user: User,
        db: Session,
    ) -> AIChatSession:
        """Fork a session from a specific message, creating a new branch.

        Copies all messages up to (but not including) the specified message_id
        into a new session. The new session inherits the original's agent_id
        and other metadata.

        Args:
            session: Original AIChatSession to fork from
            fork_from_message_id: The message_id to fork from (this message and
                all following messages are excluded from the fork)
            user: User creating the fork (for ownership and CachedFile.user_id)
            db: Database session

        Returns:
            New AIChatSession with copied messages up to fork point

        Raises:
            ValueError: If path validation fails or message_id not found
        """
        # Read original messages
        messages = await ChatSessionService.read_messages(session)

        # Find the fork point - messages up to (not including) this message_id
        fork_messages = []
        found_fork_point = False
        for msg in messages:
            if msg.get("message_id") == fork_from_message_id:
                found_fork_point = True
                break
            fork_messages.append(msg)

        if not found_fork_point and fork_from_message_id:
            raise ValueError(f"Message {fork_from_message_id} not found in session")

        # Create new session
        new_session_id = next_id()
        jsonl_path_relative = f"tenants/{session.family_id}/chat/{new_session_id}.jsonl"
        file_path = _resolve_and_validate_path(session.family_id, new_session_id)

        # Create directory and file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.touch()

        # Create new session record
        new_session = AIChatSession(
            id=new_session_id,
            family_id=session.family_id,
            user_id=user.id,
            agent_id=session.agent_id,
            jsonl_path=jsonl_path_relative,
            message_count=len(fork_messages),
            cached_file_id=None,
            title=session.title,
            source=session.source,
        )
        db.add(new_session)
        db.flush()

        # Copy forked messages to new JSONL file
        if fork_messages:
            lock_path = file_path.with_suffix(".lock")
            with FileLock(str(lock_path), timeout=10), open(file_path, "w", encoding="utf-8") as f:
                for msg in fork_messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + "\n")

            # Create CachedFile for the new session
            sha256 = _compute_sha256(file_path)
            size_bytes = file_path.stat().st_size
            cached_file = CachedFile(
                family_id=session.family_id,
                user_id=user.id,
                sha256=sha256,
                local_path=str(file_path),
                original_filename=f"{new_session_id}.jsonl",
                mime_type="application/x-ndjson",
                size_bytes=size_bytes,
                date_dir=datetime.now().strftime("%Y%m%d"),
            )
            db.add(cached_file)
            db.flush()
            new_session.cached_file_id = cached_file.id

            # Queue for remote sync if enabled
            if settings.CHAT_ENABLE_REMOTE_SYNC:
                default_backend = (
                    db.query(StorageBackend)
                    .filter_by(is_default=True, is_active=True)
                    .first()
                )
                if default_backend:
                    remote_loc = FileRemoteLocation(
                        file_id=cached_file.id,
                        backend_id=default_backend.id,
                        remote_path=f"chat/{session.family_id}/{new_session_id}.jsonl",
                        sync_status="pending",
                    )
                    db.add(remote_loc)

        db.commit()
        db.refresh(new_session)
        return new_session
