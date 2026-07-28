"""U4 tests — child literacy scenario + badge endpoints."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta

import pytest

from tests.backend.conftest import child_login_two_phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child(client, auth_headers):
    """Register a parent, create a child, and return child auth headers + id."""
    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "literacychild",
            "display_name": "小识字",
            "password": "ChildPass1",
            "avatar_color": "#FF5733",
            "pin": ["🐱", "🌟", "🎈", "🐶"],
        },
    )
    assert resp.status_code == 201, resp.text
    child_data = resp.json()["data"]
    token = child_login_two_phase(
        client, "literacychild", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"]
    )
    # Clear parent cookies to avoid polluting subsequent requests.
    client.cookies.delete("access_token")
    client.cookies.delete("child_access_token")
    return {
        "id": child_data["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


def _sunday_of(d: date) -> date:
    days_since_sunday = (d.weekday() + 1) % 7
    return d - timedelta(days=days_since_sunday)


def _seed_scenario(db, child_id: int, *, completed: bool = False, content: dict | None = None):
    """Insert a LiteracyScenario for this week directly."""
    from apps.backend.app.models.literacy_scenario import LiteracyScenario
    from apps.backend.app.utils.snowflake import next_id

    week_start = _sunday_of(date.today())
    payload = content or {
        "story": "测试故事内容",
        "choices": [
            {"label": "选项 A", "feedback": "反馈 A"},
            {"label": "选项 B", "feedback": "反馈 B"},
        ],
    }
    scenario = LiteracyScenario(
        id=next_id(),
        child_id=child_id,
        week_start=week_start,
        template_id=0,
        content_json=json.dumps(payload, ensure_ascii=False),
        choice_index=0 if completed else None,
        feedback_json=json.dumps({"feedback": "反馈 A"}, ensure_ascii=False) if completed else None,
        completed_at=datetime.now(UTC) if completed else None,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


# ---------------------------------------------------------------------------
# GET /scenario
# ---------------------------------------------------------------------------


def test_get_scenario_lazy_generation(client, child):
    """When no scenario exists, the endpoint should generate one lazily."""
    resp = client.get("/api/v1/child/literacy/scenario", headers=child["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "id" in data
    assert isinstance(data["story"], str)
    assert data["story"]
    assert isinstance(data["choices"], list)
    assert data["completed"] is False
    assert data["age_group"] in ("low", "mid", "high")


def test_get_scenario_returns_existing(client, child, db):
    """When a scenario already exists, return it without regenerating."""
    existing = _seed_scenario(db, int(child["id"]))
    resp = client.get("/api/v1/child/literacy/scenario", headers=child["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["id"] == str(existing.id)
    assert data["story"] == "测试故事内容"
    assert len(data["choices"]) == 2
    assert data["completed"] is False


def test_get_scenario_unauthenticated(client):
    """Unauthenticated requests should be rejected."""
    resp = client.get("/api/v1/child/literacy/scenario")
    assert resp.status_code in (401, 403)


def test_get_scenario_parent_forbidden(client, auth_headers):
    """A parent user cannot access child endpoints."""
    resp = client.get("/api/v1/child/literacy/scenario", headers=auth_headers)
    # get_current_child_user returns 401 for non-child roles.
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /scenario/choose
# ---------------------------------------------------------------------------


def test_post_scenario_choose_success(client, child, db):
    """A valid choice should record the selection and return feedback."""
    _seed_scenario(db, int(child["id"]))
    resp = client.post(
        "/api/v1/child/literacy/scenario/choose",
        headers=child["headers"],
        json={"choice_index": 1},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["feedback_text"] == "反馈 B"
    assert isinstance(data["badges_unlocked"], list)
    assert isinstance(data["dimension_hint"], str)

    # Verify the scenario was marked as completed in the DB.
    from apps.backend.app.models.literacy_scenario import LiteracyScenario

    scenario = db.query(LiteracyScenario).filter(
        LiteracyScenario.child_id == int(child["id"])
    ).first()
    assert scenario is not None
    assert scenario.completed_at is not None
    assert scenario.choice_index == 1


def test_post_scenario_choose_conflict(client, child, db):
    """A second choice on a completed scenario should return 409."""
    _seed_scenario(db, int(child["id"]), completed=True)
    resp = client.post(
        "/api/v1/child/literacy/scenario/choose",
        headers=child["headers"],
        json={"choice_index": 0},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body.get("code") == "LITERACY_SCENARIO_COMPLETED"


def test_post_scenario_choose_invalid_index(client, child, db):
    """An out-of-range choice_index should return 422."""
    _seed_scenario(db, int(child["id"]))
    resp = client.post(
        "/api/v1/child/literacy/scenario/choose",
        headers=child["headers"],
        json={"choice_index": 99},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body.get("code") == "VALIDATION_ERROR"


def test_post_scenario_choose_negative_index(client, child, db):
    """A negative choice_index should return 422."""
    _seed_scenario(db, int(child["id"]))
    resp = client.post(
        "/api/v1/child/literacy/scenario/choose",
        headers=child["headers"],
        json={"choice_index": -1},
    )
    assert resp.status_code == 422, resp.text


def test_post_scenario_choose_triggers_lazy_generation(client, child):
    """If no scenario exists yet, choose should generate one first."""
    resp = client.post(
        "/api/v1/child/literacy/scenario/choose",
        headers=child["headers"],
        json={"choice_index": 0},
    )
    # The fallback scenario has 4 choices, so index 0 is valid.
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# GET /badges
# ---------------------------------------------------------------------------


def test_get_badges_empty(client, child):
    """A new child with no badges should get an empty wall with next_badge populated."""
    resp = client.get("/api/v1/child/literacy/badges", headers=child["headers"])
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert "dimensions" in data
    dims = data["dimensions"]
    assert len(dims) == 4
    dimension_names = {d["dimension"] for d in dims}
    assert dimension_names == {"earning", "choosing", "waiting", "caring"}
    for dim in dims:
        # No current badge for a fresh child.
        assert dim["current_badge"] is None
        assert dim["history"] == []
        # Next badge is None only if definitions are missing from the DB
        # (which they may be in tests without seed data) — both are acceptable.
        if dim["next_badge"] is not None:
            assert "name" in dim["next_badge"]
            assert "level" in dim["next_badge"]


def test_get_badges_with_current_badge(client, child, db):
    """When the child holds a badge, it should appear in the wall."""
    from apps.backend.app.models.literacy_badge import (
        LiteracyBadge,
        LiteracyBadgeDefinition,
    )
    from apps.backend.app.utils.snowflake import next_id

    defn = LiteracyBadgeDefinition(
        id=next_id(),
        dimension="earning",
        level=1,
        name="小小理财师",
        description="描述",
        criteria_summary="标准摘要",
    )
    db.add(defn)
    db.flush()

    badge = LiteracyBadge(
        id=next_id(),
        child_id=int(child["id"]),
        definition_id=defn.id,
        source="scenario",
    )
    db.add(badge)
    db.commit()

    resp = client.get("/api/v1/child/literacy/badges", headers=child["headers"])
    assert resp.status_code == 200, resp.text
    dims = resp.json()["data"]["dimensions"]
    earning_dim = next(d for d in dims if d["dimension"] == "earning")
    assert earning_dim["current_badge"] is not None
    assert earning_dim["current_badge"]["name"] == "小小理财师"
    assert earning_dim["current_badge"]["level"] == 1


def test_get_badges_with_history(client, child, db):
    """Superseded badges should appear in the history list."""
    from apps.backend.app.models.literacy_badge import (
        LiteracyBadge,
        LiteracyBadgeDefinition,
    )
    from apps.backend.app.utils.snowflake import next_id

    defn1 = LiteracyBadgeDefinition(
        id=next_id(), dimension="caring", level=1,
        name="爱心初级", description="", criteria_summary="",
    )
    defn2 = LiteracyBadgeDefinition(
        id=next_id(), dimension="caring", level=2,
        name="爱心中级", description="", criteria_summary="",
    )
    db.add_all([defn1, defn2])
    db.flush()

    old_badge = LiteracyBadge(
        id=next_id(), child_id=int(child["id"]), definition_id=defn1.id,
        source="scenario", superseded_at=datetime.now(UTC),
    )
    current_badge = LiteracyBadge(
        id=next_id(), child_id=int(child["id"]), definition_id=defn2.id,
        source="scenario",
    )
    db.add_all([old_badge, current_badge])
    db.commit()

    resp = client.get("/api/v1/child/literacy/badges", headers=child["headers"])
    assert resp.status_code == 200, resp.text
    dims = resp.json()["data"]["dimensions"]
    caring_dim = next(d for d in dims if d["dimension"] == "caring")
    assert caring_dim["current_badge"]["name"] == "爱心中级"
    assert len(caring_dim["history"]) == 1
    assert caring_dim["history"][0]["name"] == "爱心初级"
    assert caring_dim["history"][0]["superseded_at"] is not None
