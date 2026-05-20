"""Integration tests for the enhanced three-state circuit breaker.

Covers:
- Error-type-aware circuit logic (permanent vs transient)
- Three-state transitions (closed → open → half_open → closed)
- Recovery schedule matching
- Half-open success/failure tracking
- Manual reset clears all circuit state
"""

from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.utils.snowflake import next_id

_TEST_AGENT_TOKEN = "test-agent-token-for-circuit-breaker"


@pytest.fixture(autouse=True)
def _set_agent_token():
    """Set AGENT_INTERNAL_TOKEN for all tests in this module."""
    with patch("packages.core.settings.settings.AGENT_INTERNAL_TOKEN", _TEST_AGENT_TOKEN):
        yield


def _seed_family(db, family_id: int = 1) -> int:
    """Seed a family record so verify_agent_token can validate the family_id."""
    from packages.db.models.family import Family
    existing = db.query(Family).filter(Family.id == family_id).first()
    if existing:
        return family_id
    family = Family(
        id=family_id,
        name="Test Family",
        invite_code=f"INV{family_id:03d}",
        created_by=family_id,  # Self-reference, no real user needed
    )
    db.add(family)
    db.commit()
    return family_id


def _seed_provider(
    db,
    family_id: int,
    *,
    is_active: bool = True,
    circuit_state: str = "closed",
    circuit_reason: str | None = None,
    recovery_schedule: str | None = None,
    half_open_success_count: int = 0,
    half_open_failure_count: int = 0,
    half_open_window_start: datetime | None = None,
    failure_count: int = 0,
    name: str = "test-provider",
    display_order: int = 1,
) -> AIProviderConfig:
    # Ensure family exists for verify_agent_token validation
    _seed_family(db, family_id)
    # Use real encryption for api_key so decrypt_api_key returns a value
    from apps.backend.app.services.ai_crypto import encrypt_api_key
    encrypted_key = encrypt_api_key("sk-test-key-12345") or "dummy-encrypted"
    cfg = AIProviderConfig(
        id=next_id(),
        family_id=family_id,
        name=name,
        provider="openai",
        api_key_encrypted=encrypted_key,
        model_id="gpt-4o-mini",
        model_1_capabilities='["text_generation"]',
        is_active=is_active,
        display_order=display_order,
        circuit_state=circuit_state,
        circuit_reason=circuit_reason,
        recovery_schedule=recovery_schedule,
        half_open_success_count=half_open_success_count,
        half_open_failure_count=half_open_failure_count,
        half_open_window_start=half_open_window_start,
        failure_count=failure_count,
        # Keep legacy fields synced
        circuit_open=(circuit_state in ("open", "half_open")),
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


def _agent_headers(family_id: int) -> dict:
    """Build agent-internal token headers for backend internal endpoints."""
    return {
        "Authorization": f"Bearer {_TEST_AGENT_TOKEN}",
        "X-Family-Id": str(family_id),
        "Content-Type": "application/json",
    }


class TestCircuitEventHandling:
    """Tests for /internal/ai/config/{config_id}/circuit-event endpoint."""

    def test_permanent_auth_error_opens_circuit_immediately(self, client, db):
        """401/403 errors should open circuit immediately with permanent_auth reason."""
        cfg = _seed_provider(db, family_id=1)

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-event",
            json={"error_code": 401, "error_type": "permanent_auth"},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        data = resp.json()
        body = data.get("data", data)
        assert body["circuit_state"] == "open"
        assert body["circuit_reason"] == "permanent_auth"

        db.refresh(cfg)
        assert cfg.circuit_state == "open"
        assert cfg.circuit_reason == "permanent_auth"
        assert cfg.circuit_open_until is None  # Manual recovery only

    def test_permanent_account_error_opens_circuit_immediately(self, client, db):
        """410 errors should open circuit immediately with permanent_account reason."""
        cfg = _seed_provider(db, family_id=1)

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-event",
            json={"error_code": 410, "error_type": "permanent_account"},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.circuit_state == "open"
        assert cfg.circuit_reason == "permanent_account"

    def test_transient_error_increments_failure_count(self, client, db):
        """Transient error should increment failure_count, not immediately open circuit."""
        cfg = _seed_provider(db, family_id=1)

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-event",
            json={"error_code": 429, "error_type": "transient_rate_limit"},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.failure_count == 1
        assert cfg.circuit_state == "closed"  # Below threshold

    def test_transient_error_threshold_opens_circuit(self, client, db):
        """5 transient failures should open circuit with transient reason."""
        cfg = _seed_provider(db, family_id=1, failure_count=4)

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-event",
            json={"error_code": 500, "error_type": "transient_server"},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.circuit_state == "open"
        assert cfg.circuit_reason == "transient"
        assert cfg.circuit_open_until is not None  # Has scheduled recovery

    def test_invalid_error_type_rejected(self, client, db):
        """Invalid error_type values should be rejected with 422."""
        cfg = _seed_provider(db, family_id=1)

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-event",
            json={"error_code": 500, "error_type": "made_up_type"},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 422  # Pydantic validation


class TestCircuitReset:
    """Tests for circuit reset endpoint clearing all new fields."""

    def test_reset_clears_all_circuit_state(self, client, db):
        """Reset should clear all three-state circuit fields."""
        cfg = _seed_provider(
            db,
            family_id=1,
            circuit_state="open",
            circuit_reason="permanent_auth",
            half_open_success_count=2,
            half_open_failure_count=1,
            half_open_window_start=datetime.now(UTC).replace(tzinfo=None),
            failure_count=10,
        )

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/circuit-reset",
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.circuit_state == "closed"
        assert cfg.circuit_reason is None
        assert cfg.failure_count == 0
        assert cfg.circuit_open is False
        assert cfg.last_failure_type is None
        assert cfg.half_open_success_count == 0
        assert cfg.half_open_failure_count == 0
        assert cfg.half_open_window_start is None


class TestProviderListWithCircuitMetadata:
    """Tests for /internal/ai/config returning circuit metadata."""

    def test_open_provider_excluded_from_list(self, client, db):
        """Open providers (without recovery match) should not appear in list."""
        _seed_provider(
            db,
            family_id=1,
            circuit_state="open",
            circuit_reason="permanent_auth",
            name="open-provider",
        )

        resp = client.get(
            "/api/v1/internal/ai/config",
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["ai_enabled"] is False
        assert data["providers"] == []

    def test_closed_provider_included_with_metadata(self, client, db):
        """Closed providers should appear with circuit metadata."""
        _seed_provider(
            db,
            family_id=1,
            circuit_state="closed",
            recovery_schedule=":01,:31",
            name="healthy-provider",
        )

        with patch("apps.backend.app.routers.ai_internal.decrypt_api_key", return_value="sk-test-key"):
            resp = client.get(
                "/api/v1/internal/ai/config",
                headers=_agent_headers(1),
            )

        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        providers = data["providers"]
        assert len(providers) == 1
        assert providers[0]["circuit_state"] == "closed"
        assert providers[0]["recovery_schedule"] == ":01,:31"


class TestHalfOpenResultEndpoint:
    """Tests for /internal/ai/config/{config_id}/half-open-result endpoint."""

    def test_success_increments_count(self, client, db):
        """Success during half-open should increment success count."""
        cfg = _seed_provider(
            db,
            family_id=1,
            circuit_state="half_open",
            half_open_window_start=datetime.now(UTC).replace(tzinfo=None),
        )

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/half-open-result",
            json={"success": True},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.half_open_success_count == 1
        assert cfg.circuit_state == "half_open"  # Still half_open until window expires

    def test_failure_reopens_circuit(self, client, db):
        """Failure during half-open should immediately re-open circuit."""
        cfg = _seed_provider(
            db,
            family_id=1,
            circuit_state="half_open",
            half_open_window_start=datetime.now(UTC).replace(tzinfo=None),
        )

        resp = client.post(
            f"/api/v1/internal/ai/config/{cfg.id}/half-open-result",
            json={"success": False},
            headers=_agent_headers(1),
        )

        assert resp.status_code == 200
        db.refresh(cfg)
        assert cfg.half_open_failure_count == 1
        assert cfg.circuit_state == "open"
        assert cfg.circuit_reason == "transient"


class TestRecoveryScheduleHelper:
    """Tests for recovery schedule pattern matching."""

    def test_pattern_matches_minute_suffix(self):
        from apps.backend.app.routers.ai_internal import _check_recovery_schedule_match

        # Mock current time at minute :01
        now = datetime(2026, 5, 20, 14, 1, 0)
        assert _check_recovery_schedule_match(":01,:31", now) is True
        assert _check_recovery_schedule_match(":31", now) is False
        assert _check_recovery_schedule_match(None, now) is False

    def test_pattern_matches_minute_31(self):
        from apps.backend.app.routers.ai_internal import _check_recovery_schedule_match

        now = datetime(2026, 5, 20, 14, 31, 0)
        assert _check_recovery_schedule_match(":01,:31", now) is True


class TestErrorClassification:
    """Tests for agent-side error classification."""

    def test_401_classified_as_permanent_auth(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(401) == "permanent_auth"

    def test_403_classified_as_permanent_auth(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(403) == "permanent_auth"

    def test_410_classified_as_permanent_account(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(410) == "permanent_account"

    def test_429_classified_as_transient_rate_limit(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(429) == "transient_rate_limit"

    def test_500_classified_as_transient_server(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(500) == "transient_server"

    def test_503_classified_as_transient_server(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(503) == "transient_server"

    def test_zero_classified_as_transient_timeout(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(0) == "transient_timeout"

    def test_account_message_classified_as_permanent_account(self):
        from apps.agent.core.backend_client import classify_error_type
        assert classify_error_type(500, "account suspended") == "permanent_account"
