from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class FamilyDebtThresholds(Base):
    """W5 (Plan B T8): per-family high-interest-debt thresholds (percentage).

    One row per family. A liability is "high-interest" when its annual
    interest_rate >= its category's threshold (see useDebtWarning composable).
    Owner-only write (spec §5.1 security-lens); all family members read.
    """

    __tablename__ = "family_debt_thresholds"
    __table_args__ = (UniqueConstraint("family_id", name="uq_family_debt_thresholds_family"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Annual interest-rate percentage above which a liability category counts as
    # high-interest. Defaults mirror spec §5.1 (信用卡 12% / 消费贷 10% / 房贷 6%).
    credit_card: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    personal_loan: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    mortgage: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    other: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), onupdate=func.now()
    )
