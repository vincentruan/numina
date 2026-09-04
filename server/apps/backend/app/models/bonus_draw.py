from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base, UTCDateTime
from apps.backend.app.utils.snowflake import next_id


class BonusDraw(Base):
    __tablename__ = "bonus_draws"

    __table_args__ = (
        CheckConstraint(
            "status IN ('available', 'used', 'expired')",
            name="ck_bonus_draw_status",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    source_challenge_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("challenge_grants.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available")
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_draw_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("blind_box_draws.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
