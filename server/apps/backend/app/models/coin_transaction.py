"""Append-only coin transaction ledger for the child star coin economy."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    # Positive = credit (earn), negative = debit (spend). Integer copper coins.
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # 'chore_earn' | 'wish_spend' | 'parent_grant' | 'gift_sent' | 'gift_received'
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # No FK — application-layer validation only
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # chore_earn: AI-generated; parent_grant: parent-written
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_emoji: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Bonus coins from streak multiplier (actual_amount - base_reward).
    # 0 for non-bonus chore transactions, NULL for non-chore transactions (wish_spend, parent_grant).
    streak_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        # Idempotency: prevent duplicate writes for the same chore/wish
        UniqueConstraint("ref_id", "transaction_type", name="uq_coin_tx_ref_type"),
    )
