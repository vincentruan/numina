"""Tests for AIExtractionCircuitService."""

from datetime import datetime, timedelta

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.services.ai_extraction_circuit_service import (
    AIExtractionCircuitService,
    CIRCUIT_OPEN_THRESHOLD,
    RATE_LIMIT_THRESHOLD,
)
from apps.backend.app.utils.snowflake import next_id


def _insert_fallback_audits(db, family_id, capability, count, minutes_ago_start=0):
    """Insert N llm_fallback_hit audit records spread over time."""
    now = datetime.utcnow()
    for i in range(count):
        audit = AIExtractionAudit(
            id=next_id(),
            family_id=family_id,
            capability=capability,
            method="llm_fallback_hit",
            extracted_at=now - timedelta(minutes=minutes_ago_start + i),
        )
        db.add(audit)
    db.commit()


class TestIsOpen:
    def test_no_record_returns_false(self, db):
        blocked, reason = AIExtractionCircuitService.is_open(1, "alerts", db)
        assert blocked is False
        assert reason is None

    def test_state_ok_returns_false(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="alerts", state="ok"
        )
        db.add(circuit)
        db.commit()
        blocked, reason = AIExtractionCircuitService.is_open(1, "alerts", db)
        assert blocked is False
        assert reason is None

    def test_state_circuit_open_returns_true(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="alerts", state="circuit_open",
            opened_at=datetime.utcnow(),
        )
        db.add(circuit)
        db.commit()
        blocked, reason = AIExtractionCircuitService.is_open(1, "alerts", db)
        assert blocked is True
        assert reason == "circuit_open"

    def test_state_rate_limited_not_expired_returns_true(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="disposal", state="rate_limited",
            opened_at=datetime.utcnow(),
            opened_until=datetime.utcnow() + timedelta(minutes=20),
        )
        db.add(circuit)
        db.commit()
        blocked, reason = AIExtractionCircuitService.is_open(1, "disposal", db)
        assert blocked is True
        assert reason == "rate_limited"

    def test_state_rate_limited_expired_auto_recovers(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="disposal", state="rate_limited",
            opened_at=datetime.utcnow() - timedelta(minutes=40),
            opened_until=datetime.utcnow() - timedelta(minutes=10),
        )
        db.add(circuit)
        db.commit()
        blocked, reason = AIExtractionCircuitService.is_open(1, "disposal", db)
        assert blocked is False
        assert reason is None
        # Verify state was persisted as ok
        row = db.query(AIExtractionCircuit).first()
        assert row.state == "ok"
        assert row.opened_at is None


class TestEvaluate:
    def test_below_thresholds_stays_ok(self, db):
        _insert_fallback_audits(db, 1, "alerts", 4)
        state = AIExtractionCircuitService.evaluate(1, "alerts", db)
        assert state == "ok"

    def test_1h_threshold_triggers_rate_limited(self, db):
        _insert_fallback_audits(db, 1, "alerts", RATE_LIMIT_THRESHOLD)
        state = AIExtractionCircuitService.evaluate(1, "alerts", db)
        assert state == "rate_limited"
        circuit = db.query(AIExtractionCircuit).filter_by(family_id=1, capability="alerts").first()
        assert circuit.opened_until is not None
        assert circuit.opened_until > datetime.utcnow()

    def test_24h_threshold_triggers_circuit_open(self, db):
        _insert_fallback_audits(db, 1, "disposal", CIRCUIT_OPEN_THRESHOLD)
        state = AIExtractionCircuitService.evaluate(1, "disposal", db)
        assert state == "circuit_open"
        circuit = db.query(AIExtractionCircuit).filter_by(family_id=1, capability="disposal").first()
        assert circuit.opened_until is None

    def test_24h_priority_over_1h(self, db):
        # 20 hits in 1h → both thresholds met, circuit_open wins
        _insert_fallback_audits(db, 1, "spending_leak", 20)
        state = AIExtractionCircuitService.evaluate(1, "spending_leak", db)
        assert state == "circuit_open"

    def test_old_audits_outside_window_not_counted(self, db):
        # 10 hits but all > 2h ago → outside 1h window
        _insert_fallback_audits(db, 1, "alerts", 10, minutes_ago_start=121)
        state = AIExtractionCircuitService.evaluate(1, "alerts", db)
        assert state == "ok"

    def test_evaluate_creates_circuit_if_not_exists(self, db):
        _insert_fallback_audits(db, 99, "allocation", 2)
        state = AIExtractionCircuitService.evaluate(99, "allocation", db)
        assert state == "ok"
        circuit = db.query(AIExtractionCircuit).filter_by(family_id=99, capability="allocation").first()
        assert circuit is not None
        assert circuit.state == "ok"

    def test_evaluate_expired_rate_limited_resets_if_below_threshold(self, db):
        # Set up an expired rate_limited state
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="alerts", state="rate_limited",
            opened_at=datetime.utcnow() - timedelta(minutes=40),
            opened_until=datetime.utcnow() - timedelta(minutes=10),
        )
        db.add(circuit)
        db.commit()
        # Only 2 recent hits → below threshold
        _insert_fallback_audits(db, 1, "alerts", 2)
        state = AIExtractionCircuitService.evaluate(1, "alerts", db)
        assert state == "ok"


class TestReset:
    def test_reset_circuit_open(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(), family_id=1, capability="alerts", state="circuit_open",
            opened_at=datetime.utcnow(),
        )
        db.add(circuit)
        db.commit()
        result = AIExtractionCircuitService.reset(1, "alerts", 42, db)
        assert result is True
        row = db.query(AIExtractionCircuit).first()
        assert row.state == "ok"
        assert row.manually_reset_at is not None
        assert row.reset_by_user_id == 42
        assert row.opened_at is None

    def test_reset_creates_record_if_not_exists(self, db):
        result = AIExtractionCircuitService.reset(77, "disposal", 10, db)
        assert result is True
        row = db.query(AIExtractionCircuit).filter_by(family_id=77, capability="disposal").first()
        assert row is not None
        assert row.state == "ok"
        assert row.reset_by_user_id == 10
