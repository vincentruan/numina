"""Diagnosis impression model — records each qualified prerequisite backtrace diagnosis."""

from datetime import datetime

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class DiagnosisImpression(Base):
    """One record per qualified weak-prerequisite candidate returned by a diagnosis run.

    Written server-side whenever GET /practice/recommend?diagnosis=true returns
    a qualified candidate. Keyed by child + target topic + recommended topic +
    timestamp; carries the mastery estimate, sample size, and the config/threshold
    version used so SC1/SC2/SC4 denominators can be computed later.
    """

    __tablename__ = "diagnosis_impressions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    target_topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    recommended_topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("learning_topics.id"), nullable=False, index=True
    )
    bkt_mastery: Mapped[float] = mapped_column(Float, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    config_version: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now()
    )

    __table_args__ = (
        Index(
            "ix_diagnosis_impression_child_created",
            "child_id",
            "created_at",
        ),
    )
