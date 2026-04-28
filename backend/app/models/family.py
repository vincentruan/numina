import random
import string
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.snowflake import next_id


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

    # AI 功能配置
    ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_provider: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 'anthropic' | 'openai'
    ai_api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # AES-256 Fernet 加密
    ai_base_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # 自定义 API Base URL，NULL 表示使用默认端点
    ai_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 主模型 ID，NULL 使用 provider 默认
    ai_vision_model_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 图像模型 ID，NULL 使用主模型

    # AI 测试结果缓存（每次测试连接后更新）
    # 主模型连接测试结果（基本连通性）
    ai_test_connected: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_test_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 主模型thinking测试结果（独立）
    ai_test_thinking_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_test_thinking_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_test_thinking_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_test_thinking_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 图像模型测试结果（独立存储）
    ai_vision_test_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_vision_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_vision_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_vision_test_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 图像模型OCR文本准确度测试结果（独立存储）
    ai_vision_text_test_success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ai_vision_text_test_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_vision_text_test_latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_vision_text_test_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 儿童星星币系统配置
    auto_approve_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)  # 1-168，仅 owner 可修改
    coin_copper_to_silver: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    coin_silver_to_gold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    members = relationship("User", back_populates="family")
    categories = relationship("Category", back_populates="family")
    tags = relationship("Tag", back_populates="family")
    snapshots = relationship("AssetSnapshot", back_populates="family")
    child_bind_tokens = relationship("ChildBindToken", back_populates="family")
