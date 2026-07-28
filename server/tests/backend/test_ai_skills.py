"""Tests for ai_skills.py - RESERVED_NAMES + INTERNAL_ONLY_SKILLS + FIXED_CAPABILITIES cleanup."""

from apps.backend.app.routers.ai_skills import RESERVED_NAMES


def test_reserved_names_contains_chat_and_time_machine():
    """RESERVED_NAMES protects system fixed-flows from custom skill collisions.

    U7 deleted ``time_machine`` (and 4 other trigger skills); U8 added
    ``import-parse``; Plan A T1 added ``finance-coach``. The current reserved
    set is the post-U7 + Plan A state — ``time_machine`` is intentionally gone.
    """
    assert RESERVED_NAMES == ["chat", "asset-report", "import-parse", "finance-coach", "dashboard-narrative"]


def test_fixed_capabilities_constant_removed():
    """The FIXED_CAPABILITIES constant should no longer exist on the module."""
    from apps.backend.app.routers import ai_skills

    assert not hasattr(ai_skills, "FIXED_CAPABILITIES"), (
        "FIXED_CAPABILITIES should be removed per R9; use RESERVED_NAMES instead"
    )


def test_grouped_skills_fixed_section_is_empty(client, auth_headers):
    """GET /api/v1/ai/skills/grouped returns an empty fixed section (no chat/time_machine virtuals)."""
    resp = client.get("/api/v1/ai/skills/grouped", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json().get("data", resp.json())
    assert data["fixed"] == []
    builtin_ids = {item["id"] for item in data["builtin"]}
    assert "chat" not in builtin_ids
    assert "time_machine" not in builtin_ids
    assert builtin_ids == set()  # T11: BUILTIN_CAPABILITIES deleted, builtin always empty


def test_toggle_report_returns_not_found(client, auth_headers):
    """report is a fixed system flow (not a toggleable skill),
    so toggling it via the skill-management endpoint returns 404."""
    resp = client.put(
        "/api/v1/ai/skills/report/toggle",
        json={"is_enabled": False},
        headers=auth_headers,
    )
    assert resp.status_code in (404, 400), resp.text


def test_toggle_chat_returns_not_found(client, auth_headers):
    """Toggling 'chat' returns 404 — chat is no longer a known skill in the catalog."""
    resp = client.put(
        "/api/v1/ai/skills/chat/toggle",
        json={"is_enabled": False},
        headers=auth_headers,
    )
    # chat is in RESERVED_NAMES, and no SkillRegistry record exists for it.
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
    """Creating a custom skill with a RESERVED_NAMES skill_id is rejected.

    U7 removed ``time_machine`` from RESERVED_NAMES, so that id is no longer
    rejected. ``finance-coach`` (Plan A T1) is now a reserved system
    fixed-flow — use it to verify the reserved-name rejection path stays alive.
    """
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "finance-coach",
            "name": "My Finance Coach",
            "icon": "💰",
            "color": "#a855f7",
            "prompt_content": "Custom prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422), resp.text


def test_create_custom_skill_with_internal_only_id_rejected(client, auth_headers):
    """T11: BUILTIN_CAPABILITIES deleted; INTERNAL_ONLY_SKILLS (e.g. skill-creator) still rejects custom skill creation."""
    resp = client.post(
        "/api/v1/ai/skills/custom",
        json={
            "skill_id": "skill-creator",
            "name": "My Creator",
            "icon": "🛠️",
            "color": "#6366f1",
            "prompt_content": "Custom prompt",
        },
        headers=auth_headers,
    )
    assert resp.status_code in (400, 422), resp.text
    body = resp.text
    assert "内部技能" in body or "internal" in body.lower()


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
