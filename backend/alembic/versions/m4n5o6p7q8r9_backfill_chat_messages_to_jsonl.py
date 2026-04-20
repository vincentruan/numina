"""backfill_chat_messages_to_jsonl

Exports existing ai_chat_messages rows to per-family legacy JSONL files
and creates corresponding ai_chat_sessions records.

All JSONL write and SHA256 logic is inlined — no application service imports.

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-04-20 10:01:00.000000

"""

import hashlib
import json
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, None] = "n5o6p7q8r9s0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _get_chat_dir() -> str:
    """Get CHAT_DIR from environment or use default."""
    return os.environ.get("CHAT_DIR", "./data/chat")


def _is_valid_uuid(value: str) -> bool:
    return bool(UUID_PATTERN.match(value))


def _compute_sha256(file_path: Path) -> str:
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def upgrade() -> None:
    conn = op.get_bind()
    chat_dir = _get_chat_dir()

    # Get all distinct family_ids from ai_chat_messages
    result = conn.execute(sa.text("SELECT DISTINCT family_id FROM ai_chat_messages"))
    family_ids = [row[0] for row in result]

    for family_id in family_ids:
        if not _is_valid_uuid(family_id):
            # Skip invalid family_ids (path traversal protection)
            continue

        # Get all messages for this family, ordered by created_at ASC
        messages_result = conn.execute(
            sa.text(
                "SELECT id, role, content, created_at FROM ai_chat_messages "
                "WHERE family_id = :family_id ORDER BY created_at ASC"
            ),
            {"family_id": family_id},
        )
        messages = list(messages_result)

        if not messages:
            continue

        # Create JSONL file
        session_id = str(uuid.uuid4())
        jsonl_path_relative = f"{family_id}/legacy_{family_id}.jsonl"
        family_dir = Path(chat_dir) / family_id
        family_dir.mkdir(parents=True, exist_ok=True)
        jsonl_file = family_dir / f"legacy_{family_id}.jsonl"

        # Write messages to JSONL
        last_preview = None
        message_count = 0
        with open(jsonl_file, "w", encoding="utf-8") as f:
            for msg in messages:
                msg_id, role, content, created_at = msg[0], msg[1], msg[2], msg[3]
                # Normalize timestamp
                if isinstance(created_at, datetime):
                    timestamp = created_at.isoformat() + "Z"
                else:
                    timestamp = str(created_at)
                line = json.dumps({
                    "message_id": msg_id,
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                }, ensure_ascii=False) + "\n"
                f.write(line)
                message_count += 1
                if role == "assistant":
                    last_preview = content[:100]

        # Compute SHA256 and file size
        sha256 = _compute_sha256(jsonl_file)
        size_bytes = jsonl_file.stat().st_size
        local_path = str(jsonl_file.resolve())
        date_dir = datetime.now().strftime("%Y%m%d")
        now = datetime.utcnow()

        # Insert CachedFile row (user_id is NULL for legacy sessions — no single owner)
        cached_file_id = str(uuid.uuid4())
        conn.execute(
            sa.text(
                "INSERT INTO cached_files "
                "(id, family_id, user_id, sha256, local_path, original_filename, "
                "mime_type, size_bytes, date_dir, created_at) "
                "VALUES (:id, :family_id, :user_id, :sha256, :local_path, "
                ":original_filename, :mime_type, :size_bytes, :date_dir, :created_at)"
            ),
            {
                "id": cached_file_id,
                "family_id": family_id,
                "user_id": None,
                "sha256": sha256,
                "local_path": local_path,
                "original_filename": f"legacy_{family_id}.jsonl",
                "mime_type": "application/x-ndjson",
                "size_bytes": size_bytes,
                "date_dir": date_dir,
                "created_at": now,
            },
        )

        # Insert AIChatSession row
        conn.execute(
            sa.text(
                "INSERT INTO ai_chat_sessions "
                "(id, family_id, user_id, cached_file_id, jsonl_path, "
                "message_count, last_preview, created_at, updated_at) "
                "VALUES (:id, :family_id, :user_id, :cached_file_id, :jsonl_path, "
                ":message_count, :last_preview, :created_at, :updated_at)"
            ),
            {
                "id": session_id,
                "family_id": family_id,
                "user_id": None,
                "cached_file_id": cached_file_id,
                "jsonl_path": jsonl_path_relative,
                "message_count": message_count,
                "last_preview": last_preview,
                "created_at": now,
                "updated_at": now,
            },
        )

    # NOTE: ai_chat_messages rows are NOT deleted — kept for rollback safety.


def downgrade() -> None:
    conn = op.get_bind()
    chat_dir = _get_chat_dir()

    # Delete all AIChatSession rows
    conn.execute(sa.text("DELETE FROM ai_chat_sessions"))

    # Delete all CachedFile rows for JSONL chat files
    conn.execute(
        sa.text("DELETE FROM cached_files WHERE mime_type = 'application/x-ndjson'")
    )

    # Delete all JSONL files in CHAT_DIR
    chat_path = Path(chat_dir)
    if chat_path.exists():
        for jsonl_file in chat_path.rglob("*.jsonl"):
            try:
                jsonl_file.unlink()
            except OSError:
                pass
        # Remove empty family directories
        for family_dir in chat_path.iterdir():
            if family_dir.is_dir():
                try:
                    family_dir.rmdir()
                except OSError:
                    pass  # Not empty — leave it
