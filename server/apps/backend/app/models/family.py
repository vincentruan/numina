import random
import string
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


def generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True, default=generate_invite_code)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
