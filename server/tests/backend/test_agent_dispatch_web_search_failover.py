# server/tests/backend/test_agent_dispatch_web_search_failover.py
"""Integration test: web search provider failover when primary returns 401."""
from datetime import UTC, datetime, timedelta

import pytest

from apps.backend.app.models.family_web_search_provider import FamilyWebSearchProvider
from apps.backend.app.services.ai_crypto import encrypt_api_key
from apps.backend.app.services.web_search_circuit_service import WebSearchCircuitService
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def family_providers(db):
    """Two providers: tavily (primary) and ddg_search (fallback)."""
    p1 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=2001,
        provider_name="tavily",
        api_key_encrypted=encrypt_api_key("tvly-bad-key"),
        is_enabled=True,
        display_order=1,
        max_results=5,
        circuit_state="closed",
    )
    p2 = FamilyWebSearchProvider(
        id=next_id(),
        family_id=2001,
        provider_name="ddg_search",
        is_enabled=True,
        display_order=2,
        max_results=3,
        circuit_state="closed",
    )
    db.add_all([p1, p2])
    db.commit()
    return p1, p2


def test_circuit_opens_on_permanent_auth_failure(db, family_providers):
    """When tavily returns 401, circuit opens and ddg becomes primary."""
    tavily, ddg = family_providers

    # Simulate permanent auth failure
    WebSearchCircuitService.report_failure(tavily.id, "permanent_auth", db)

    db.refresh(tavily)
    assert tavily.circuit_state == "open"
    assert tavily.circuit_reason == "permanent_auth"

    # Query available providers (simulating what internal API does)
    available = (
        db.query(FamilyWebSearchProvider)
        .filter(
            FamilyWebSearchProvider.family_id == 2001,
            FamilyWebSearchProvider.is_enabled.is_(True),
            FamilyWebSearchProvider.circuit_state != "open",
        )
        .order_by(FamilyWebSearchProvider.display_order)
        .all()
    )
    assert len(available) == 1
    assert available[0].provider_name == "ddg_search"


def test_transient_failures_accumulate_then_open(db, family_providers):
    """5 transient failures open the circuit."""
    tavily, _ = family_providers

    for _ in range(4):
        WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)
        db.refresh(tavily)
        assert tavily.circuit_state == "closed"

    WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)
    db.refresh(tavily)
    assert tavily.circuit_state == "open"


def test_half_open_recovery_flow(db, family_providers):
    """After circuit opens, recovery transitions through half_open to closed."""
    tavily, _ = family_providers

    # Open the circuit
    for _ in range(5):
        WebSearchCircuitService.report_failure(tavily.id, "transient_rate_limit", db)

    db.refresh(tavily)
    assert tavily.circuit_state == "open"

    # Manually set last_failure_at to 61 seconds ago (bypass the 60s wait)
    tavily.last_failure_at = datetime.now(UTC) - timedelta(seconds=61)
    db.commit()

    # Trigger recovery check
    result = WebSearchCircuitService.check_recovery(tavily.id, db)
    assert result is True
    db.refresh(tavily)
    assert tavily.circuit_state == "half_open"

    # 3 successes close it
    for _ in range(3):
        WebSearchCircuitService.report_success(tavily.id, db)

    db.refresh(tavily)
    assert tavily.circuit_state == "closed"
    assert tavily.failure_count == 0