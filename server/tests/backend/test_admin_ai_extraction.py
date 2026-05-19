"""Tests for /api/v1/admin/ai-extraction-* endpoints."""

from datetime import datetime, timedelta

from apps.backend.app.models.ai_extraction_audit import AIExtractionAudit
from apps.backend.app.models.ai_extraction_circuit import AIExtractionCircuit
from apps.backend.app.utils.snowflake import next_id


def _seed_audits(db, family_id: int):
    now = datetime.utcnow()
    methods = [
        "regex_html",
        "regex_html",
        "regex_fence",
        "regex_bare",
        "llm_fallback_hit",
        "failed",
    ]
    for i, m in enumerate(methods):
        db.add(
            AIExtractionAudit(
                id=next_id(),
                family_id=family_id,
                capability="alerts",
                method=m,
                extracted_at=now - timedelta(minutes=i),
            )
        )
    # An old record outside the 7-day window
    db.add(
        AIExtractionAudit(
            id=next_id(),
            family_id=family_id,
            capability="alerts",
            method="regex_html",
            extracted_at=now - timedelta(days=10),
        )
    )
    db.commit()


class TestListAudit:
    def test_owner_can_query(self, client, auth_headers, db):
        # auth_headers fixture creates a family with owner role
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_audits(db, user.family_id)

        resp = client.get(
            "/api/v1/admin/ai-extraction-audit?days=7",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        # Default days=7 → exclude the 10-day-old record
        assert body["aggregates"]["total"] == 6
        assert body["aggregates"]["regex_html"] == 2
        assert body["aggregates"]["regex_fence"] == 1
        assert body["aggregates"]["regex_bare"] == 1
        assert body["aggregates"]["llm_fallback_hit"] == 1
        assert body["aggregates"]["failed"] == 1
        assert len(body["rows"]) == 6

    def test_filter_by_family_id(self, client, auth_headers, db):
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_audits(db, user.family_id)
        # Add a record for a different family
        db.add(
            AIExtractionAudit(
                id=next_id(),
                family_id=99999,
                capability="alerts",
                method="regex_html",
                extracted_at=datetime.utcnow(),
            )
        )
        db.commit()

        resp = client.get(
            f"/api/v1/admin/ai-extraction-audit?family_id={user.family_id}&days=7",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert body["aggregates"]["total"] == 6  # only this family

    def test_filter_by_capability(self, client, auth_headers, db):
        from apps.backend.app.models.user import User

        user = db.query(User).filter_by(username="testuser").first()
        _seed_audits(db, user.family_id)
        # Add a different capability
        db.add(
            AIExtractionAudit(
                id=next_id(),
                family_id=user.family_id,
                capability="disposal",
                method="regex_html",
                extracted_at=datetime.utcnow(),
            )
        )
        db.commit()

        resp = client.get(
            "/api/v1/admin/ai-extraction-audit?capability=alerts&days=7",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        body = resp.json()["data"]
        assert body["aggregates"]["total"] == 6
        assert all(r["capability"] == "alerts" for r in body["rows"])

    def test_no_auth_returns_401(self, client):
        resp = client.get("/api/v1/admin/ai-extraction-audit")
        assert resp.status_code == 401


class TestListCircuit:
    def test_returns_only_non_ok(self, client, auth_headers, db):
        # Seed: one ok, one rate_limited, one circuit_open
        db.add(
            AIExtractionCircuit(
                id=next_id(), family_id=1, capability="alerts", state="ok"
            )
        )
        db.add(
            AIExtractionCircuit(
                id=next_id(),
                family_id=2,
                capability="disposal",
                state="rate_limited",
                opened_at=datetime.utcnow(),
                opened_until=datetime.utcnow() + timedelta(minutes=20),
            )
        )
        db.add(
            AIExtractionCircuit(
                id=next_id(),
                family_id=3,
                capability="spending_leak",
                state="circuit_open",
                opened_at=datetime.utcnow(),
            )
        )
        db.commit()

        resp = client.get(
            "/api/v1/admin/ai-extraction-circuit",
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        body = resp.json()["data"]
        assert len(body["rows"]) == 2
        states = {r["state"] for r in body["rows"]}
        assert states == {"rate_limited", "circuit_open"}


class TestResetCircuit:
    def test_reset_existing(self, client, auth_headers, db):
        circuit = AIExtractionCircuit(
            id=next_id(),
            family_id=10,
            capability="alerts",
            state="circuit_open",
            opened_at=datetime.utcnow(),
        )
        db.add(circuit)
        db.commit()

        resp = client.post(
            "/api/v1/admin/ai-extraction-circuit/reset",
            json={"family_id": "10", "capability": "alerts"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["ok"] is True

        db.refresh(circuit)
        assert circuit.state == "ok"
        assert circuit.manually_reset_at is not None
        assert circuit.reset_by_user_id is not None

    def test_reset_creates_when_missing(self, client, auth_headers, db):
        resp = client.post(
            "/api/v1/admin/ai-extraction-circuit/reset",
            json={"family_id": "777", "capability": "disposal"},
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["ok"] is True
        circuit = (
            db.query(AIExtractionCircuit)
            .filter_by(family_id=777, capability="disposal")
            .first()
        )
        assert circuit is not None
        assert circuit.state == "ok"

    def test_reset_missing_field_returns_422(self, client, auth_headers):
        resp = client.post(
            "/api/v1/admin/ai-extraction-circuit/reset",
            json={"family_id": "10"},  # missing capability
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 422

    def test_reset_no_auth_returns_401(self, client):
        resp = client.post(
            "/api/v1/admin/ai-extraction-circuit/reset",
            json={"family_id": "10", "capability": "alerts"},
        )
        assert resp.status_code == 401
