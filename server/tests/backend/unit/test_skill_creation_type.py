"""Tests for SkillRegistry creation_type and source_url columns (U1)."""

from apps.backend.app.models.skill_registry import SkillRegistry
from apps.backend.app.utils.snowflake import next_id


def test_creation_type_defaults_to_manual(db):
    """New SkillRegistry record defaults creation_type to 'manual' when not specified."""
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-default-creation",
        skill_type="custom",
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.creation_type == "manual"


def test_creation_type_accepts_manual(db):
    """creation_type accepts 'manual' value."""
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-creation-manual",
        skill_type="custom",
        creation_type="manual",
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.creation_type == "manual"


def test_creation_type_accepts_cmd(db):
    """creation_type accepts 'cmd' value."""
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-creation-cmd",
        skill_type="custom",
        creation_type="cmd",
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.creation_type == "cmd"


def test_creation_type_accepts_ai_created(db):
    """creation_type accepts 'ai_created' value."""
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-creation-ai",
        skill_type="custom",
        creation_type="ai_created",
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.creation_type == "ai_created"


def test_source_url_is_nullable(db):
    """source_url is nullable — None is accepted."""
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-source-url-null",
        skill_type="custom",
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.source_url is None


def test_source_url_stores_value(db):
    """source_url stores a URL string when provided."""
    url = "https://example.com/skills/my-skill.md"
    skill = SkillRegistry(
        id=next_id(),
        family_id=next_id(),
        skill_id="test-source-url-set",
        skill_type="custom",
        source_url=url,
    )
    db.add(skill)
    db.commit()
    db.refresh(skill)
    assert skill.source_url == url
