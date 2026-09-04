from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class ChildEconomyConfig(Base):
    __tablename__ = "child_economy_configs"
    __table_args__ = (UniqueConstraint("family_id", name="uq_child_economy_config_family"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    auto_approve_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    coin_copper_to_silver: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    coin_silver_to_gold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    # B1 教育联动：family 级 opt-in 开关 + 星币→元汇率（1 星币 = N 元）
    education_reward_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    coin_to_yuan_rate: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", nullable=False
    )
    # 素养徽章联动：family 级 opt-in 开关 + 解锁奖励星币数量
    literacy_badge_coin_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    literacy_badge_coin_amount: Mapped[int] = mapped_column(
        Integer, default=50, server_default="50", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
