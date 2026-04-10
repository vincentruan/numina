from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    family_id: Mapped[str] = mapped_column(String(36), ForeignKey("families.id"), nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#4F46E5")
    role: Mapped[str] = mapped_column(String(10), default="member")  # 'owner' or 'member'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # User settings
    theme: Mapped[str] = mapped_column(String(20), default="light")  # 'light' or 'dark'
    language: Mapped[str] = mapped_column(String(10), default="zh-CN")  # 'zh-CN' or 'en-US'
    default_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    view_mode: Mapped[str] = mapped_column(String(20), default="card")  # 'card' or 'list'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # AI 功能
    ai_chat_last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    family = relationship("Family", back_populates="members")
    assets = relationship("Asset", back_populates="user")
    liabilities = relationship("Liability", back_populates="user")
    wishes = relationship("Wish", back_populates="user")
