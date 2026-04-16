from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ChildWish(Base):
    __tablename__ = "child_wishes"

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_review', 'active', 'rejected', 'redemption_requested', 'realized')",
            name="ck_child_wish_status",
        ),
        CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name="ck_child_wish_priority",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    star_coin_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    realized_asset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("assets.id"), nullable=True)
    star_coin_cost_history: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    child_user = relationship("User", foreign_keys=[child_user_id])
    realized_asset = relationship("Asset", foreign_keys=[realized_asset_id])
