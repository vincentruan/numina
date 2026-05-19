"""Tests for ai_extraction_audit and ai_extraction_circuit models."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.utils.snowflake import next_id


class TestAIExtractionAudit:
    def test_insert_and_query_basic(self, db):
        audit = AIExtractionAudit(
            id=next_id(),
            family_id=12345,
            capability="alerts",
            task_id="task-abc",
            method="regex_html",
        )
        db.add(audit)
        db.commit()

        rows = db.query(AIExtractionAudit).filter_by(family_id=12345).all()
        assert len(rows) == 1
        assert rows[0].capability == "alerts"
        assert rows[0].method == "regex_html"
        assert rows[0].extracted_at is not None

    def test_query_by_family_capability_time_window(self, db):
        now = datetime.utcnow()
        for i in range(5):
            audit = AIExtractionAudit(
                id=next_id(),
                family_id=99,
                capability="disposal",
                method="llm_fallback_hit",
                extracted_at=now - timedelta(minutes=i * 10),
            )
            db.add(audit)
        db.commit()

        cutoff = now - timedelta(minutes=25)
        rows = (
            db.query(AIExtractionAudit)
            .filter(
                AIExtractionAudit.family_id == 99,
                AIExtractionAudit.capability == "disposal",
                AIExtractionAudit.extracted_at >= cutoff,
            )
            .all()
        )
        assert len(rows) == 3

    def test_optional_fields_nullable(self, db):
        audit = AIExtractionAudit(
            id=next_id(),
            family_id=1,
            capability="spending_leak",
            method="failed",
            error_msg=None,
            answer_excerpt=None,
            task_id=None,
        )
        db.add(audit)
        db.commit()
        assert db.query(AIExtractionAudit).count() == 1

    def test_error_msg_and_excerpt_persisted(self, db):
        audit = AIExtractionAudit(
            id=next_id(),
            family_id=2,
            capability="allocation",
            method="failed",
            error_msg="json decode error",
            answer_excerpt="some redacted text",
        )
        db.add(audit)
        db.commit()
        row = db.query(AIExtractionAudit).first()
        assert row.error_msg == "json decode error"
        assert row.answer_excerpt == "some redacted text"


class TestAIExtractionCircuit:
    def test_insert_and_default_state(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=1,
            capability="alerts",
        )
        db.add(circuit)
        db.commit()
        row = db.query(AIExtractionCircuit).first()
        assert row.state == "ok"
        assert row.last_evaluated_at is not None

    def test_unique_constraint_family_capability(self, db):
        circuit1 = AIExtractionCircuit(
            id=next_id(), family_id=10, capability="disposal"
        )
        db.add(circuit1)
        db.commit()

        circuit2 = AIExtractionCircuit(
            id=next_id(), family_id=10, capability="disposal"
        )
        db.add(circuit2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_state_transitions_persistent(self, db):
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=20,
            capability="spending_leak",
            state="rate_limited",
            opened_at=datetime.utcnow(),
            opened_until=datetime.utcnow() + timedelta(minutes=30),
        )
        db.add(circuit)
        db.commit()
        row = db.query(AIExtractionCircuit).first()
        assert row.state == "rate_limited"
        assert row.opened_until is not None

    def test_manual_reset_fields(self, db):
        now = datetime.utcnow()
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=30,
            capability="allocation",
            state="ok",
            manually_reset_at=now,
            reset_by_user_id=99999,
        )
        db.add(circuit)
        db.commit()
        row = db.query(AIExtractionCircuit).first()
        assert row.manually_reset_at is not None
        assert row.reset_by_user_id == 99999

    def test_different_families_can_share_capability(self, db):
        c1 = AIExtractionCircuit(id=next_id(), family_id=1, capability="alerts")
        c2 = AIExtractionCircuit(id=next_id(), family_id=2, capability="alerts")
        db.add(c1)
        db.add(c2)
        db.commit()
        assert db.query(AIExtractionCircuit).count() == 2
