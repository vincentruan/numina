"""Preset learning path — curriculum-aligned path template."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class PresetLearningPath(Base):
    """A preset learning path template generated from curriculum standards.

    Preset paths are system-generated templates that parents can assign to children.
    They group topics by grade, semester, and subject, with topics topologically sorted
    by prerequisite dependencies.
    """

    __tablename__ = "preset_learning_paths"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    grade: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    semester: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    topic_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    topic_count: Mapped[int] = mapped_column(Integer, nullable=False)
    age_group: Mapped[str] = mapped_column(String(10), nullable=False)
    source_taxonomy: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )
