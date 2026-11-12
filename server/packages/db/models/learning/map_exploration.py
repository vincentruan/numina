"""Knowledge map exploration telemetry (R11, R12).

One row per map visit. Captures how long the child spent on the map before
their first topic selection (R11) and the zoom depth they reached (R12), so
exploration depth is separable from dwell time. A visit that ends with no
topic selection is still recorded (AE4).
"""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from packages.core.snowflake import next_id
from packages.db.session import Base, UTCDateTime


class LearningMapExploration(Base):
    __tablename__ = "learning_map_explorations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    child_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    # Elapsed time between map mount and first topic selection (R11). For a
    # visit with no selection this is the full time on map before leaving.
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Deepest zoom level reached: 0 subject, 1 domain, 2 topic (R12).
    max_zoom_level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    topic_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Total pan/zoom/tap interactions — separates browsing from a drive-by (R12).
    interaction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    selected_topic_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=func.now(), nullable=False, index=True
    )
