"""Family invitation code model for launch control.

Each code can only be used once to create a family.
Complete audit trail: tracks who used it, when, and for which family.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FamilyInvitationCode(Base):
    """Family creation invitation code for launch control.

    Each code can only be used once to create a family.
    Complete audit trail: tracks who used it, when, and for which family.
    Admins can revoke unused codes to invalidate them.
    """

    __tablename__ = "family_invitation_codes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    code: Mapped[str] = mapped_column(
        String(6), unique=True, nullable=False, index=True
    )
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    used_by_family_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("families.id"), nullable=True
    )
    used_by_username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
