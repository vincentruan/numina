from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BlindBoxConfig(Base):
    __tablename__ = "blind_box_config"

    __table_args__ = (
        UniqueConstraint("family_id", name="uq_blind_box_config_family"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 免费抽奖触发概率
    base_draw_prob: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)
    special_day_prob: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)

    # 权重算法参数
    weight_scale: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    surprise_threshold_coins: Mapped[int] = mapped_column(Integer, default=200, nullable=False)

    # 超预期惊喜概率
    surprise_prob_normal: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    surprise_prob_parent_bday: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)
    surprise_prob_sibling_bday: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
