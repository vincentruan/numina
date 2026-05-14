from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class ChildWishCostHistory(Base):
    __tablename__ = "child_wish_cost_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    wish_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_cost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
