"""AI 结构化提取审计记录 — 每次 parse 尝试写一条。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class AIExtractionAudit(Base):
    __tablename__ = "ai_extraction_audits"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    # method: regex_html | regex_fence | regex_bare | llm_fallback_hit | failed
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index(
            "ix_ai_extraction_audits_family_capability_time",
            "family_id",
            "capability",
            "extracted_at",
        ),
    )
