"""Tests for the agent capability registry."""

from pathlib import Path

from services.capability_registry import CapabilityRegistry


def test_registry_loads_skill_frontmatter_as_capability(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "chat.md").write_text(
        """---
capability: chat
name: AI 问答
description: 回答家庭资产问题
category: conversation
thinking: true
mcp_tools: [asset_search]
icon: message-circle
route: /ai/chat
examples:
  - 我们家净资产是多少？
---
prompt body
""",
        encoding="utf-8",
    )

    registry = CapabilityRegistry(skills_dir=skills_dir)

    capabilities = registry.list_capabilities()

    assert len(capabilities) == 1
    cap = capabilities[0]
    assert cap.id == "chat"
    assert cap.name == "AI 问答"
    assert cap.description == "回答家庭资产问题"
    assert cap.category == "conversation"
    assert cap.ui.icon == "message-circle"
    assert cap.ui.route == "/ai/chat"
    assert cap.ui.example_questions == ["我们家净资产是多少？"]
    assert cap.policy.enable_thinking is True
    assert cap.policy.enable_tools == ["asset_search"]


def test_registry_uses_defaults_for_minimal_skill(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "alerts.md").write_text(
        """---
capability: alerts
thinking: false
---
prompt body
""",
        encoding="utf-8",
    )

    cap = CapabilityRegistry(skills_dir=skills_dir).get("alerts")

    assert cap is not None
    assert cap.id == "alerts"
    assert cap.name == "alerts"
    assert cap.description == ""
    assert cap.ui.route is None
    assert cap.policy.enable_thinking is False
