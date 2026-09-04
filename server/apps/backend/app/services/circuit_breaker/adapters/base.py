"""Abstract base class for circuit breaker adapters."""

from abc import ABC, abstractmethod
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig
from apps.backend.app.services.circuit_breaker.fsm import CircuitBreakerFSM, Transition
from apps.backend.app.services.circuit_breaker.types import FailureKind


class CircuitBreakerAdapter(ABC):
    """Base adapter: translates entity-specific operations into FSM calls + persistence.

    Subclasses provide: entity lookup, field mapping, side effects, and
    (optionally) override methods for entity-specific behavior.
    """

    @abstractmethod
    def get_config(self) -> CircuitBreakerConfig:
        """Return the behavioral config for this circuit."""
        ...

    @abstractmethod
    def load_entity(self, db: Session) -> object:
        """Load the entity from DB (with_for_update for locking).

        Returns None if entity not found.
        """
        ...

    @abstractmethod
    def persist(self, db: Session) -> None:
        """Commit changes to DB."""
        ...

    def on_transition(self, transition: Transition, db: Session) -> None:
        """Hook for side effects (e.g., ASR setting is_active=False).

        Called after a state transition occurs. Default: no-op.
        Override in subclasses for entity-specific side effects.
        """
        del transition, db  # unused in base class

    # ── Entity binding (avoids redundant DB query) ──

    @abstractmethod
    def bind(self, entity: object) -> None:
        """Bind a pre-loaded entity to avoid a redundant DB query.

        Call this when the caller already has the entity object (e.g., from a
        list query) to skip the load_entity() round-trip.
        """
        ...

    # ── Public API (same for all adapters) ──

    def record_failure(self, failure_type: str, db: Session) -> dict:
        """Record a failure event.

        Args:
            failure_type: One of the FailureKind enum values.
            db: SQLAlchemy session.

        Returns:
            Status dict with circuit_state, circuit_reason, failure_count.
        """
        entity = self.load_entity(db)
        if entity is None:
            return {
                "circuit_state": "closed",
                "circuit_reason": None,
                "failure_count": 0,
            }

        config = self.get_config()
        transition = CircuitBreakerFSM.record_failure(
            entity,
            FailureKind(failure_type),
            config,
            datetime.now(UTC),
        )

        if transition.changed:
            self.on_transition(transition, db)
        self.persist(db)
        return self._status(entity)

    def record_success(self, db: Session) -> dict:
        """Record a success event.

        Returns:
            Status dict with circuit_state, circuit_reason, failure_count.
        """
        entity = self.load_entity(db)
        if entity is None:
            return {
                "circuit_state": "closed",
                "circuit_reason": None,
                "failure_count": 0,
            }

        config = self.get_config()
        transition = CircuitBreakerFSM.record_success(
            entity, config, datetime.now(UTC)
        )

        if transition.changed:
            self.on_transition(transition, db)
        self.persist(db)
        return self._status(entity)

    def check_recovery(self, db: Session) -> bool:
        """Check if an open circuit should transition to half_open.

        Returns:
            True if transitioned to half_open, False otherwise.
        """
        entity = self.load_entity(db)
        if entity is None:
            return False

        config = self.get_config()
        transition = CircuitBreakerFSM.attempt_recovery(
            entity, config, datetime.now(UTC)
        )

        if transition.changed:
            self.on_transition(transition, db)
            self.persist(db)
        return transition.changed

    def reset(self, db: Session) -> dict:
        """Manual reset to closed state.

        Returns:
            Status dict with circuit_state, circuit_reason, failure_count.
        """
        entity = self.load_entity(db)
        if entity is None:
            return {
                "circuit_state": "closed",
                "circuit_reason": None,
                "failure_count": 0,
            }

        transition = CircuitBreakerFSM.reset(entity)

        if transition.changed:
            self.on_transition(transition, db)
        self.persist(db)
        return self._status(entity)

    def _status(self, entity: object) -> dict:
        """Return status dict for the entity."""
        return {
            "circuit_state": entity.circuit_state,  # type: ignore[attr-defined]
            "circuit_reason": getattr(entity, "circuit_reason", None),
            "failure_count": entity.failure_count,  # type: ignore[attr-defined]
        }
