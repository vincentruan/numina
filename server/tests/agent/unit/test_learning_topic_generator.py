"""Tests for learning-topic-generator skill (Issue #190).

These tests verify:
1. SKILL.md format and content
2. RESERVED_NAMES includes the new skill
3. Agent derivation logic (subject/domain/age_group adaptation)
4. Taxonomy context building from os_taxonomy data
"""

from __future__ import annotations

from pathlib import Path

import pytest

SKILL_DIR = (
    Path(__file__).resolve().parents[3]
    / "apps"
    / "agent"
    / "skills"
    / "builtin"
    / "public"
    / "learning-topic-generator"
)


class TestSkillMd:
    """Verify SKILL.md format and content."""

    @pytest.fixture
    def skill_content(self):
        return (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    def test_skill_md_exists(self):
        assert (SKILL_DIR / "SKILL.md").exists()

    def test_frontmatter_has_required_fields(self, skill_content):
        """SKILL.md must have name, description, trigger_phrases in frontmatter."""
        assert skill_content.startswith("---")
        # Extract frontmatter
        parts = skill_content.split("---", 2)
        assert len(parts) >= 3
        frontmatter = parts[1].strip()

        assert "name: learning-topic-generator" in frontmatter
        assert "description:" in frontmatter
        assert "trigger_phrases:" in frontmatter
        assert "thinking: true" in frontmatter
        assert "max_tokens:" in frontmatter

    def test_trigger_phrases_present(self, skill_content):
        """Must have at least one trigger phrase."""
        assert "/learning-topic-generator" in skill_content

    def test_has_role_definition(self, skill_content):
        assert "## Role" in skill_content

    def test_has_output_format(self, skill_content):
        assert "## Output Format" in skill_content

    def test_has_agent_derivation_rules(self, skill_content):
        assert "## Agent Derivation Rules" in skill_content
        assert "### By Age Group" in skill_content
        assert "### By Subject" in skill_content

    def test_has_content_safety_rules(self, skill_content):
        assert "## Content Safety Rules" in skill_content

    def test_has_quality_checklist(self, skill_content):
        assert "## Quality Checklist" in skill_content

    def test_output_json_has_required_fields(self, skill_content):
        """Output JSON schema must include objectives, outline, prerequisites, exercises."""
        assert '"objectives"' in skill_content
        assert '"outline"' in skill_content
        assert '"prerequisites"' in skill_content
        assert '"recommended_exercises"' in skill_content
        assert '"assessment"' in skill_content

    def test_age_groups_covered(self, skill_content):
        """All three age groups must be documented."""
        assert "**low**" in skill_content
        assert "**mid**" in skill_content
        assert "**high**" in skill_content

    def test_subjects_covered(self, skill_content):
        """Key subjects must have derivation rules."""
        assert "Mathematics" in skill_content
        assert "Science" in skill_content
        assert "English" in skill_content
        assert "Computing" in skill_content


class TestReservedNames:
    """Verify RESERVED_NAMES includes the new skill."""

    def test_reserved_names_includes_learning_topic_generator(self):
        """The ai_skills.py RESERVED_NAMES list must include the new skill."""
        ai_skills_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "backend"
            / "app"
            / "routers"
            / "ai_skills.py"
        )
        content = ai_skills_path.read_text(encoding="utf-8")
        assert '"learning-topic-generator"' in content


class TestWorkerConfig:
    """Verify worker.py _SIMPLE_APPS includes the new config."""

    def test_simple_apps_includes_learning_topic_generator(self):
        worker_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "services"
            / "runtime"
            / "worker.py"
        )
        content = worker_path.read_text(encoding="utf-8")
        assert '"learning-topic-generator": _SimpleAppConfig(' in content
        assert 'skill_name="learning-topic-generator"' in content
        assert 'trigger_key="learning-topic-generator"' in content

    def test_trigger_translations_includes_learning_topic_generator(self):
        worker_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "services"
            / "runtime"
            / "worker.py"
        )
        content = worker_path.read_text(encoding="utf-8")
        # Check trigger phrase entries
        assert '"learning-topic-generator": {' in content
        assert "生成学习课题方案" in content
        assert "Generate learning topic plan" in content

    def test_session_titles_includes_learning_topic_generator(self):
        worker_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "services"
            / "runtime"
            / "worker.py"
        )
        content = worker_path.read_text(encoding="utf-8")
        assert "学习课题方案" in content
        assert "Learning Topic Plan" in content


class TestSseGatewayR1:
    """Verify R1 allowlist includes learning-topic-generator."""

    def test_r1_allowlist_includes_learning_topic_generator(self):
        gateway_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "services"
            / "runtime"
            / "sse_gateway.py"
        )
        content = gateway_path.read_text(encoding="utf-8")
        assert 'app == "learning-topic-generator"' in content
        assert "课题方案生成须经由后端触发端点" in content

    def test_r1_unknown_app_check_includes_learning_topic_generator(self):
        """The unknown-app 400 check must also accept learning-topic-generator."""
        gateway_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "services"
            / "runtime"
            / "sse_gateway.py"
        )
        content = gateway_path.read_text(encoding="utf-8")
        # The app allowlist in the final check must include learning-topic-generator
        assert 'and app != "learning-topic-generator"' in content


class TestAgentGateway:
    """Verify agent gateway has the trigger endpoint."""

    def test_gateway_has_learning_topic_generator_endpoint(self):
        gateway_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "agent"
            / "app"
            / "routers"
            / "gateway.py"
        )
        content = gateway_path.read_text(encoding="utf-8")
        assert '"/runs/learning-topic-generator/{thread_id}"' in content
        assert "LearningTopicGeneratorRunRequest" in content
        assert "trigger_learning_topic_generator_run" in content


class TestTaxonomyContext:
    """Verify os_taxonomy data can be loaded for context building."""

    def test_os_taxonomy_topics_loadable(self):
        from packages.os_taxonomy import get_topics

        topics = get_topics()
        assert len(topics) > 0
        # Verify topic structure
        t = topics[0]
        assert "id" in t
        assert "subject" in t
        assert "domain" in t
        assert "name" in t

    def test_os_taxonomy_dependencies_loadable(self):
        from packages.os_taxonomy import get_dependencies

        deps = get_dependencies()
        assert len(deps) > 0
        d = deps[0]
        assert "topicId" in d
        assert "prerequisiteId" in d
        assert "strength" in d

    def test_os_taxonomy_clusters_loadable(self):
        from packages.os_taxonomy import get_clusters

        clusters = get_clusters()
        assert len(clusters) > 0
        c = clusters[0]
        assert "subject" in c
        assert "domain" in c

    def test_topic_lookup_by_key(self):
        from packages.os_taxonomy import get_topics

        topics = get_topics()
        first_key = topics[0]["id"]
        found = next((t for t in topics if t["id"] == first_key), None)
        assert found is not None
        assert found["id"] == first_key

    def test_dependency_lookup_by_topic(self):
        from packages.os_taxonomy import get_dependencies

        deps = get_dependencies()
        first_topic = deps[0]["topicId"]
        prereqs = [d for d in deps if d["topicId"] == first_topic]
        assert len(prereqs) > 0


class TestBackendEndpoint:
    """Verify backend learning_family.py has the trigger endpoint."""

    def test_backend_has_topic_plan_generate_endpoint(self):
        router_path = (
            Path(__file__).resolve().parents[3]
            / "apps"
            / "backend"
            / "app"
            / "routers"
            / "learning_family.py"
        )
        content = router_path.read_text(encoding="utf-8")
        assert '"/topic-plan/generate"' in content
        assert "_TopicPlanGenerateRequest" in content
        assert "generate_topic_plan" in content
        assert "learning-topic-generator" in content
