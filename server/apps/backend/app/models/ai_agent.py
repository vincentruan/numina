from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from apps.backend.app.database import Base
from packages.db.snowflake import next_id


class AIAgent(Base):
    __tablename__ = "ai_agents"
    __table_args__ = (
        UniqueConstraint("family_id", "agent_name", name="uq_ai_agents_family_name"),
        CheckConstraint("agent_name ~ '^[a-z][a-z0-9_-]*$'", name="ck_ai_agents_name_format"),
    )

    id = Column(BigInteger, primary_key=True, default=next_id)
    family_id = Column(BigInteger, nullable=False, index=True)
    agent_name = Column(String(64), nullable=False)
    display_name = Column(String(128), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(16), nullable=True)
    color = Column(String(16), nullable=True)

    soul_md = Column(Text, nullable=False)
    skills = Column(JSONB, nullable=True)
    model = Column(String(64), nullable=True)
    subagent_enabled = Column(Boolean, nullable=False, default=False)
    tool_groups = Column(JSONB, nullable=True)

    is_builtin = Column(Boolean, nullable=False, default=False)
    is_enabled = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_by = Column(BigInteger, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
