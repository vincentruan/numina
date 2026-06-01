# server/apps/backend/app/services/web_search_circuit_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider

TRANSIENT_FAILURE_THRESHOLD = 5
HALF_OPEN_SUCCESS_THRESHOLD = 3


class WebSearchCircuitService:
    @staticmethod
    def report_failure(provider_id: int, failure_type: str, db: Session) -> None:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider:
            return

        provider.last_failure_type = failure_type
        provider.last_failure_at = datetime.now()
        provider.failure_count += 1

        if failure_type.startswith("permanent_"):
            provider.circuit_state = "open"
            provider.circuit_reason = failure_type
        elif provider.failure_count >= TRANSIENT_FAILURE_THRESHOLD:
            provider.circuit_state = "open"
            provider.circuit_reason = failure_type
            provider.recovery_schedule = ":01,:31"

        db.commit()

    @staticmethod
    def report_success(provider_id: int, db: Session) -> None:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider:
            return

        if provider.circuit_state == "half_open":
            provider.half_open_success_count += 1
            if provider.half_open_success_count >= HALF_OPEN_SUCCESS_THRESHOLD:
                provider.circuit_state = "closed"
                provider.circuit_reason = None
                provider.failure_count = 0
                provider.half_open_success_count = 0
                provider.half_open_failure_count = 0
                provider.half_open_window_start = None
                provider.recovery_schedule = None
        elif provider.circuit_state == "closed":
            if provider.failure_count > 0:
                provider.failure_count = max(0, provider.failure_count - 1)

        db.commit()

    @staticmethod
    def check_recovery(provider_id: int, db: Session) -> bool:
        provider = db.query(FamilyWebSearchProvider).filter_by(id=provider_id).first()
        if not provider or provider.circuit_state != "open":
            return False

        if not provider.recovery_schedule:
            return False

        if provider.circuit_reason and provider.circuit_reason.startswith("permanent_"):
            return False

        now = datetime.now()
        if provider.last_failure_at:
            elapsed = (now - provider.last_failure_at).total_seconds()
            if elapsed < 60:
                return False

        provider.circuit_state = "half_open"
        provider.half_open_success_count = 0
        provider.half_open_failure_count = 0
        provider.half_open_window_start = now
        db.commit()
        return True