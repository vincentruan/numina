from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


class Wish(Base):
    __tablename__ = "wishes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/realized/cancelled
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    converts_to_asset: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wishes")
    category = relationship("Category")
    realized_asset = relationship("Asset")
