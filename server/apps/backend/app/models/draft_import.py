import json
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class DraftImport(Base):
    """Persistent import staging, history, and rollback tracking.

    Each file parse creates a record.  After the user confirms, status moves
    to ``committed`` and ``committed_record_ids`` stores the created Asset /
    Liability IDs (JSON array).  Rollback sets ``status`` to ``rolled_back``
    and soft-deletes the imported records via ``is_archived=True``.
    """

    __tablename__ = "draft_imports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    source_format: Mapped[str] = mapped_column(String(20), nullable=False)  # pdf/png/jpeg/xlsx/csv
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)  # SHA-256
    # JSON-serialized list[dict] — stored as Text for DB portability (SQLite + PostgreSQL).
    # Mirrors Asset.properties pattern (CLAUDE.md §bigint).
    parsed_items: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # JSON-serialized list of committed Asset/Liability IDs (strings for snowflake safety).
    committed_record_ids: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending / committed / rolled_back
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_draft_imports_family_created", "family_id", "created_at"),
    )

    # --- JSON helpers (parsed_items is Text, not a native JSON column) ---

    def get_parsed_items(self) -> list[dict]:
        return json.loads(self.parsed_items) if self.parsed_items else []

    def set_parsed_items(self, items: list[dict]) -> None:
        self.parsed_items = json.dumps(items, ensure_ascii=False)

    def get_committed_record_ids(self) -> list[str]:
        if not self.committed_record_ids:
            return []
        return json.loads(self.committed_record_ids)

    def set_committed_record_ids(self, ids: list[str]) -> None:
        self.committed_record_ids = json.dumps(ids, ensure_ascii=False)
