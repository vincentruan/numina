"""ChildMilestone ORM model."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ChildMilestone(Base):
    __tablename__ = "child_milestones"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    milestone_type: Mapped[str] = mapped_column(String(50), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ref_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
