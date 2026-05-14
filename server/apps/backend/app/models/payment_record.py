from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    liability_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("liabilities.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
