from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base


class StorageBackend(Base):
    __tablename__ = "storage_backends"
    __table_args__ = (
        UniqueConstraint("family_id", name="uq_storage_backends_family_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    # Each family may have at most one remote storage backend.
    # family_id is non-nullable — global backends are no longer supported.
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    backend_type: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    family = relationship("Family", back_populates="storage_backend")
    remote_locations = relationship("FileRemoteLocation", back_populates="backend")
