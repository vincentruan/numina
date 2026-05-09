"""Tests for AI capability discovery API."""

from app.models.ai_provider_config import AIProviderConfig
from app.models.family_skill_config import FamilySkillConfig
from app.models.user import User


def test_list_capabilities_returns_enabled_capability_grid_items(client, auth_headers, db):
    user = db.query(User).filter_by(username="testuser").first()
    assert user is not None
    db.add(
        AIProviderConfig(
            family_id=user.family_id,
            name="测试配置",
            provider="anthropic",
            api_key_encrypted="test_encrypted_key",
            model_id="claude-3-5-sonnet-20241022",
            is_active=True,
        )
    )
    db.add(
        FamilySkillConfig(
            family_id=user.family_id,
            capability="alerts",
            is_enabled=False,
            custom_prompt=None,
        )
    )
    db.commit()

    resp = client.get("/api/v1/ai/capabilities", headers=auth_headers)

    assert resp.status_code == 200
    data = resp.json()["data"]
    ids = [cap["id"] for cap in data]
    assert "report" in ids
    assert "chat" in ids
    assert "alerts" not in ids

    chat = next(cap for cap in data if cap["id"] == "chat")
    assert chat["name"] == "AI 问答"
    assert chat["ui"]["route"] == "/ai/chat"
    assert chat["policy"]["enable_thinking"] is True
