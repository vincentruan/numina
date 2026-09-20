"""Generic expense entry — debit/credit pair ledger for travel (and future modules)."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Date,
    Float,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ExpenseEntry(Base):
    """费用条目 — 双Entry 记账。

    每笔费用产生两行：一条 debit（支出类别消费）和一条 credit（资金来源）。
    通过 transfer_id 关联。ref_id + ref_type 指向父实体（trip 等）。

    leg_type: 'debit' | 'credit'
    transfer_id: 共享 Snowflake ID，关联 debit+credit 对
    """

    __tablename__ = "expense_entries"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    # Shared Snowflake ID linking debit+credit pair
    transfer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # 'debit' = expense category consumption; 'credit' = funding source
    leg_type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Polymorphic reference to parent entity (trip, rental_contract, etc.)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("expense_categories.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    amount_cny: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    exchange_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        # Prevent duplicate legs per transfer
        UniqueConstraint("transfer_id", "leg_type", name="uq_expense_transfer_leg"),
    )
