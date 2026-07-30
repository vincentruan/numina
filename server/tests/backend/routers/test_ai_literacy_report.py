"""Tests for literacy report HTTP routers (Task 7).

Covers:
- GET /api/v1/literacy-reports/status  (literacy_parent router)
- POST /api/v1/ai/literacy-report/generate  (ai_literacy_report router)
"""
from __future__ import annotations

import json
from datetime import date
from unittest.mock import AsyncMock, patch

from apps.backend.app.models.literacy_report import LiteracyWeeklyReport
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parent_token(client) -> tuple[dict, int]:
    """Register a parent and return (auth_headers, family_id)."""
    resp = client.post("/api/v1/auth/register", json={
        "username": "lr7_parent",
        "display_name": "LR7 Parent",
        "password": "LR7Pass123",
        "family_name": "LR7 Family",
        "family_invitation_code": "AUTO-TEST",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    me = client.get("/api/v1/auth/me", headers=headers)
    family_id = int(me.json()["data"]["family_id"])
    return headers, family_id


def _make_child(db, family_id: int, username: str = "lr7_child") -> User:
    """Create a child user directly via ORM."""
    child = User(
        id=next_id(),
        username=username,
        display_name="LR7 小孩",
        password_hash="test_hash",
        family_id=family_id,
        role="child",
        birthday=date(2018, 6, 15),
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


def _enable_ai(db, family_id: int):
    """Enable AI for the family by creating an active AIProviderConfig."""
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

    cfg = AIProviderConfig(
        family_id=family_id,
        name="LR7 AI Config",
        provider="anthropic",
        api_key_encrypted="test_encrypted_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(cfg)
    db.commit()


# ---------------------------------------------------------------------------
# GET /literacy-reports/status
# ---------------------------------------------------------------------------


class TestGetReportStatus:
    def test_status_none_when_no_report(self, client, db):
        """Returns status='none' when no report exists for the current week."""
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        resp = client.get(
            f"/api/v1/literacy-reports/status?child_id={child.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "none"

    def test_status_ready_when_report_exists(self, client, db):
        """Returns status='ready' with preview when a report exists."""
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({"signals": {}}),
            narrative="本周表现不错，继续加油！",
            thread_id="test-thread-123",
        )
        db.add(report)
        db.commit()

        resp = client.get(
            f"/api/v1/literacy-reports/status?child_id={child.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ready"
        assert data["thread_id"] == "test-thread-123"
        assert data["week_start"] == ws.isoformat()
        assert "本周表现不错" in data["narrative"]

    def test_status_cross_family_rejected(self, client, db):
        """A parent cannot check status of another family's child."""
        headers, _ = _make_parent_token(client)
        fake_child_id = 999999

        resp = client.get(
            f"/api/v1/literacy-reports/status?child_id={fake_child_id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_status_invalid_child_id(self, client, db):
        """Invalid child_id format returns 422."""
        headers, _ = _make_parent_token(client)

        resp = client.get(
            "/api/v1/literacy-reports/status?child_id=not_a_number",
            headers=headers,
        )
        assert resp.status_code == 422

    def test_status_unauthenticated(self, client):
        """Unauthenticated requests are rejected."""
        resp = client.get("/api/v1/literacy-reports/status?child_id=123")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /ai/literacy-report/generate
# ---------------------------------------------------------------------------


class TestTriggerGenerate:
    def test_generate_returns_cached_status(self, client, db):
        """When a report already exists and force=false, return cached status."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({}),
            narrative="已缓存的报告内容",
            thread_id="cached-thread",
        )
        db.add(report)
        db.commit()

        resp = client.post(
            f"/api/v1/ai/literacy-report/generate?child_id={child.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ready"
        assert data["thread_id"] == "cached-thread"

    def test_generate_validates_child_in_family(self, client, db):
        """Trigger with a child from another family returns 404."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)

        fake_child_id = 999999
        resp = client.post(
            f"/api/v1/ai/literacy-report/generate?child_id={fake_child_id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_generate_invalid_child_id(self, client, db):
        """Invalid child_id format returns 422."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)

        resp = client.post(
            "/api/v1/ai/literacy-report/generate?child_id=abc",
            headers=headers,
        )
        assert resp.status_code == 422

    def test_generate_calls_agent_when_no_cache(self, client, db):
        """When no cached report exists, the agent is called."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        mock_report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({}),
            narrative="Agent 生成的报告",
            thread_id="agent-thread-456",
        )

        with patch(
            "apps.backend.app.routers.ai_literacy_report.generate_literacy_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ):
            resp = client.post(
                f"/api/v1/ai/literacy-report/generate?child_id={child.id}",
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ready"
        assert data["thread_id"] == "agent-thread-456"

    def test_generate_returns_error_on_agent_failure(self, client, db):
        """When agent returns None, status='error' is returned."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)
        child = _make_child(db, family_id)

        with patch(
            "apps.backend.app.routers.ai_literacy_report.generate_literacy_report",
            new_callable=AsyncMock,
            return_value=None,
        ):
            resp = client.post(
                f"/api/v1/ai/literacy-report/generate?child_id={child.id}",
                headers=headers,
            )

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "error"
        assert data["thread_id"] is None

    def test_generate_requires_ai_enabled(self, client, db):
        """When AI is not enabled, the endpoint returns an error."""
        headers, family_id = _make_parent_token(client)
        # Do NOT call _enable_ai
        child = _make_child(db, family_id)

        resp = client.post(
            f"/api/v1/ai/literacy-report/generate?child_id={child.id}",
            headers=headers,
        )
        # AI_NOT_ENABLED → 403
        assert resp.status_code == 403

    def test_generate_unauthenticated(self, client):
        """Unauthenticated requests are rejected."""
        resp = client.post("/api/v1/ai/literacy-report/generate?child_id=123")
        assert resp.status_code == 401

    def test_generate_force_true_calls_agent(self, client, db):
        """force=true bypasses the idempotency cache and calls the agent."""
        headers, family_id = _make_parent_token(client)
        _enable_ai(db, family_id)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({}),
            narrative="cached narrative",
            thread_id="cached-thread",
        )
        db.add(report)
        db.commit()

        mock_report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({}),
            narrative="fresh narrative",
            thread_id="fresh-thread",
        )

        with patch(
            "apps.backend.app.routers.ai_literacy_report.generate_literacy_report",
            new_callable=AsyncMock,
            return_value=mock_report,
        ) as mock_gen:
            resp = client.post(
                f"/api/v1/ai/literacy-report/generate?child_id={child.id}&force=true",
                headers=headers,
            )

        assert resp.status_code == 200
        # Verify force=True was passed through to the service
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args
        assert call_kwargs.kwargs.get("force") is True
