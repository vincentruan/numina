from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class BalanceCorrection(Base):
    """Post-creation balance adjustment for a liability.

    NOT used during create_liability (Path 1 decision). Only for manual
    corrections after the liability exists — e.g. user discovers the
    remaining_amount is wrong, or a lender recalculates interest.

    Signed amount: positive increases remaining, negative decreases it.
    """

    __tablename__ = "balance_corrections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    liability_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("liabilities.id"), nullable=False)
    # Money: NUMERIC(18,2) — signed. Positive = increase debt, negative = decrease.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
