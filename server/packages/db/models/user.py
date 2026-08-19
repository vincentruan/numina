from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from packages.core.snowflake import next_id
from packages.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("families.id"), nullable=False
    )
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#4F46E5")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    avatar_token: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    role: Mapped[str] = mapped_column(
        String(10), default="member"
    )  # 'owner', 'member', or 'child'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Child identity fields (NULL for adult accounts)
    pin_hash: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )  # bcrypt hash of 4-emoji PIN
    pin_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # for force-logout

    # Numeric PIN fields (for adult accounts — optional second factor)
    numeric_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numeric_pin_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    numeric_pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Second factor configuration
    second_factor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'numeric_pin' | 'emoji_pin' | 'totp'
    second_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # WebAuthn credentials (JSON array of registered passkeys)
    webauthn_credentials: Mapped[str | None] = mapped_column(
        String, nullable=True
    )  # JSON array: [{"id": "...", "public_key": "...", "sign_count": 0}]
    # User settings
    theme: Mapped[str] = mapped_column(String(20), default="light")  # 'light' or 'dark'
    language: Mapped[str] = mapped_column(
        String(10), default="zh-CN"
    )  # 'zh-CN' or 'en-US'
    default_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    theme_color: Mapped[str | None] = mapped_column(String(20), nullable=True)  # hex color e.g. #007aff
    view_mode: Mapped[str] = mapped_column(
        String(20), default="card"
    )  # 'card' or 'list'
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # AI 功能
    ai_chat_last_read_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # 生日字段（用于盲盒特殊日期判定）
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    birthday_is_lunar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 累计完成任务数（用于里程碑触发）
    total_approved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 用户名修改历史（JSON 数组，存储最近修改时间戳，用于频率限制）
    username_change_history: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of ISO timestamp strings, e.g. ["2026-08-01T10:00:00"]

    family = relationship("Family", back_populates="members")
    assets = relationship("Asset", back_populates="user")
    liabilities = relationship("Liability", back_populates="user")
    wishes = relationship("Wish", back_populates="user")
