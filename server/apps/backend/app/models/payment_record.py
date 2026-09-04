from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    liability_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("liabilities.id"), nullable=False)
    # Money: NUMERIC(18,2) — Decimal in Python, str on the wire (money-as-str).
    # Was Float pre-review-followup (silent precision loss on payment history);
    # migrated to Numeric to mirror WishSavingsLog + the liability money fields.
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    paid_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Source: "manual" (user-recorded) or "system" (auto-generated during retroactive creation).
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual", server_default="manual")
