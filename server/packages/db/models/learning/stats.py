"""Child learning stats — cumulative XP, level, streak tracking."""

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ChildLearningStats(Base):
    __tablename__ = "child_learning_stats"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False, index=True
    )
    cumulative_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    learning_streak_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_learning_date: Mapped[datetime | None] = mapped_column(Date(), nullable=True)
    current_zone: Mapped[str] = mapped_column(
        String(10), nullable=False, default="growth"
    )
    onboarding_completed: Mapped[bool] = mapped_column(
        default=False, nullable=False
    )
    xp_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_xp_date: Mapped[date | None] = mapped_column(Date(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )
