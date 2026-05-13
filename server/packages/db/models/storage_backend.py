from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.utils.snowflake import next_id
from packages.db.session import Base


class StorageBackend(Base):
    __tablename__ = "storage_backends"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    backend_type: Mapped[str] = mapped_column(String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    remote_locations = relationship("FileRemoteLocation", back_populates="backend")
