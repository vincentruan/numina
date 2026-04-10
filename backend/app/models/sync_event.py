from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    file_id: Mapped[str] = mapped_column(String(36), ForeignKey("cached_files.id"), nullable=False)
    backend_id: Mapped[str | None] = mapped_column(String(100), ForeignKey("storage_backends.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # upload_started|upload_succeeded|upload_failed|deleted|default_changed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    occurred_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("ix_sync_events_file_id", "file_id"),
        Index("ix_sync_events_backend_occurred", "backend_id", "occurred_at"),
    )
