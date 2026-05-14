from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id

asset_tags = Table(
    "asset_tags",
    Base.metadata,
    Column("asset_id", BigInteger, ForeignKey("assets.id"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tags.id"), primary_key=True),
)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # 'physical' or 'financial'
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_use")  # in_use/idle/sold/retired
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_lifespan_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_maintenance_cost: Mapped[float | None] = mapped_column(Float, nullable=True, default=0)
    usage_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)  # daily/weekly/monthly/rarely/idle
    properties: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_daily_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="assets")
    category = relationship("Category", back_populates="assets")
    tags = relationship("Tag", secondary=asset_tags, back_populates="assets")
    linked_liabilities = relationship("Liability", back_populates="linked_asset")
