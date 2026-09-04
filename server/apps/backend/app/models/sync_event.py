from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class SyncEvent(Base):
    __tablename__ = "sync_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cached_files.id"), nullable=False)
    backend_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("storage_backends.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # upload_started|upload_succeeded|upload_failed|deleted|default_changed
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    __table_args__ = (
        Index("ix_sync_events_file_id", "file_id"),
        Index("ix_sync_events_backend_occurred", "backend_id", "occurred_at"),
    )
