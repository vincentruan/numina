from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from apps.backend.app.database import Base
from apps.backend.app.utils.snowflake import next_id


class FamilySkillConfig(Base):
    __tablename__ = "family_skill_configs"
    __table_args__ = (UniqueConstraint("family_id", "capability", name="uq_family_skill"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(50), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # When set, overrides the default prompt from skills/{capability}.md
    custom_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
