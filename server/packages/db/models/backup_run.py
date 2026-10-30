from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class BackupRun(Base):
    """One recorded attempt to back a family's data up to remote storage.

    The row outlives the process that wrote it so the consecutive-failure
    counter survives a scheduler restart, and so the API can report the last
    backup date and status without a remote round-trip.
    """

    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    backup_date: Mapped[str] = mapped_column(String(8), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # "success" | "failed"
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False, server_default="0"
    )
    # "scheduled" | "manual"
    trigger_type: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())

    family = relationship("Family", back_populates="backup_runs")
