"""Tests for U1: ai_skills.py — RESERVED_NAMES + BUILTIN_CAPABILITIES + FIXED_CAPABILITIES cleanup."""

from apps.backend.app.routers.ai_skills import (
    BUILTIN_CAPABILITIES,
    RESERVED_NAMES,
)


def test_builtin_capabilities_excludes_chat_and_time_machine():
    """BUILTIN_CAPABILITIES must contain only the 6 business skills."""
    assert set(BUILTIN_CAPABILITIES) == {
        "report",
        "alerts",
        "allocation",
        "disposal",
        "liability",
        "spending_leak",
    }
    assert "chat" not in BUILTIN_CAPABILITIES
    assert "time_machine" not in BUILTIN_CAPABILITIES


def test_reserved_names_contains_chat_and_time_machine():
    """RESERVED_NAMES protects chat and time_machine from custom skill collisions."""
    assert RESERVED_NAMES == ["chat", "time_machine"]


def test_fixed_capabilities_constant_removed():
    """The FIXED_CAPABILITIES constant should no longer exist on the module."""
    from apps.backend.app.routers import ai_skills

    assert not hasattr(ai_skills, "FIXED_CAPABILITIES"), (
        "FIXED_CAPABILITIES should be removed per R9; use BUILTIN_CAPABILITIES + RESERVED_NAMES instead"
    )


def test_list_skills_returns_only_business_skills(client, auth_headers):
    """GET /api/v1/ai/skills returns the 6 business skills, no chat or time_machine."""
    resp = client.get("/api/v1/ai/skills", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    capabilities = {item["capability"] for item in data}
    assert capabilities == {
        "report",
        "alerts",
        "allocation",
        "disposal",
        "liability",
        "spending_leak",
    }
    assert "chat" not in capabilities
    assert "time_machine" not in capabilities


def test_grouped_skills_fixed_section_is_empty(client, auth_headers):
    """GET /api/v1/ai/skills/grouped returns an empty fixed section (no chat/time_machine virtuals)."""
    resp = client.get("/api/v1/ai/skills/grouped", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["fixed"] == []
    builtin_ids = {item["id"] for item in data["builtin"]}
    assert "chat" not in builtin_ids
    assert "time_machine" not in builtin_ids
    assert builtin_ids == set(BUILTIN_CAPABILITIES)


def test_toggle_business_skill_succeeds(client, auth_headers):
    """Toggling a business skill (e.g. report) succeeds — no FIXED_CAPABILITIES guard."""
    resp = client.put(
        "/api/v1/ai/skills/report/toggle",
        json={"is_enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    assert data["id"] == "report"
    assert data["is_enabled"] is False


def test_toggle_chat_returns_not_found(client, auth_headers):
    """Toggling 'chat' returns 404 — chat is no longer a known skill in the catalog."""
    resp = client.put(
        "/api/v1/ai/skills/chat/toggle",
        json={"is_enabled": False},
        headers=auth_headers,
    )
    # chat is not in BUILTIN_CAPABILITIES anymore, and no SkillRegistry record exists for it.
    # toggle_skill_endpoint raises NOT_FOUND for unknown skills.
    assert resp.status_code in (404, 400), resp.text


def test_toggle_time_machine_returns_not_found(client, auth_headers):
    """Toggling 'time_machine' returns 404 — time_machine is no longer a known skill."""
    resp = client.put(
        "/api/v1/ai/skills/time_machine/toggle",
        json={"is_enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code in (404, 400), resp.text


def test_create_custom_skill_with_chat_id_rejected(client, auth_headers):
    """Creating a custom skill with skill_id='chat' is rejected by RESERVED_NAMES."""
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "chat",
            "name": "My Chat",
            "icon": "💬",
            "color": "#06b6d4",
            "prompt_content": "Custom chat prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422), resp.text
    body = resp.text
    assert "保留命名" in body or "reserved" in body.lower()


def test_create_custom_skill_with_time_machine_id_rejected(client, auth_headers):
    """Creating a custom skill with skill_id='time_machine' is rejected by RESERVED_NAMES."""
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "time_machine",
            "name": "My Time Machine",
            "icon": "⏰",
            "color": "#a855f7",
            "prompt_content": "Custom prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422), resp.text


def test_create_custom_skill_with_builtin_id_rejected(client, auth_headers):
    """Creating a custom skill with skill_id='report' is rejected by BUILTIN_CAPABILITIES."""
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "report",
            "name": "My Report",
            "icon": "📊",
            "color": "#6366f1",
            "prompt_content": "Custom prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422), resp.text
    body = resp.text
    assert "内置技能" in body or "builtin" in body.lower()


def test_create_custom_skill_with_unique_id_succeeds(client, auth_headers):
    """Creating a custom skill with a non-reserved, non-builtin id succeeds."""
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "my_custom_skill",
            "name": "我的自定义技能",
            "icon": "✨",
            "color": "#8b5cf6",
            "prompt_content": "Custom skill prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json().get("data", resp.json())
    assert data["id"] == "my_custom_skill"
    assert data["skill_type"] == "custom"
