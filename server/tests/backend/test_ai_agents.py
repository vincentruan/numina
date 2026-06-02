"""Tests for Agent CRUD API and tenant isolation."""

import pytest


@pytest.fixture
def seed_builtin_agents(db):
    """Seed builtin agents into the test DB."""
    from apps.backend.app.models.ai_agent import AIAgent

    db.add(
        AIAgent(
            id=100000000000001,
            family_id=0,
            agent_name="asset-health-advisor",
            display_name="资产健康顾问",
            description="test builtin",
            icon="🏥",
            color="#10B981",
            soul_md="你是资产健康顾问。" * 2,
            skills=["report", "alerts"],
            agent_type="builtin",
            is_builtin=True,
            display_order=100,
        )
    )
    db.add(
        AIAgent(
            id=100000000000002,
            family_id=0,
            agent_name="finance-optimizer",
            display_name="财务优化师",
            description="test builtin",
            icon="💰",
            color="#F59E0B",
            soul_md="你是财务优化师。" * 2,
            skills=["liability", "spending_leak"],
            agent_type="builtin",
            is_builtin=True,
            display_order=200,
        )
    )
    db.commit()


def test_list_agents_returns_builtin(client, auth_headers, seed_builtin_agents):
    resp = client.get("/api/v1/ai/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["builtin"]) == 2
    assert data["builtin"][0]["agent_name"] == "asset-health-advisor"
    assert data["builtin"][1]["agent_name"] == "finance-optimizer"
    assert data["custom"] == []
    assert isinstance(data["builtin"][0]["id"], str)


def test_create_agent_success(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "my-test-agent",
        "display_name": "我的测试智能体",
        "description": "A test agent",
        "icon": "🎯",
        "color": "#3B82F6",
        "soul_md": "你是一个测试智能体，帮助用户做各种测试。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["agent_name"] == "my-test-agent"
    assert data["display_name"] == "我的测试智能体"
    assert data["is_builtin"] is False
    assert data["can_edit"] is True
    assert data["can_delete"] is True


def test_create_agent_duplicate_name_fails(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "dup-agent",
        "display_name": "Dup1",
        "soul_md": "你是一个重复名称测试智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    resp2 = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp2.status_code == 422


def test_create_agent_builtin_name_conflict(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "asset-health-advisor",
        "display_name": "冒充内置",
        "soul_md": "你是一个冒充内置智能体的自定义智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_create_agent_invalid_name_format(client, auth_headers, seed_builtin_agents):
    payload = {
        "agent_name": "Invalid-Name",
        "display_name": "Invalid",
        "soul_md": "你是一个名称格式错误的智能体。",
    }
    resp = client.post("/api/v1/ai/agents", json=payload, headers=auth_headers)
    assert resp.status_code == 422


def test_update_custom_agent(client, auth_headers, seed_builtin_agents):
    create_resp = client.post(
        "/api/v1/ai/agents",
        json={
            "agent_name": "updatable",
            "display_name": "Before",
            "soul_md": "你是一个可更新的测试智能体。",
        },
        headers=auth_headers,
    )
    agent_id = create_resp.json()["data"]["id"]

    update_resp = client.put(
        f"/api/v1/ai/agents/{agent_id}",
        json={
            "display_name": "After",
            "soul_md": "你是一个已更新的测试智能体。更新后的版本。",
        },
        headers=auth_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["display_name"] == "After"


def test_update_builtin_agent_limited_fields(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(
        f"/api/v1/ai/agents/{builtin_id}",
        json={
            "icon": "🩺",
            "color": "#059669",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["icon"] == "🩺"


def test_update_builtin_agent_disallowed_field(
    client, auth_headers, seed_builtin_agents
):
    builtin_id = "100000000000001"
    resp = client.put(
        f"/api/v1/ai/agents/{builtin_id}",
        json={
            "soul_md": "Hacked soul",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_delete_custom_agent(client, auth_headers, seed_builtin_agents):
    create_resp = client.post(
        "/api/v1/ai/agents",
        json={
            "agent_name": "deletable",
            "display_name": "Deletable",
            "soul_md": "你是一个可删除的测试智能体。",
        },
        headers=auth_headers,
    )
    agent_id = create_resp.json()["data"]["id"]

    del_resp = client.delete(f"/api/v1/ai/agents/{agent_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/ai/agents/{agent_id}", headers=auth_headers)
    assert get_resp.status_code == 404


def test_delete_builtin_agent_forbidden(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.delete(f"/api/v1/ai/agents/{builtin_id}", headers=auth_headers)
    assert resp.status_code == 403


def test_toggle_agent(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(
        f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=false", headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False

    resp2 = client.put(
        f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=true", headers=auth_headers
    )
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_enabled"] is True


# ── U5: system agent can_edit for owners enables read-only edit view ──────────


@pytest.fixture
def seed_system_agents(db):
    """Seed the two existing system agents (ai-assistant, time-machine) plus numina."""
    from apps.backend.app.models.ai_agent import AIAgent

    db.add(
        AIAgent(
            id=100000000000003,
            family_id=0,
            agent_name="ai-assistant",
            display_name="AI助手",
            description="通用对话助手",
            icon="🤖",
            color="#3B82F6",
            soul_md="你是友好的 AI 助手。" * 2,
            skills=["chat"],
            agent_type="system",
            is_builtin=True,
            display_order=10,
        )
    )
    db.add(
        AIAgent(
            id=100000000000005,
            family_id=0,
            agent_name="numina",
            display_name="数鸣",
            description="家庭财务大使",
            icon="✨",
            color="#8b5cf6",
            soul_md="你是数鸣，家庭财务大使。" * 2,
            skills=["*"],
            agent_type="system",
            is_builtin=True,
            display_order=15,
        )
    )
    db.commit()


def test_owner_sees_can_edit_true_for_system_agents(
    client, auth_headers, seed_system_agents
):
    """U5: owner role gets can_edit=True on system agents (enables read-only AgentFormPage view)."""
    resp = client.get("/api/v1/ai/agents", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["system"]) == 2
    for agent in data["system"]:
        assert agent["can_edit"] is True, (
            f"{agent['agent_name']} should be can_edit=True for owner"
        )
        assert agent["can_delete"] is False, (
            f"{agent['agent_name']} must remain can_delete=False"
        )


def _make_numina_agent():
    """Build an AIAgent instance with all fields set (server defaults not applied
    when the agent isn't persisted)."""
    from datetime import datetime

    from apps.backend.app.models.ai_agent import AIAgent

    return AIAgent(
        id=100000000000005,
        family_id=0,
        agent_name="numina",
        display_name="数鸣",
        description="家庭财务大使",
        icon="✨",
        color="#8b5cf6",
        soul_md="你是数鸣。" * 2,
        skills=["*"],
        agent_type="system",
        is_builtin=True,
        display_order=15,
        subagent_enabled=False,
        is_enabled=True,
        created_at=datetime(2026, 5, 27),
        updated_at=datetime(2026, 5, 27),
    )


def test_non_owner_sees_can_edit_false_for_system_agents():
    """Non-owner (adult) role gets can_edit=False on system agents — they cannot navigate to the edit view.

    Tested at the _to_response unit level: JWT embeds role at issue time, so
    flipping User.role in the DB after register does not affect role-checked
    auth dependencies. Calling _to_response directly with a synthesized
    non-owner User mirrors what the dependency would deliver.
    """
    from apps.backend.app.models.user import User
    from apps.backend.app.routers.ai_agents import _to_response

    numina = _make_numina_agent()
    adult_user = User(
        id=999,
        username="adult-test",
        display_name="Adult",
        password_hash="x",
        family_id=42,
        role="adult",
    )
    response = _to_response(numina, adult_user)
    assert response.can_edit is False
    assert response.can_delete is False


def test_owner_to_response_for_system_agent_yields_can_edit_true():
    """Direct unit test confirming owner role → can_edit=True for system agents."""
    from apps.backend.app.models.user import User
    from apps.backend.app.routers.ai_agents import _to_response

    numina = _make_numina_agent()
    owner_user = User(
        id=998,
        username="owner-test",
        display_name="Owner",
        password_hash="x",
        family_id=42,
        role="owner",
    )
    response = _to_response(numina, owner_user)
    assert response.can_edit is True
    assert response.can_delete is False  # system agents never deletable


def test_put_system_agent_still_returns_403_for_owner(
    client, auth_headers, seed_system_agents
):
    """U5: can_edit=True does NOT grant mutation authority — PUT to a system agent still 403s."""
    numina_id = "100000000000005"
    resp = client.put(
        f"/api/v1/ai/agents/{numina_id}",
        json={"display_name": "Hacked Name"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


def test_delete_system_agent_returns_403(client, auth_headers, seed_system_agents):
    """System agents are never deletable — can_delete=False is enforced at API level too."""
    numina_id = "100000000000005"
    resp = client.delete(f"/api/v1/ai/agents/{numina_id}", headers=auth_headers)
    assert resp.status_code == 403


def test_custom_agent_can_edit_for_owner_unchanged(client, auth_headers):
    """U5 must not break custom agent can_edit semantics (owner can still edit own custom agents)."""
    create_resp = client.post(
        "/api/v1/ai/agents",
        json={
            "agent_name": "u5-custom-agent",
            "display_name": "U5 Custom",
            "soul_md": "你是 U5 测试智能体。" * 2,
        },
        headers=auth_headers,
    )
    assert create_resp.status_code == 201
    data = create_resp.json()["data"]
    assert data["agent_type"] == "custom"
    assert data["can_edit"] is True
    assert data["can_delete"] is True
