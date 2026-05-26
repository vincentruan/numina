"""Tests for Agent CRUD API and tenant isolation."""
import pytest


@pytest.fixture
def seed_builtin_agents(db):
    """Seed builtin agents into the test DB."""
    from apps.backend.app.models.ai_agent import AIAgent

    db.add(AIAgent(
        id=100000000000001, family_id=0, agent_name="asset-health-advisor",
        display_name="资产健康顾问", description="test builtin",
        icon="🏥", color="#10B981", soul_md="你是资产健康顾问。" * 2,
        skills=["report", "alerts"], agent_type="builtin", display_order=100,
    ))
    db.add(AIAgent(
        id=100000000000002, family_id=0, agent_name="finance-optimizer",
        display_name="财务优化师", description="test builtin",
        icon="💰", color="#F59E0B", soul_md="你是财务优化师。" * 2,
        skills=["liability", "spending_leak"], agent_type="builtin", display_order=200,
    ))
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
    create_resp = client.post("/api/v1/ai/agents", json={
        "agent_name": "updatable",
        "display_name": "Before",
        "soul_md": "你是一个可更新的测试智能体。",
    }, headers=auth_headers)
    agent_id = create_resp.json()["data"]["id"]

    update_resp = client.put(f"/api/v1/ai/agents/{agent_id}", json={
        "display_name": "After",
        "soul_md": "你是一个已更新的测试智能体。更新后的版本。",
    }, headers=auth_headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["data"]["display_name"] == "After"


def test_update_builtin_agent_limited_fields(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}", json={
        "icon": "🩺",
        "color": "#059669",
    }, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["icon"] == "🩺"


def test_update_builtin_agent_disallowed_field(client, auth_headers, seed_builtin_agents):
    builtin_id = "100000000000001"
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}", json={
        "soul_md": "Hacked soul",
    }, headers=auth_headers)
    assert resp.status_code == 422


def test_delete_custom_agent(client, auth_headers, seed_builtin_agents):
    create_resp = client.post("/api/v1/ai/agents", json={
        "agent_name": "deletable",
        "display_name": "Deletable",
        "soul_md": "你是一个可删除的测试智能体。",
    }, headers=auth_headers)
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
    resp = client.put(f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=false", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_enabled"] is False

    resp2 = client.put(f"/api/v1/ai/agents/{builtin_id}/toggle?enabled=true", headers=auth_headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["is_enabled"] is True
