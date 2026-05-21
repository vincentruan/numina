"""Tests for the agent capability registry."""

from pathlib import Path

from apps.agent.services.capability_registry import (
    FIXED_CAPABILITY_DEFS,
    FIXED_CAPABILITIES,
    CapabilityRegistry,
)


def test_registry_loads_skill_frontmatter_as_capability(tmp_path: Path):
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()
    (skills_dir / "alerts.md").write_text(
        """---
capability: alerts
name: 资产预警
description: 检测资产异常
category: monitoring
thinking: true
mcp_tools: [asset_search]
icon: bell
route: /ai/alerts
examples:
  - 有哪些资产需要关注？
---
prompt body
""",
        encoding="utf-8",
    )

    registry = CapabilityRegistry(skills_dir=skills_dir)

    capabilities = registry.list_capabilities()

    # Fixed capabilities (chat + time_machine) are always included
    assert len(capabilities) == len(FIXED_CAPABILITY_DEFS) + 1
    ids = [c.id for c in capabilities]
    assert "chat" in ids
    assert "time_machine" in ids
    assert "alerts" in ids

    # Non-fixed capability loaded from file has correct metadata
    alerts_cap = next(c for c in capabilities if c.id == "alerts")
    assert alerts_cap.name == "资产预警"
    assert alerts_cap.description == "检测资产异常"
    assert alerts_cap.category == "monitoring"
    assert alerts_cap.ui.icon == "bell"
    assert alerts_cap.ui.route == "/ai/alerts"
    assert alerts_cap.ui.example_questions == ["有哪些资产需要关注？"]
    assert alerts_cap.policy.enable_thinking is True
    assert alerts_cap.policy.enable_tools == ["asset_search"]


def test_fixed_capabilities_always_included(tmp_path: Path):
    """Fixed capabilities are returned even when no skill files exist."""
    skills_dir = tmp_path / "skills"
    skills_dir.mkdir()

    registry = CapabilityRegistry(skills_dir=skills_dir)
    capabilities = registry.list_capabilities()

    assert len(capabilities) == len(FIXED_CAPABILITY_DEFS)
    ids = [c.id for c in capabilities]
    for cap_id in FIXED_CAPABILITIES:
        assert cap_id in ids


def test_fixed_capability_defs_metadata():
    """Hard-coded fixed capability definitions have expected metadata."""
    defs_by_id = {c.id: c for c in FIXED_CAPABILITY_DEFS}

    chat = defs_by_id["chat"]
    assert chat.category == "chat"
    assert chat.ui.route == "/ai/chat"
    assert chat.ui.input_mode == "free_text"
    assert chat.policy.enable_thinking is True

    tm = defs_by_id["time_machine"]
    assert tm.category == "simulation"
    assert tm.ui.route == "/ai/time-machine"
    assert tm.ui.input_mode == "free_text"
    assert tm.policy.enable_thinking is True


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

