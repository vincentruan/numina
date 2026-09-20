"""Split group, participants, and settlement models for shared travel expenses."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


def generate_invite_code() -> str:
    """Generate a 6-char alphanumeric invite code (uppercase + digits)."""
    import random
    import string

    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


class SplitGroup(Base):
    """分摊组 — 一个行程最多一个活跃分摊组。

    invite_code: 6位大写字母+数字，供外部参与者加入
    is_active=False 表示行程取消后失效
    """

    __tablename__ = "split_groups"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    invite_code: Mapped[str] = mapped_column(
        String(6), unique=True, nullable=False, default=generate_invite_code
    )
    created_by_user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class SplitParticipant(Base):
    """分摊参与者 — 外部参与者（自由文本姓名）或共同组织者。

    family_id 非 null 时表示该参与者是某家庭成员（共同组织者）；
    null 表示外部参与者（无系统账户）。
    """

    __tablename__ = "split_participants"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    group_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("split_groups.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    family_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class SplitSettlement(Base):
    """分摊结算 — 债务简化后的转账记录。

    从 from_participant_name 转给 to_participant_name。
    is_complete=True 且 settled_at 在 24 小时内可撤销。
    """

    __tablename__ = "split_settlements"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    from_participant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    to_participant_name: Mapped[str] = mapped_column(String(200), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="CNY")
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    settled_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    settled_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class TripCoOrganizer(Base):
    """行程共同组织者 — 由 organizer 委托的家庭成员。

    共同组织者可添加/修改费用、标记结算完成。最多 3 人。
    """

    __tablename__ = "trip_co_organizers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    trip_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("trips.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
