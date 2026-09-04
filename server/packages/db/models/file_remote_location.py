from datetime import datetime

from sqlalchemy import (
    BigInteger,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class FileRemoteLocation(Base):
    __tablename__ = "file_remote_locations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    file_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("cached_files.id"), nullable=False)
    backend_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("storage_backends.id"), nullable=True)
    remote_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    remote_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    remote_sha: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    synced_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    cached_file = relationship("CachedFile", back_populates="remote_locations")
    backend = relationship("StorageBackend", back_populates="remote_locations")

    __table_args__ = (
        UniqueConstraint("file_id", "backend_id", name="uq_file_remote_locations_file_backend"),
        Index("ix_file_remote_locations_file_id", "file_id"),
        Index("ix_file_remote_locations_backend_status", "backend_id", "sync_status"),
    )
