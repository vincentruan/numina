"""AI 提取熔断状态 — per (family_id, skill_id) 唯一。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIExtractionCircuit(Base):
    __tablename__ = "ai_extraction_circuits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    skill_id: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="ok")
    # state: ok | rate_limited | circuit_open
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    manually_reset_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reset_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("family_id", "skill_id", name="uq_extraction_circuit_family_skill"),
    )
