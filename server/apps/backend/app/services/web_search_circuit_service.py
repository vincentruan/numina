# server/apps/backend/app/services/web_search_circuit_service.py
"""Web Search Provider circuit breaker service.

This service delegates to the unified CircuitBreaker FSM via the WebSearchAdapter.
"""

from sqlalchemy.orm import Session

from apps.backend.app.services.circuit_breaker.adapters.web_search import (
    WebSearchAdapter,
)


class WebSearchCircuitService:
    """Public API for web search provider circuit breaker.

    This class maintains backward compatibility with existing callers.
    All logic is delegated to the unified CircuitBreaker FSM.
    """

    @staticmethod
    def report_failure(provider_id: int, failure_type: str, db: Session) -> None:
        """Record a failure event for the provider."""
        adapter = WebSearchAdapter(provider_id)
        adapter.record_failure(failure_type, db)

    @staticmethod
    def report_success(provider_id: int, db: Session) -> None:
        """Record a success event for the provider."""
        adapter = WebSearchAdapter(provider_id)
        adapter.record_success(db)

    @staticmethod
    def check_recovery(provider_id: int, db: Session) -> bool:
        """Check if the provider should transition to half_open.

        Returns True if transitioned to half_open, False otherwise.
        """
        adapter = WebSearchAdapter(provider_id)
        return adapter.check_recovery(db)
