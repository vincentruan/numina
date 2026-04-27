# backend/app/models/notification_config.py
from datetime import datetime
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.utils.snowflake import next_id

class NotificationConfig(Base):
    __tablename__ = "notification_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, unique=True, index=True)
    large_purchase_threshold_fixed: Mapped[float | None] = mapped_column(Float, nullable=True)
    large_purchase_threshold_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
