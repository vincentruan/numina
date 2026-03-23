import random
import string
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Family(Base):
    __tablename__ = "families"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True, default=generate_invite_code)
    created_by: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
