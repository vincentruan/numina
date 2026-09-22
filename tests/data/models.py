"""独立 ORM 模型 — 镜像 backend 真实表结构，不依赖 backend 包。

主键使用 BigInteger（Snowflake ID），由工厂层负责生成。
儿童账号是 role='child' 的 User 行，无独立 child_users 表。
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Table,
    Text,
    Time,
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

    total_approved_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

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


class RentalContract(Base):
    """租约合同 — 镜像 backend rental_contracts 表。

    role='landlord': linked_asset_id 指向出租的房产资产
    role='tenant': linked_asset_id 为 null（承租不关联自有资产）
    end_date 为 null 表示不定期租约
    is_active=False 表示合同已结束（软删除）
    """

    __tablename__ = "rental_contracts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # landlord/tenant
    monthly_rent: Mapped[float] = mapped_column(Float, nullable=False)
    deposit: Mapped[float] = mapped_column(Float, default=0)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    linked_asset_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("assets.id"), nullable=True)
    counterparty: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    linked_asset = relationship("Asset", foreign_keys=[linked_asset_id])


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


# ── Travel module ─────────────────────────────────────────────────────────────

class Trip(Base):
    """家庭旅行 — 镜像 backend trips 表。"""

    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    destination: Mapped[str] = mapped_column(String(200), nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planning")
    planned_budget: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    initial_funding: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    actual_spend: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="CNY")
    wish_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("wishes.id"), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseCategory(Base):
    """支出类别 — 镜像 backend expense_categories 表。"""

    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="label")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ExpenseEntry(Base):
    """费用条目 — 双Entry记账，镜像 backend expense_entries 表。"""

    __tablename__ = "expense_entries"

    __table_args__ = (
        UniqueConstraint("transfer_id", "leg_type", name="uq_expense_transfer_leg"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    transfer_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    leg_type: Mapped[str] = mapped_column(String(10), nullable=False)  # debit/credit
    ref_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ref_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    category_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("expense_categories.id"), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    amount_cny: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    exchange_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    receipt_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    split_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # equal/per_person/custom
    itinerary_item_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("itinerary_items.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class SplitGroup(Base):
    """分摊组 — 镜像 backend split_groups 表。"""

    __tablename__ = "split_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    invite_code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SplitParticipant(Base):
    """分摊参与者 — 镜像 backend split_participants 表。"""

    __tablename__ = "split_participants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("split_groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SplitSettlement(Base):
    """分摊结算 — 镜像 backend split_settlements 表。"""

    __tablename__ = "split_settlements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    from_participant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    to_participant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settled_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TripCoOrganizer(Base):
    """行程共同组织者 — 镜像 backend trip_co_organizers 表。"""

    __tablename__ = "trip_co_organizers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)


class ItineraryItemType(Base):
    """行程项自定义类型 — 家庭范围内可复用。"""

    __tablename__ = "itinerary_item_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="star")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ItineraryItem(Base):
    """行程项 — 按天的旅行计划条目。

    type: accommodation | dining | transport | activity | custom
    type_metadata: JSON 存放类型特有字段
      - accommodation: {"check_in_time": "14:00", "check_out_time": "12:00"}
      - dining: {"diners": 4}
      - transport: {"origin": "...", "destination": "..."}
      - activity: {"ticket_price": "100.00"}
      - custom: 用户自定义
    """

    __tablename__ = "itinerary_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_amount: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    custom_type_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("itinerary_item_types.id"), nullable=True)
    type_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


# ── Manifesto (家庭约定) ─────────────────────────────────────────────────────


class FamilyManifesto(Base):
    __tablename__ = "family_manifesto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    current_version_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    signing_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class ManifestoVersion(Base):
    __tablename__ = "manifesto_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    manifesto_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("family_manifesto.id"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, default="initial")
    trackable_clause_indices: Mapped[list | None] = mapped_column(JSON, nullable=True)
    signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ManifestoSignature(Base):
    __tablename__ = "manifesto_signature"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    version_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("manifesto_version.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    signature_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("version_id", "user_id", name="uq_manifesto_signature_version_user"),
    )
