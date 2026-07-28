"""Tests for skill command parser — security-critical input validation."""

import pytest

from apps.backend.app.services.skill_command_parser import (
    SkillCommandParser,
)


@pytest.fixture
def parser():
    return SkillCommandParser()


class TestVariantA:
    def test_npx_skills_add(self, parser):
        result = parser.parse("npx skills add anthropics/deploy-staging")
        assert result.match_type == "cli"
        assert result.provider == "anthropics"
        assert result.skill_name == "deploy-staging"

    def test_skillhub_install(self, parser):
        result = parser.parse("skillhub install user/my-skill")
        assert result.match_type == "cli"
        assert result.provider == "user"
        assert result.skill_name == "my-skill"

    def test_case_insensitive(self, parser):
        result = parser.parse("NPX Skills Add Provider/SkillName")
        assert result.match_type == "cli"
        assert result.provider == "provider"
        assert result.skill_name == "skillname"


class TestVariantB:
    def test_github_url(self, parser):
        result = parser.parse("https://github.com/anthropics/skills")
        assert result.match_type == "url"
        assert result.provider == "anthropics"
        assert result.skill_name == "skills"
        assert result.repo_url == "https://github.com/anthropics/skills"

    def test_skills_sh_url(self, parser):
        result = parser.parse("https://skills.sh/v1/skills/deploy-staging")
        assert result.match_type == "url"
        assert result.provider == "skills.sh"
        assert result.skill_name == "deploy-staging"


class TestVariantC:
    def test_curl_pipe_sh(self, parser):
        result = parser.parse("curl -fsSL https://skills.sh/install.sh | sh -s -- deploy")
        assert result.match_type == "unmatched"

    def test_arbitrary_text(self, parser):
        result = parser.parse("install the deploy staging skill from skills.sh")
        assert result.match_type == "unmatched"


class TestSecurityValidation:
    def test_path_traversal_rejected(self, parser):
        result = parser.parse("npx skills add ../../etc/passwd")
        assert result.match_type == "unmatched"

    def test_shell_injection_semicolon(self, parser):
        result = parser.parse("npx skills add foo/bar; rm -rf /")
        assert result.match_type == "unmatched"

    def test_shell_injection_pipe(self, parser):
        result = parser.parse("npx skills add foo/bar|cat /etc/passwd")
        assert result.match_type == "unmatched"

    def test_null_bytes(self, parser):
        result = parser.parse("npx skills add foo/bar\x00evil")
        assert result.match_type == "unmatched"

    def test_url_encoded_traversal(self, parser):
        result = parser.parse("npx skills add foo%2F..%2Fetc/passwd")
        assert result.match_type == "unmatched"

    def test_oversized_input_truncated(self, parser):
        huge = "npx skills add provider/" + "a" * 3000
        result = parser.parse(huge)
        assert len(result.raw_input) == 2048

    def test_dollar_sign_rejected(self, parser):
        result = parser.parse("npx skills add foo/$HOME")
        assert result.match_type == "unmatched"

    def test_backtick_rejected(self, parser):
        result = parser.parse("npx skills add foo/`whoami`")
        assert result.match_type == "unmatched"


class TestEdgeCases:
    def test_empty_string(self, parser):
        result = parser.parse("")
        assert result.match_type == "unmatched"

    def test_whitespace_only(self, parser):
        result = parser.parse("   ")
        assert result.match_type == "unmatched"

    def test_none_like_empty(self, parser):
        result = parser.parse("")
        assert result.match_type == "unmatched"
        assert result.raw_input == ""
