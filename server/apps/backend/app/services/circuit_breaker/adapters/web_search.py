"""Web Search Provider circuit breaker adapter."""

from sqlalchemy.orm import Session

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.circuit_breaker.adapters.base import (
    CircuitBreakerAdapter,
)
from apps.backend.app.services.circuit_breaker.config import CircuitBreakerConfig


class WebSearchAdapter(CircuitBreakerAdapter):
    """Adapter for FamilyWebSearchProvider entity.

    Uses count-based recovery (3 successes) with 60-second cooldown.
    """

    def __init__(self, provider_id: int) -> None:
        self._provider_id = provider_id
        self._provider: FamilyWebSearchProvider | None = None

    def bind(self, entity: object) -> None:
        """Bind a pre-loaded FamilyWebSearchProvider to skip the DB query."""
        self._provider = entity  # type: ignore[assignment]

    def get_config(self) -> CircuitBreakerConfig:
        """Return config matching original WebSearchCircuitService behavior."""
        return CircuitBreakerConfig(
            transient_failure_threshold=5,
            half_open_success_threshold=3,
            recovery_cooldown_seconds=60,
        )

    def load_entity(self, db: Session) -> FamilyWebSearchProvider | None:
        """Load provider with row lock."""
        self._provider = (
            db.query(FamilyWebSearchProvider)
            .filter_by(id=self._provider_id)
            .with_for_update()
            .first()
        )
        return self._provider

    def persist(self, db: Session) -> None:
        """Commit changes to DB."""
        db.commit()
