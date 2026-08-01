"""Tests for the parent-facing literacy report router."""
from __future__ import annotations

import json
from datetime import date

from apps.backend.app.models.literacy_report import LiteracyWeeklyReport
from apps.backend.app.models.user import User
from apps.backend.app.utils.snowflake import next_id

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_parent_token(client) -> tuple[dict, int]:
    """Register a parent and return (auth_headers, family_id)."""
    resp = client.post("/api/v1/auth/register", json={
        "username": "rpt_parent",
        "display_name": "Report Parent",
        "password": "ReportPass123",
        "family_name": "Report Family",
        "family_invitation_code": "AUT01",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    headers = {"Authorization": f"Bearer {data['access_token']}"}
    # Get family_id from /auth/me
    me = client.get("/api/v1/auth/me", headers=headers)
    family_id = int(me.json()["data"]["family_id"])
    return headers, family_id


def _make_child(db, family_id: int, username: str = "rchild") -> User:
    """Create a child user directly via ORM."""
    child = User(
        id=next_id(),
        username=username,
        display_name="报告小孩",
        password_hash="test_hash",
        family_id=family_id,
        role="child",
        birthday=date(2018, 6, 15),
    )
    db.add(child)
    db.commit()
    db.refresh(child)
    return child


# ---------------------------------------------------------------------------
# GET /literacy-reports/children
# ---------------------------------------------------------------------------


class TestGetChildren:
    def test_returns_children_list(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        resp = client.get("/api/v1/literacy-reports/children", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "children" in data
        assert len(data["children"]) >= 1
        child_ids = [str(c["child_id"]) for c in data["children"]]
        assert str(child.id) in child_ids

    def test_unauthenticated_rejected(self, client):
        resp = client.get("/api/v1/literacy-reports/children")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /literacy-reports
# ---------------------------------------------------------------------------


class TestGetReport:
    def test_no_report_returns_404(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        resp = client.get(
            f"/api/v1/literacy-reports?child_id={child.id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_returns_existing_report(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({"signals": {}, "age_group": "mid"}),
            narrative="测试周报内容",
        )
        db.add(report)
        db.commit()

        resp = client.get(
            f"/api/v1/literacy-reports?child_id={child.id}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["narrative"] == "测试周报内容"
        assert data["report_json"] == {"signals": {}, "age_group": "mid"}

    def test_with_week_start_param(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({"signals": {}}),
            narrative="特定周报",
        )
        db.add(report)
        db.commit()

        resp = client.get(
            f"/api/v1/literacy-reports?child_id={child.id}&week_start={ws.isoformat()}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["narrative"] == "特定周报"
        assert data["week_start"] == ws.isoformat()

    def test_cross_family_child_rejected(self, client, db):
        """A parent cannot query another family's child."""
        headers, _ = _make_parent_token(client)
        fake_child_id = 999999
        resp = client.get(
            f"/api/v1/literacy-reports?child_id={fake_child_id}",
            headers=headers,
        )
        # Should return 404 (child not found in family)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /literacy-reports/history
# ---------------------------------------------------------------------------


class TestGetHistory:
    def test_returns_weeks(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        resp = client.get(
            f"/api/v1/literacy-reports/history?child_id={child.id}&weeks=4",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "weeks" in data
        assert len(data["weeks"]) == 4
        # No reports exist → all has_report = False
        for w in data["weeks"]:
            assert w["has_report"] is False

    def test_marks_existing_report(self, client, db):
        headers, family_id = _make_parent_token(client)
        child = _make_child(db, family_id)

        from apps.backend.app.services.literacy_report import _sunday_of

        ws = _sunday_of(date.today())
        report = LiteracyWeeklyReport(
            child_id=child.id,
            week_start=ws,
            report_json=json.dumps({}),
            narrative="test",
        )
        db.add(report)
        db.commit()

        resp = client.get(
            f"/api/v1/literacy-reports/history?child_id={child.id}&weeks=4",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        # First week should have report
        assert data["weeks"][0]["has_report"] is True
        assert data["weeks"][0]["week_start"] == ws.isoformat()
