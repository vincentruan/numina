"""WishSavingsLog — source of truth for a wish's saved_amount (Plan B W1).

Each row is one deposit (positive amount) or withdrawal (negative amount).
saved_amount on the parent Wish is a derived cache maintained in-transaction by
the savings CRUD; recompute_saved_amount() reconciles it (CI asserts equality).
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class WishSavingsLog(Base):
    __tablename__ = "wish_savings_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    wish_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("wishes.id"), nullable=False, index=True)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)  # recorder (DELETE authz)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # +deposit / -withdrawal
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
