"""Unit tests for EffectiveConfigBuilder."""
import shutil
import pytest
from packages.core.effective_config import EffectiveConfigBuilder, EffectiveConfig
from packages.core.path_manager import PathManager


@pytest.fixture
def tmp_data_root(tmp_path):
    return tmp_path / "data"


@pytest.fixture
def pm(tmp_data_root):
    return PathManager(data_root=tmp_data_root)


@pytest.fixture
def builder(pm):
    return EffectiveConfigBuilder(pm)


@pytest.fixture
def sample_ai_provider():
    return {
        "ai_provider": "anthropic",
        "ai_model_id": "claude-sonnet-4-6",
        "api_key": "sk-test-key",
        "model_1_capabilities": ["text_generation", "deep_thinking"],
    }


@pytest.fixture
def sample_agent_config():
    return {
        "agent_name": "asset-health-advisor",
        "soul_md": "You are a professional asset health advisor.",
        "skills": ["family-asset-checkup"],
        "tool_groups": [],
        "model": None,
        "subagent_enabled": False,
        "is_enabled": True,
    }


class TestEffectiveConfigBuild:
    def test_returns_effective_config(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert isinstance(result, EffectiveConfig)

    def test_config_dict_has_models(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        assert "models" in result.config_dict
        assert len(result.config_dict["models"]) == 1
        model = result.config_dict["models"][0]
        assert model["name"] == "main"
        assert model["model"] == "claude-sonnet-4-6"
        assert model["api_key"] == "sk-test-key"

    def test_config_dict_has_memory(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        memory = result.config_dict["memory"]
        assert memory["enabled"] is True
        expected_path = str(pm.tenant_memory_dir(12345, "asset-health-advisor") / "memory.json")
        assert memory["storage_path"] == expected_path

    def test_config_dict_has_checkpointer(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        cp = result.config_dict["checkpointer"]
        assert cp["type"] == "sqlite"
        assert "deerflow-checkpoints.db" in cp["connection_string"]

    def test_config_dict_has_skills_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        result = builder.build(
            family_id=12345,
            agent_name="asset-health-advisor",
            ai_provider=sample_ai_provider,
            agent_config=sample_agent_config,
            enabled_skills=[],
            mcp_servers=[],
        )
        skills = result.config_dict["skills"]
        expected = str(pm.effective_skills_dir(12345))
        assert skills["path"] == expected


class TestEffectiveConfigIsolation:
    def test_two_families_get_different_memory_paths(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(family_id=11111, agent_name="asset-health-advisor", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        config_b = builder.build(family_id=22222, agent_name="asset-health-advisor", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        assert config_a.config_dict["memory"]["storage_path"] != config_b.config_dict["memory"]["storage_path"]
        assert "11111" in config_a.config_dict["memory"]["storage_path"]
        assert "22222" in config_b.config_dict["memory"]["storage_path"]

    def test_two_families_get_different_skills_paths(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(family_id=11111, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        config_b = builder.build(family_id=22222, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        assert config_a.config_dict["skills"]["path"] != config_b.config_dict["skills"]["path"]

    def test_config_dicts_are_independent_objects(self, builder, sample_ai_provider, sample_agent_config):
        config_a = builder.build(family_id=11111, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        config_b = builder.build(family_id=22222, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        config_a.config_dict["models"][0]["api_key"] = "MUTATED"
        assert config_b.config_dict["models"][0]["api_key"] == "sk-test-key"


class TestEffectiveConfigWithProvider:
    def test_openai_provider(self, builder, sample_agent_config):
        provider = {"ai_provider": "openai", "ai_model_id": "gpt-4o", "api_key": "sk-openai-test", "model_1_capabilities": ["text_generation"]}
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        model = result.config_dict["models"][0]
        assert model["use"] == "langchain_openai:ChatOpenAI"
        assert model["model"] == "gpt-4o"

    def test_openai_compatible_with_base_url(self, builder, sample_agent_config):
        provider = {"ai_provider": "openai_compatible", "ai_model_id": "glm-4", "api_key": "sk-glm", "ai_base_url": "https://api.zhipu.ai/v4", "model_1_capabilities": ["text_generation"]}
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        model = result.config_dict["models"][0]
        assert model["base_url"] == "https://api.zhipu.ai/v4"


class TestEffectiveConfigSkillMerging:
    def test_builtin_skill_source_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        skills = [{"skill_name": "family-asset-checkup", "is_builtin": True}]
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=skills, mcp_servers=[])
        assert result.skill_sources == [{"name": "family-asset-checkup", "source": pm.builtin_skill_dir("family-asset-checkup"), "is_builtin": True}]

    def test_custom_skill_source_path(self, builder, pm, sample_ai_provider, sample_agent_config):
        skills = [{"skill_name": "my-custom-skill", "is_builtin": False}]
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=skills, mcp_servers=[])
        assert result.skill_sources == [{"name": "my-custom-skill", "source": pm.tenant_skill_dir(12345, "my-custom-skill"), "is_builtin": False}]

    def test_mixed_builtin_and_custom_skills(self, builder, pm, sample_ai_provider, sample_agent_config):
        skills = [{"skill_name": "builtin-skill", "is_builtin": True}, {"skill_name": "custom-skill", "is_builtin": False}]
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=skills, mcp_servers=[])
        assert len(result.skill_sources) == 2
        names = [s["name"] for s in result.skill_sources]
        assert "builtin-skill" in names
        assert "custom-skill" in names


class TestEffectiveConfigMCPServers:
    def test_mcp_servers_included_when_provided(self, builder, sample_ai_provider, sample_agent_config):
        mcp = [{"name": "filesystem", "transport": "stdio", "command": "mcp-filesystem"}]
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=mcp)
        assert result.extensions_config_path != ""
        assert "mcp_servers" not in result.config_dict

    def test_mcp_servers_omitted_when_empty(self, builder, sample_ai_provider, sample_agent_config):
        result = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        assert result.extensions_config_path == ""
        assert "mcp_servers" not in result.config_dict


class TestEffectiveConfigRebuilds:
    def test_rebuild_produces_same_config(self, builder, sample_ai_provider, sample_agent_config):
        result1 = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        effective_dir = builder._pm.effective_dir(12345)
        if effective_dir.exists():
            shutil.rmtree(effective_dir)
        result2 = builder.build(family_id=12345, agent_name="my-agent", ai_provider=sample_ai_provider, agent_config=sample_agent_config, enabled_skills=[], mcp_servers=[])
        assert result1.config_dict == result2.config_dict
