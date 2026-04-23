from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.snowflake import next_id


class BlindBoxDraw(Base):
    __tablename__ = "blind_box_draws"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_fulfillment', 'fulfilled')",
            name="ck_blind_box_draw_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    coins_spent: Mapped[int] = mapped_column(Integer, nullable=False)
    gift_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("blind_box_gifts.id"), nullable=False)
    is_surprise: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_bonus: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_fulfillment")
    draw_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
