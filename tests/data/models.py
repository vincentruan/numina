"""独立 ORM 模型 — 镜像 backend 真实表结构，不依赖 backend 包。

主键使用 BigInteger（Snowflake ID），由工厂层负责生成。
儿童账号是 role='child' 的 User 行，无独立 child_users 表。
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


# ── Association tables ────────────────────────────────────────────────────────

asset_tags = Table(
    "asset_tags",
    Base.metadata,
    Column("asset_id", BigInteger, ForeignKey("assets.id"), primary_key=True),
    Column("tag_id", BigInteger, ForeignKey("tags.id"), primary_key=True),
)

chore_template_assignees = Table(
    "chore_template_assignees",
    Base.metadata,
    Column("template_id", BigInteger, ForeignKey("chore_templates.id"), primary_key=True),
    Column("child_user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
)


# ── Core models ───────────────────────────────────────────────────────────────

class Family(Base):
    __tablename__ = "families"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    custom_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    members = relationship("User", back_populates="family", foreign_keys="User.family_id")
    categories = relationship("Category", back_populates="family")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    username: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_color: Mapped[str] = mapped_column(String(20), default="#4F46E5")
    role: Mapped[str] = mapped_column(String(10), default="member")  # owner/member/child
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Child-only fields
    pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pin_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Adult second-factor fields
    numeric_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    numeric_pin_fail_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    numeric_pin_locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    second_factor_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    second_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webauthn_credentials: Mapped[str | None] = mapped_column(String, nullable=True)

    # Preferences
    theme: Mapped[str] = mapped_column(String(20), default="light")
    language: Mapped[str] = mapped_column(String(10), default="zh-CN")
    default_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    view_mode: Mapped[str] = mapped_column(String(20), default="card")
    ai_chat_last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    birthday_is_lunar: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    family = relationship("Family", back_populates="members", foreign_keys=[family_id])
    assets = relationship("Asset", back_populates="user")
    liabilities = relationship("Liability", back_populates="user")
    wishes = relationship("Wish", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#6366F1")
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # physical/financial
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    family = relationship("Family", back_populates="categories")
    assets = relationship("Asset", back_populates="category")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    assets = relationship("Asset", secondary=asset_tags, back_populates="tags")


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(20), nullable=False)  # physical/financial
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="in_use")  # in_use/idle/sold/retired
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    maturity_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    warranty_expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_lifespan_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_maintenance_cost: Mapped[float | None] = mapped_column(Float, nullable=True, default=0)
    usage_frequency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    properties: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_daily_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="assets")
    category = relationship("Category", back_populates="assets")
    tags = relationship("Tag", secondary=asset_tags, back_populates="assets")
    linked_liabilities = relationship("Liability", back_populates="linked_asset")


class Liability(Base):
    __tablename__ = "liabilities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    original_amount: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_amount: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_payment: Mapped[float | None] = mapped_column(Float, nullable=True)
    interest_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    institution: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linked_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="liabilities")
    linked_asset = relationship("Asset", back_populates="linked_liabilities")


class Wish(Base):
    __tablename__ = "wishes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")  # low/medium/high
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/realized/cancelled
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("categories.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    converts_to_asset: Mapped[bool] = mapped_column(Boolean, default=True)
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="wishes")
    category = relationship("Category")
    realized_asset = relationship("Asset")


# ── Children / chores / coins ─────────────────────────────────────────────────

class ChildWish(Base):
    __tablename__ = "child_wishes"

    __table_args__ = (
        UniqueConstraint("child_user_id", "name", name="uq_child_wish_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending_review")
    star_coin_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    realized_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    child_user = relationship("User", foreign_keys=[child_user_id])


class ChoreTemplate(Base):
    __tablename__ = "chore_templates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    frequency: Mapped[str] = mapped_column(String(10), nullable=False)  # daily/weekly
    assignment_type: Mapped[str] = mapped_column(String(10), nullable=False)  # assigned/pool
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    assignees = relationship("User", secondary=chore_template_assignees)
    instances = relationship("ChoreInstance", back_populates="template")


class ChoreInstance(Base):
    __tablename__ = "chore_instances"

    __table_args__ = (
        UniqueConstraint("template_id", "child_user_id", "date_bucket", name="uq_chore_instance"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    template_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chore_templates.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    chore_name: Mapped[str] = mapped_column(String(100), nullable=False)
    chore_emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    coin_reward: Mapped[int] = mapped_column(Integer, nullable=False)
    date_bucket: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD or YYYY-Www
    status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    streak_bonus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    submitted_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    template = relationship("ChoreTemplate", back_populates="instances")


class CoinTransaction(Base):
    __tablename__ = "coin_transactions"

    __table_args__ = (
        UniqueConstraint("ref_id", "transaction_type", name="uq_coin_tx_ref_type"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    child_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(20), nullable=False)
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    narrative_emoji: Mapped[str | None] = mapped_column(String(20), nullable=True)
    streak_bonus: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


# ── Blind box ─────────────────────────────────────────────────────────────────

class BlindBoxConfig(Base):
    __tablename__ = "blind_box_config"

    __table_args__ = (
        UniqueConstraint("family_id", name="uq_blind_box_config_family"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    base_draw_prob: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)
    special_day_prob: Mapped[float] = mapped_column(Float, default=0.80, nullable=False)
    weight_scale: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    surprise_threshold_coins: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    surprise_prob_normal: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    surprise_prob_parent_bday: Mapped[float] = mapped_column(Float, default=0.60, nullable=False)
    surprise_prob_sibling_bday: Mapped[float] = mapped_column(Float, default=0.50, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class BlindBoxGift(Base):
    __tablename__ = "blind_box_gifts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)
    value_score: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-10
    source_wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("child_wishes.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
