import random
import string
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
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

    # AI 功能配置
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'anthropic' | 'openai'
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # AES-256 Fernet 加密
    ai_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # 自定义 API Base URL，NULL 表示使用默认端点
    ai_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 主模型 ID，NULL 使用 provider 默认
    ai_vision_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 图像模型 ID，NULL 使用主模型

    # 儿童星星币系统配置
    auto_approve_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)  # 1-168，仅 owner 可修改

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
    child_bind_tokens = relationship("ChildBindToken", back_populates="family")
