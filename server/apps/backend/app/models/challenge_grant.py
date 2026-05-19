"""ChallengeGrant model for parent-initiated goal challenges."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class ChallengeGrant(Base):
    __tablename__ = "challenge_grants"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'expired', 'cancelled')",
            name="ck_challenge_grant_status",
        ),
        CheckConstraint(
            "target_type IN ('task_count', 'streak_length', 'specific_chore', 'star_earnings')",
            name="ck_challenge_grant_target_type",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    chore_template_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("chore_templates.id"), nullable=True)
    current_progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    message: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    child_user = relationship("User", foreign_keys=[child_user_id])
    chore_template = relationship("ChoreTemplate", foreign_keys=[chore_template_id])