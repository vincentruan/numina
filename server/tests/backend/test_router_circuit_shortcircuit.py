"""Tests for router-level circuit breaker short-circuit (U7).

Verifies that when ai_extraction_circuits.state is rate_limited or circuit_open,
the /refresh/events endpoints return capability.error NDJSON without invoking
the agent or creating a new task.
"""

from datetime import datetime, timedelta

from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.ai_task import AITask


def _seed_circuit(db, family_id: int, capability: str, state: str, ttl_minutes: int | None = None):
    circuit = AIExtractionCircuit(
        id=next_id(),
        family_id=family_id,
        capability=capability,
        state=state,
        opened_at=datetime.utcnow() if state != "ok" else None,
        opened_until=(
            datetime.utcnow() + timedelta(minutes=ttl_minutes)
            if state == "rate_limited" and ttl_minutes is not None
            else None
        ),
    )
    db.add(circuit)
    db.commit()
    return circuit


def _enable_ai_for_family(db, family_id: int):
    """Seed an active AIProviderConfig so require_ai_enabled passes."""
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

    cfg = AIProviderConfig(
        id=next_id(),
        family_id=family_id,
        name="test-provider",
        provider="openai",
        api_key_encrypted="dummy-encrypted",
        model_id="gpt-4o-mini",
        is_active=True,
        display_order=1,
    )
    db.add(cfg)
    db.commit()


def _get_user_family(db):
    from apps.backend.app.models.user import User

    user = db.query(User).filter_by(username="testuser").first()
    return user, user.family_id


class TestAlertsCircuitShortCircuit:
    def test_circuit_open_blocks_request(self, client, auth_headers, db):
        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        _seed_circuit(db, family_id, "alerts", "circuit_open")

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200  # streaming starts even if it's just an error event
        body = resp.text
        assert "capability.error" in body
        assert "circuit_blocked:circuit_open" in body
        # No new AITask was created
        assert db.query(AITask).filter_by(family_id=family_id, capability="alerts").count() == 0

    def test_rate_limited_blocks_request(self, client, auth_headers, db):
        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        _seed_circuit(db, family_id, "alerts", "rate_limited", ttl_minutes=20)

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.text
        assert "capability.error" in body
        assert "circuit_blocked:rate_limited" in body
        assert db.query(AITask).filter_by(family_id=family_id, capability="alerts").count() == 0

    def test_rate_limited_expired_does_not_block(self, client, auth_headers, db, monkeypatch):
        """Expired rate_limited window auto-recovers; request proceeds (and may fail downstream)."""
        from apps.backend.app.routers import _ai_events_helper

        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=family_id,
            capability="alerts",
            state="rate_limited",
            opened_at=datetime.utcnow() - timedelta(minutes=40),
            opened_until=datetime.utcnow() - timedelta(minutes=10),
        )
        db.add(circuit)
        db.commit()

        # Stub the agent stream so we don't need a real backend
        class NoopStream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            async def aiter_lines(self):
                if False:
                    yield ""

        class NoopClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return None

            def stream(self, *a, **k):
                return NoopStream()

        monkeypatch.setattr(_ai_events_helper.httpx, "AsyncClient", lambda **k: NoopClient())

        resp = client.post(
            "/api/v1/ai/asset-alerts/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.text
        # No "circuit_blocked" header — was allowed through
        assert "circuit_blocked" not in body
        # Circuit was auto-recovered to ok
        db.refresh(circuit)
        assert circuit.state == "ok"


class TestDisposalCircuitShortCircuit:
    def test_circuit_open_blocks_disposal(self, client, auth_headers, db):
        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        _seed_circuit(db, family_id, "disposal", "circuit_open")

        resp = client.post(
            "/api/v1/ai/disposal-suggestions/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.text
        assert "capability.error" in body
        assert "circuit_blocked:circuit_open" in body


class TestSpendingLeakCircuitShortCircuit:
    def test_circuit_open_blocks_spending_leak(self, client, auth_headers, db):
        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        _seed_circuit(db, family_id, "spending_leak", "circuit_open")

        resp = client.post(
            "/api/v1/ai/spending-leaks/refresh/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.text
        assert "capability.error" in body
        assert "circuit_blocked:circuit_open" in body


class TestAllocationCircuitShortCircuit:
    def test_circuit_open_blocks_allocation(self, client, auth_headers, db):
        _user, family_id = _get_user_family(db)
        _enable_ai_for_family(db, family_id)
        _seed_circuit(db, family_id, "allocation", "circuit_open")

        # allocation also requires a target to be set
        from apps.backend.app.models.ai_allocation_target import AIAllocationTarget

        target = AIAllocationTarget(
            id=next_id(),
            family_id=family_id,
            category_targets=[{"category": "stocks", "target_pct": 50}],
        )
        db.add(target)
        db.commit()

        resp = client.post(
            "/api/v1/ai/allocation-target/check/events",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.text
        assert "capability.error" in body
        assert "circuit_blocked:circuit_open" in body
