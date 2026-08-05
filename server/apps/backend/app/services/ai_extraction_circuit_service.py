"""AI 提取熔断服务。

This service delegates to the unified CircuitBreaker FSM via the ExtractionAdapter.
Thresholds and vocabulary are preserved for backward compatibility.
"""

from sqlalchemy.orm import Session

from apps.backend.app.services.circuit_breaker.adapters.extraction import (
    CIRCUIT_OPEN_THRESHOLD,
    RATE_LIMIT_THRESHOLD,
    ExtractionAdapter,
)

# Re-export constants for backward compatibility with tests
__all__ = [
    "AIExtractionCircuitService",
    "CIRCUIT_OPEN_THRESHOLD",
    "RATE_LIMIT_THRESHOLD",
]


class AIExtractionCircuitService:
    """Public API for AI extraction circuit breaker.

    This class maintains backward compatibility with existing callers.
    All logic is delegated to the unified CircuitBreaker FSM.
    """

    @staticmethod
    def is_open(
        family_id: int | str, skill_id: str, db: Session
    ) -> tuple[bool, str | None]:
        """Check if circuit is open (blocking).

        Returns (is_blocked, reason) where reason is "rate_limited" or "circuit_open".
        """
        adapter = ExtractionAdapter(int(family_id), skill_id)
        return adapter.is_open(db)

    @staticmethod
    def evaluate(family_id: int | str, skill_id: str, db: Session) -> str:
        """Evaluate circuit state based on audit table counts.

        Returns new state string.
        """
        adapter = ExtractionAdapter(int(family_id), skill_id)
        return adapter.evaluate(db)

    @staticmethod
    def reset(
        family_id: int | str, skill_id: str, user_id: int | str, db: Session
    ) -> bool:
        """Manual admin reset to ok state."""
        adapter = ExtractionAdapter(int(family_id), skill_id)
        return adapter.reset(int(user_id), db)
