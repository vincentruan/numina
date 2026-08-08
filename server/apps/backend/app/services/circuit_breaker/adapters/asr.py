"""ASR Provider circuit breaker adapter.

Inherits CircuitBreakerAdapter for the ``on_transition`` hook and ``bind``
interface, but uses a simpler two-state model (no half_open) with custom
record_failure/record_success logic — does NOT delegate to CircuitBreakerFSM.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.app.models.asr_provider_config import ASRProviderConfig
from apps.backend.app.services.circuit_breaker.adapters.base import (
    CircuitBreakerAdapter,
)
from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.fsm import Transition

# ASR uses a simpler two-state model with threshold=3
_CIRCUIT_FAILURE_THRESHOLD = 3


class ASRAdapter(CircuitBreakerAdapter):
    """Adapter for ASRProviderConfig entity.

    ASR uses a simpler two-state model (no half_open):
    - failure_count >= 3 -> open + is_active=False
    - test pass or transcribe success -> closed + failure_count=0

    Note: ASRProviderConfig lacks the full FSM protocol fields
    (circuit_reason, last_failure_type, half_open_*) so record_failure and
    record_success are intentionally custom rather than delegating to the
    base class / FSM. The on_transition hook still handles the is_active
    side effect for consistency with other adapters.
    """

    def __init__(self, config_id: int) -> None:
        self._config_id = config_id
        self._config: ASRProviderConfig | None = None

    def bind(self, entity: object) -> None:
        """Bind a pre-loaded ASRProviderConfig to skip the DB query."""
        self._config = entity  # type: ignore[assignment]

    def get_config(self) -> CircuitBreakerConfig:
        """Return config matching ASR behavior."""
        return CircuitBreakerConfig(
            transient_failure_threshold=_CIRCUIT_FAILURE_THRESHOLD,
            half_open_success_threshold=1,  # Not used (no half_open)
            recovery_cooldown_seconds=0,  # No auto-recovery
        )

    def load_entity(self, db: Session) -> ASRProviderConfig | None:
        """Load ASR config by ID with row lock."""
        self._config = (
            db.query(ASRProviderConfig)
            .filter(ASRProviderConfig.id == self._config_id)
            .with_for_update()
            .first()
        )
        return self._config

    def persist(self, db: Session) -> None:
        """Commit changes to DB."""
        db.commit()

    def on_transition(self, transition: Transition, db: Session) -> None:
        """Handle ASR-specific side effects.

        When opening: set is_active=False
        When closing from open: clear failure_count
        """
        del db  # unused
        if self._config is None:
            return

        # Transition to open: disable the config
        if transition.new_state.value == "open":
            self._config.is_active = False

    def record_failure(self, db: Session) -> None:  # type: ignore[override]
        """Record a transcription failure.

        ASR doesn't use failure_type - just increments counter.
        Auto-disables after threshold.
        """
        if self._config is None:
            self.load_entity(db)
        if self._config is None:
            return

        self._config.failure_count += 1
        self._config.last_failure_at = datetime.now(UTC).replace(tzinfo=None)

        if self._config.failure_count >= _CIRCUIT_FAILURE_THRESHOLD:
            self._config.circuit_state = "open"
            self._config.is_active = False

        db.commit()

    def record_success(self, db: Session) -> None:  # type: ignore[override]
        """Record a transcription or test success.

        Resets failure counter and closes circuit.
        """
        if self._config is None:
            self.load_entity(db)
        if self._config is None:
            return

        self._config.failure_count = 0
        self._config.circuit_state = "closed"
        db.commit()


def get_first_usable_config(family_id: int, db: Session) -> ASRProviderConfig | None:
    """Find the first active, enabled, circuit-closed ASR config for a family.

    This is a module-level function since it's a query, not an instance method.
    """
    result = db.execute(
        select(ASRProviderConfig)
        .where(
            ASRProviderConfig.family_id == family_id,
            ASRProviderConfig.is_active == True,  # noqa: E712
            ASRProviderConfig.circuit_state != "open",
        )
        .order_by(ASRProviderConfig.display_order.asc().nulls_last())
    )
    return result.scalar_one_or_none()
