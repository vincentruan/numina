"""Tests for SkillLoader."""
from apps.agent.services.deerflow_adapter.skill_loader import SkillLoader


def test_load_report_skill():
    loader = SkillLoader()
    config = loader.load("report")
    assert config.capability == "report"
    assert config.thinking is True
    assert config.prompt == ""  # prompts live in skills/custom/*/SKILL.md, loaded by DeerFlow harness


def test_load_alerts_skill():
    loader = SkillLoader()
    config = loader.load("alerts")
    assert config.thinking is False


def test_load_missing_skill_returns_minimal():
    loader = SkillLoader()
    config = loader.load("nonexistent_capability")
    assert config.capability == "nonexistent_capability"
    assert config.thinking is False
    assert config.prompt == ""


def test_cache_works():
    loader = SkillLoader()
    config1 = loader.load("report")
    config2 = loader.load("report")
    assert config1 is config2  # same object from cache


def test_invalidate_clears_cache():
    loader = SkillLoader()
    loader.load("report")
    assert "report" in loader._cache
    loader.invalidate("report")
    assert "report" not in loader._cache


def test_all_capabilities_loadable():
    loader = SkillLoader()
    capabilities = ["report", "alerts", "disposal", "liability", "allocation",
                    "spending_leak", "time_machine", "chat"]
    for cap in capabilities:
        config = loader.load(cap)
        assert config.capability == cap
        assert config.prompt == "", f"Expected empty prompt for {cap} (prompts live in DeerFlow custom skills)"
