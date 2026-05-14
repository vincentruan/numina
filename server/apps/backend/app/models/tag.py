from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.app.database import Base
from apps.backend.app.models.asset import asset_tags
from apps.backend.app.utils.snowflake import next_id


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    family = relationship("Family", back_populates="tags")
    assets = relationship("Asset", secondary=asset_tags, back_populates="tags")
