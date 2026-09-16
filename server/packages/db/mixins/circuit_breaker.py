"""Circuit breaker column mixin.

Provides the 9 FSM columns shared by AIProviderConfig, FamilyWebSearchProvider,
and ASRProviderConfig.  All three models inherit identical column definitions;
the FSM (``apps.backend.app.services.circuit_breaker.fsm``) operates on any
object exposing these attributes via structural typing.
"""

from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.session import UTCDateTime


class CircuitBreakerMixin:
    """Nine circuit-breaker FSM columns shared across provider models.

    Drop-in compatible with :class:`CircuitBreakerFSM` which reads/writes
    these attributes by name.
    """

    circuit_state: Mapped[str] = mapped_column(
        String(20), default="closed", nullable=False
    )
    circuit_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    recovery_schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_failure_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    half_open_success_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    half_open_failure_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    half_open_window_start: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_failure_at: Mapped[datetime | None] = mapped_column(
        UTCDateTime(), nullable=True
    )
