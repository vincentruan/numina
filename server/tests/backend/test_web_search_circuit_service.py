# server/tests/backend/test_web_search_circuit_service.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.web_search_circuit_service import WebSearchCircuitService
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def provider(db: Session) -> FamilyWebSearchProvider:
    p = FamilyWebSearchProvider(
        id=next_id(),
        family_id=1001,
        provider_name="tavily",
        api_key_encrypted="encrypted_key",
        is_enabled=True,
        display_order=1,
        max_results=5,
        circuit_state="closed",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_report_transient_failure_increments_count(db: Session, provider: FamilyWebSearchProvider):
    WebSearchCircuitService.report_failure(provider.id, "transient_rate_limit", db)
    db.refresh(provider)
    assert provider.failure_count == 1
    assert provider.circuit_state == "closed"


def test_report_permanent_auth_opens_circuit(db: Session, provider: FamilyWebSearchProvider):
    WebSearchCircuitService.report_failure(provider.id, "permanent_auth", db)
    db.refresh(provider)
    assert provider.circuit_state == "open"
    assert provider.circuit_reason == "permanent_auth"


def test_transient_failures_open_after_threshold(db: Session, provider: FamilyWebSearchProvider):
    for _ in range(5):
        WebSearchCircuitService.report_failure(provider.id, "transient_rate_limit", db)
    db.refresh(provider)
    assert provider.circuit_state == "open"
    assert provider.circuit_reason == "transient_rate_limit"


def test_half_open_success_closes_circuit(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "half_open"
    provider.half_open_success_count = 0
    provider.half_open_window_start = datetime.now(UTC).replace(tzinfo=None)
    db.commit()

    WebSearchCircuitService.report_success(provider.id, db)
    db.refresh(provider)
    assert provider.half_open_success_count == 1


def test_half_open_three_successes_closes(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "half_open"
    provider.half_open_success_count = 2
    provider.half_open_window_start = datetime.now(UTC).replace(tzinfo=None)
    db.commit()

    WebSearchCircuitService.report_success(provider.id, db)
    db.refresh(provider)
    assert provider.circuit_state == "closed"
    assert provider.failure_count == 0


def test_recovery_schedule_transitions_to_half_open(db: Session, provider: FamilyWebSearchProvider):
    provider.circuit_state = "open"
    provider.circuit_reason = "transient_rate_limit"
    provider.recovery_schedule = ":01,:31"
    provider.last_failure_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=35)
    db.commit()

    result = WebSearchCircuitService.check_recovery(provider.id, db)
    db.refresh(provider)
    assert result is True
    assert provider.circuit_state == "half_open"