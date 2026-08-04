import random
import string
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base


def generate_invite_code() -> str:
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True, default=generate_invite_code)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    report_auto_generate_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    ai_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
    storage_backend = relationship(
        "StorageBackend",
        back_populates="family",
        uselist=False,
        cascade="all, delete-orphan",
    )
