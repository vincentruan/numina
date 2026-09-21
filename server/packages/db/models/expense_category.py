"""Expense category — family-scoped, not coupled to Asset like Category."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class ExpenseCategory(Base):
    """支出类别 — 餐饮、交通、住宿、活动、购物、杂项。

    与 Category 不同：不耦合 asset_type，专用于支出记账。
    is_system=True 为系统预置类别；family_id=null 为全局默认。
    """

    __tablename__ = "expense_categories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str] = mapped_column(String(50), nullable=False, default="label")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
