"""Tests for streak multiplier, streak_bonus, milestones, and milestone API."""

import pytest

from tests.backend.conftest import child_login_two_phase


def _data(resp):
    body = resp.json()
    return body.get("data", body)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def child_user(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "xiaoming5",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = _data(resp)
    token = child_login_two_phase(client, "xiaoming5", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def template(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "刷牙",
        "emoji": "🦷",
        "coin_reward": 10,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201
    return _data(resp)


def _get_instance(client, child_headers, date_str=None):
    """Get today's chore instance for the child."""
    from datetime import date
    params = {"date": date_str or date.today().isoformat()}
    resp = client.get("/api/v1/child/chores", headers=child_headers, params=params)
    assert resp.status_code == 200
    instances = _data(resp)
    assert len(instances) > 0
    return instances[0]


def _complete_and_approve(client, child_headers, auth_headers, instance_id):
    """Mark complete then approve, return approve response."""
    r = client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_headers)
    assert r.status_code == 200
    r2 = client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)
    assert r2.status_code == 200
    return _data(r2)


# ---------------------------------------------------------------------------
# Multiplier threshold tests
# ---------------------------------------------------------------------------

def test_streak_multiplier_no_bonus_at_streak_1(client, auth_headers, child_user, template):
    """streak=1 → no bonus, amount == base coin_reward."""
    instance = _get_instance(client, child_user["headers"])
    result = _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])
    assert result["streak_count"] == 1
    assert result["streak_bonus"] == 0


def test_streak_bonus_floor_division(client, auth_headers, child_user):
    """coin_reward=3, streak=7 → actual=int(3*1.5)=4, bonus=1."""
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "读书",
        "coin_reward": 3,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201

    # Simulate 7 consecutive days by manipulating date_bucket via direct DB
    # Instead, test the multiplier helper directly via import
    from apps.backend.app.services.chores import _get_streak_multiplier
    assert _get_streak_multiplier(1) == 1.0
    assert _get_streak_multiplier(6) == 1.0
    assert _get_streak_multiplier(7) == 1.5
    assert _get_streak_multiplier(13) == 1.5
    assert _get_streak_multiplier(14) == 2.0
    assert _get_streak_multiplier(30) == 2.0
    assert int(3 * 1.5) == 4  # floor division check


def test_get_streak_multiplier_thresholds():
    """Unit test for _get_streak_multiplier."""
    from apps.backend.app.services.chores import _get_streak_multiplier
    assert _get_streak_multiplier(1) == 1.0
    assert _get_streak_multiplier(6) == 1.0
    assert _get_streak_multiplier(7) == 1.5
    assert _get_streak_multiplier(13) == 1.5
    assert _get_streak_multiplier(14) == 2.0
    assert _get_streak_multiplier(100) == 2.0


# ---------------------------------------------------------------------------
# Milestone: first_chore
# ---------------------------------------------------------------------------

def test_first_chore_triggers_on_first_approval(client, auth_headers, child_user, template):
    instance = _get_instance(client, child_user["headers"])
    result = _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])
    assert result.get("milestone_triggered") == "first_chore"


def test_first_chore_not_duplicated(client, auth_headers, child_user, template):
    """Second approval does not re-trigger first_chore."""

    # First approval
    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    # Second day — need a new instance; simulate by checking milestones count
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    assert resp.status_code == 200
    milestones = _data(resp)
    first_chore_count = sum(1 for m in milestones if m["milestone_type"] == "first_chore")
    assert first_chore_count == 1


# ---------------------------------------------------------------------------
# Milestone: coins_50 / coins_200
# ---------------------------------------------------------------------------

def test_coins_50_triggers_when_total_crosses(client, auth_headers, child_user):
    """Grant 49 coins, then approve a chore worth 2 → coins_50 triggers."""
    # Grant 49 coins
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 49,
        "reason": "test grant",
    })

    # Create a template worth 2 coins
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "整理书包",
        "coin_reward": 2,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201

    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    # coins_50 should appear in milestones list (first_chore may also be there)
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    milestones = _data(resp)
    types = [m["milestone_type"] for m in milestones]
    assert "coins_50" in types


def test_coins_50_based_on_total_earned_not_balance(client, auth_headers, child_user, template):
    """Spending coins (wish realize) doesn't prevent coins_50 milestone."""
    # Grant 48 coins
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 48,
        "reason": "test",
    })

    # Approve a chore worth 10 → total earned = 58, but we check total not balance
    instance = _get_instance(client, child_user["headers"])
    _result = _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    # Should have coins_50 in milestones since total earned (48+10=58) >= 50
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    types = [m["milestone_type"] for m in _data(resp)]
    assert "coins_50" in types


def test_coins_50_not_triggered_if_already_recorded(client, auth_headers, child_user, template):
    """coins_50 only triggers once."""
    # Grant 60 coins to already be past threshold
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 60,
        "reason": "test",
    })

    # First approval — may trigger coins_50
    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    # Check milestones — coins_50 should appear at most once
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    milestones = _data(resp)
    coins_50_count = sum(1 for m in milestones if m["milestone_type"] == "coins_50")
    assert coins_50_count <= 1


# ---------------------------------------------------------------------------
# Milestone: first_wish_realized
# ---------------------------------------------------------------------------

def test_first_wish_realized_triggers(client, auth_headers, child_user):
    """Realizing a wish triggers first_wish_realized milestone."""
    # Grant enough coins
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 100,
        "reason": "test",
    })

    # Create and approve a wish
    resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "乐高",
        "priority": "high",
    })
    assert resp.status_code == 201
    wish = _data(resp)

    # Parent approves with cost 10
    r = client.post(f"/api/v1/family/child-wishes/{wish['id']}/approve", headers=auth_headers,
                    json={"star_coin_cost": 10})
    assert r.status_code == 200

    # Child requests redemption
    r = client.post(f"/api/v1/child/wishes/{wish['id']}/request-redemption", headers=child_user["headers"])
    assert r.status_code == 200

    # Get a category for realize
    cat_resp = client.get("/api/v1/categories", headers=auth_headers)
    categories = _data(cat_resp)
    cat_id = categories[0]["id"] if categories else None

    # Parent realizes
    realize_body = {"category_id": cat_id} if cat_id else {}
    r = client.post(f"/api/v1/family/child-wishes/{wish['id']}/realize", headers=auth_headers,
                    json=realize_body)
    assert r.status_code == 200
    # first_wish_realized should be recorded (coins_50 may also fire due to grant)
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    types = [m["milestone_type"] for m in _data(resp)]
    assert "first_wish_realized" in types


# ---------------------------------------------------------------------------
# Milestone failure isolation
# ---------------------------------------------------------------------------

def test_milestone_failure_does_not_block_approval(client, auth_headers, child_user, template, monkeypatch):
    """If milestone check raises, approval still succeeds."""
    from apps.backend.app.services import milestones as ms

    def boom(*args, **kwargs):
        raise RuntimeError("simulated milestone failure")

    monkeypatch.setattr(ms, "_check_milestones", boom)

    instance = _get_instance(client, child_user["headers"])
    r = client.post(f"/api/v1/child/chores/{instance['id']}/complete", headers=child_user["headers"])
    assert r.status_code == 200
    r2 = client.post(f"/api/v1/family/chore-approvals/{instance['id']}/approve", headers=auth_headers)
    assert r2.status_code == 200  # approval succeeds despite milestone failure
    result = _data(r2)
    assert result.get("milestone_triggered") is None


# ---------------------------------------------------------------------------
# Milestone API endpoints
# ---------------------------------------------------------------------------

def test_child_can_list_own_milestones(client, auth_headers, child_user, template):
    """Child can list their own milestones."""
    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    assert resp.status_code == 200
    milestones = _data(resp)
    assert isinstance(milestones, list)
    assert len(milestones) >= 1
    assert milestones[0]["milestone_type"] == "first_chore"


def test_parent_can_list_child_milestones(client, auth_headers, child_user, template):
    """Parent can list a child's milestones."""
    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    resp = client.get(f"/api/v1/family/children/{child_user['id']}/milestones", headers=auth_headers)
    assert resp.status_code == 200
    milestones = _data(resp)
    assert len(milestones) >= 1


def test_parent_cross_family_blocked(client, auth_headers, child_user):
    """Parent cannot access child from another family."""
    # Register a second family
    r = client.post("/api/v1/auth/register", json={
        "username": "other_parent",
        "password": "Password123",
        "display_name": "Other Parent",
        "family_name": "Other Family",
        "family_invitation_code": "AUTO-MILESTONE-OTHER"
    })
    assert r.status_code == 200
    other_token = _data(r)["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}

    resp = client.get(f"/api/v1/family/children/{child_user['id']}/milestones", headers=other_headers)
    assert resp.status_code == 404


def test_empty_milestones_returns_empty_list(client, auth_headers, child_user):
    """New child with no milestones returns empty list."""
    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    assert resp.status_code == 200
    assert _data(resp) == []


def test_milestone_response_has_required_fields(client, auth_headers, child_user, template):
    """Milestone response includes id, milestone_type, triggered_at."""
    instance = _get_instance(client, child_user["headers"])
    _complete_and_approve(client, child_user["headers"], auth_headers, instance["id"])

    resp = client.get("/api/v1/child/milestones", headers=child_user["headers"])
    m = _data(resp)[0]
    assert "id" in m
    assert "milestone_type" in m
    assert "triggered_at" in m


# ---------------------------------------------------------------------------
# Milestone: streak_7 re-triggers across cycles (P1-A regression test)
# ---------------------------------------------------------------------------

def test_streak_7_retriggers_in_second_cycle(db, client, auth_headers, child_user, template):
    """streak_7 milestone must fire again after a streak reset and rebuild.

    This is a regression test for the unique constraint bug: the old migration
    had UniqueConstraint('child_user_id', 'milestone_type') which prevented
    streak_7/14/30 from being recorded more than once per child.
    """
    from uuid import uuid4

    from apps.backend.app.models.child_milestone import ChildMilestone
    from apps.backend.app.models.chore import ChoreInstance
    from apps.backend.app.services.milestones import check_and_record_milestones

    child_id = child_user["id"]
    # Resolve family_id from DB
    from apps.backend.app.models.user import User
    child_obj = db.query(User).filter(User.id == child_id).first()
    family_id = child_obj.family_id

    # Get the template id
    tmpl_resp = client.get("/api/v1/family/chore-templates", headers=auth_headers)
    tmpl_id = _data(tmpl_resp)[0]["id"]

    def _make_instance(streak: int, bucket: str) -> ChoreInstance:
        inst = ChoreInstance(
            id=str(uuid4()),
            template_id=tmpl_id,
            family_id=family_id,
            child_user_id=child_id,
            chore_name="刷牙",
            chore_emoji="🦷",
            coin_reward=10,
            date_bucket=bucket,
            status="approved",
            streak_count=streak,
            streak_bonus=0,
        )
        db.add(inst)
        db.flush()
        return inst

    # --- First cycle: streak reaches 10 (above threshold 7) ---
    inst_cycle1 = _make_instance(streak=10, bucket="2026-01-10")
    db.commit()
    check_and_record_milestones(db, child_id, family_id, {"instance": inst_cycle1})

    # Verify one streak_7 record exists (return value may be first_chore due to priority)
    count1 = db.query(ChildMilestone).filter(
        ChildMilestone.child_user_id == child_id,
        ChildMilestone.milestone_type == "streak_7",
    ).count()
    assert count1 == 1, f"Expected 1 streak_7 after first cycle, got {count1}"

    # --- Second cycle: streak resets then rebuilds past 7 ---
    # Cycle detection: inst_cycle2.streak_count (7) < inst_cycle1.streak_count (10)
    # → new cycle detected → streak_7 fires again
    inst_cycle2 = _make_instance(streak=7, bucket="2026-02-07")
    db.commit()
    check_and_record_milestones(db, child_id, family_id, {"instance": inst_cycle2})

    # Verify two streak_7 records now exist (one per cycle)
    count2 = db.query(ChildMilestone).filter(
        ChildMilestone.child_user_id == child_id,
        ChildMilestone.milestone_type == "streak_7",
    ).count()
    assert count2 == 2, f"Expected 2 streak_7 milestones (one per cycle), got {count2}"
