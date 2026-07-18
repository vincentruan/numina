"""Tests for SkillLoader."""
from datetime import datetime

import pytest

from apps.agent.services.deerflow_adapter.skill_loader import (
    SkillLoader,
    _FamilyPromptEntry,
)


def test_load_report_skill():
    loader = SkillLoader()
    config = loader.load("report")
    assert config.capability == "report"
    assert config.thinking is True
    assert config.prompt == ""  # prompts live in skills/custom/*/SKILL.md, loaded by DeerFlow harness


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
    """U7: 5 trigger skills deleted; remaining builtin skills + routing caps load."""
    loader = SkillLoader()
    # report stays until U5; chat is the SOUL; time_machine has no skill dir
    # (returns minimal config) but is still a routing capability.
    capabilities = ["report", "chat", "time_machine"]
    for cap in capabilities:
        config = loader.load(cap)
        assert config.capability == cap
        assert config.prompt == "", f"Expected empty prompt for {cap} (prompts live in DeerFlow custom skills)"


# ── U11 regression: SkillConfig.prompt is dead data ──────────────────────────
# DeerFlow harness loads skills/custom/{capability}/SKILL.md independently.
# SkillConfig.prompt is never consumed by any agent code path.
# These tests pin the architecture decision so future changes don't silently
# re-introduce the brainstorm's failure-point #5.

@pytest.mark.asyncio
async def test_load_for_family_with_empty_override_uses_base_prompt(monkeypatch):
    """When family has no custom prompt, effective_prompt = base.prompt (empty string)."""
    loader = SkillLoader()

    async def fake_fetch(*args, **kwargs):
        return _FamilyPromptEntry(prompt=None, is_enabled=True, updated_at=datetime.utcnow())

    monkeypatch.setattr(loader, "_fetch_family_entry", fake_fetch)

    config = await loader.load_for_family("report", "123", "http://x", "tok")
    # base.prompt is "" (prompts live in DeerFlow custom skills, not builtin SKILL.md)
    assert config.prompt == ""
    assert config.is_enabled is True


@pytest.mark.asyncio
async def test_load_for_family_with_custom_prompt_overrides(monkeypatch):
    """When family has a custom prompt, it goes into SkillConfig.prompt (even though unused)."""
    loader = SkillLoader()

    async def fake_fetch(*args, **kwargs):
        return _FamilyPromptEntry(prompt="custom family prompt", is_enabled=True, updated_at=datetime.utcnow())

    monkeypatch.setattr(loader, "_fetch_family_entry", fake_fetch)

    config = await loader.load_for_family("report", "123", "http://x", "tok")
    assert config.prompt == "custom family prompt"


@pytest.mark.asyncio
async def test_load_for_family_disabled_returns_empty_prompt(monkeypatch):
    """When family disables a capability, prompt is empty and is_enabled=False."""
    loader = SkillLoader()

    async def fake_fetch(*args, **kwargs):
        return _FamilyPromptEntry(prompt="ignored", is_enabled=False, updated_at=datetime.utcnow())

    monkeypatch.setattr(loader, "_fetch_family_entry", fake_fetch)

    config = await loader.load_for_family("report", "123", "http://x", "tok")
    assert config.prompt == ""
    assert config.is_enabled is False


@pytest.mark.asyncio
async def test_load_for_family_fetch_failure_falls_back_to_base(monkeypatch):
    """On network error, falls back to base config (empty prompt, enabled)."""
    loader = SkillLoader()

    async def exploding_fetch(*args, **kwargs):
        raise RuntimeError("network error")

    monkeypatch.setattr(loader, "_fetch_family_entry", exploding_fetch)

    config = await loader.load_for_family("report", "123", "http://x", "tok")
    assert config.prompt == ""
    assert config.is_enabled is True
