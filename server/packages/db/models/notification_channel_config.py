from datetime import datetime

from sqlalchemy import BigInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class NotificationChannelConfig(Base):
    __tablename__ = "notification_channel_configs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
