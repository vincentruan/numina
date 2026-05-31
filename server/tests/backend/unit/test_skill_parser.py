"""Tests for SKILL.md frontmatter parser."""

import pytest

from apps.backend.app.services.skill_parser import (
    parse_skill_frontmatter,
    validate_skill_content,
)


class TestParseSkillFrontmatter:
    def test_valid_skill_md(self):
        content = "---\nname: deploy-staging\ndescription: Deploy to staging\n---\n\n# Instructions\nDo stuff"
        result = parse_skill_frontmatter(content)
        assert result["name"] == "deploy-staging"
        assert result["description"] == "Deploy to staging"
        assert result["raw_frontmatter"]["name"] == "deploy-staging"

    def test_extra_fields_preserved_in_raw(self):
        content = "---\nname: test\ndescription: desc\ntrigger_phrases:\n  - hello\nallowed-tools: []\n---\n\nbody"
        result = parse_skill_frontmatter(content)
        assert result["name"] == "test"
        assert result["description"] == "desc"
        assert "trigger_phrases" in result["raw_frontmatter"]

    def test_missing_delimiters(self):
        content = "name: test\ndescription: no frontmatter"
        result = parse_skill_frontmatter(content)
        assert result["name"] is None
        assert result["description"] is None
        assert result["raw_frontmatter"] == {}

    def test_malformed_yaml(self):
        content = "---\nname: [invalid yaml\n  broken: {{\n---\n\nbody"
        result = parse_skill_frontmatter(content)
        assert result["name"] is None
        assert result["raw_frontmatter"] == {}

    def test_empty_content(self):
        result = parse_skill_frontmatter("")
        assert result["name"] is None
        assert result["description"] is None

    def test_frontmatter_only_no_body(self):
        content = "---\nname: minimal\ndescription: just frontmatter\n---\n"
        result = parse_skill_frontmatter(content)
        assert result["name"] == "minimal"

    def test_unicode_content(self):
        content = "---\nname: 资产分析\ndescription: 分析家庭资产配置\n---\n\n# 说明"
        result = parse_skill_frontmatter(content)
        assert result["name"] == "资产分析"
        assert result["description"] == "分析家庭资产配置"

    def test_oversized_frontmatter_rejected(self):
        huge_yaml = "name: test\n" + "x: " + "a" * 5000 + "\n"
        content = f"---\n{huge_yaml}---\n\nbody"
        result = parse_skill_frontmatter(content)
        assert result["name"] is None

    def test_non_dict_yaml(self):
        content = "---\n- item1\n- item2\n---\n\nbody"
        result = parse_skill_frontmatter(content)
        assert result["name"] is None


class TestValidateSkillContent:
    def test_valid_content(self):
        content = "---\nname: test-skill\ndescription: A test\n---\n\n# Instructions"
        assert validate_skill_content(content) is True

    def test_missing_name(self):
        content = "---\ndescription: no name field\n---\n\nbody"
        assert validate_skill_content(content) is False

    def test_empty_content(self):
        assert validate_skill_content("") is False

    def test_no_frontmatter(self):
        assert validate_skill_content("just plain text") is False
