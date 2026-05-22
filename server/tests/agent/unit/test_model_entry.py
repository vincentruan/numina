"""Unit tests for ModelEntryBuilder — provider-to-class mapping + thinking config."""
import pytest
from packages.core.model_entry import build_model_entry


class TestProviderClassMapping:
    def test_anthropic_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-test",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_anthropic:ChatAnthropic"
        assert entry["model"] == "claude-haiku-4-5"
        assert entry["api_key"] == "sk-test"
        assert entry["name"] == "main"
        assert entry["supports_thinking"] is False

    def test_openai_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-openai",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"
        assert entry["supports_thinking"] is False

    def test_openai_compatible_non_thinking(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "glm-4",
            "api_key": "sk-glm",
            "ai_base_url": "https://api.zhipu.ai/v4",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"
        assert entry["base_url"] == "https://api.zhipu.ai/v4"

    def test_unknown_provider_defaults_to_openai(self):
        entry = build_model_entry({
            "ai_provider": "unknown_vendor",
            "ai_model_id": "some-model",
            "api_key": "sk-x",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"


class TestThinkingClassOverrides:
    def test_deepseek_thinking_uses_patched_class(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "deepseek-r1",
            "api_key": "sk-ds",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_deepseek:PatchedChatDeepSeek"
        assert entry["supports_thinking"] is True

    def test_openai_thinking_uses_patched_openai(self):
        """Must use PatchedChatOpenAI, NOT ReasoningChatOpenAI (bug fix)."""
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "o1-preview",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_openai:PatchedChatOpenAI"
        assert "ReasoningChatOpenAI" not in entry["use"]

    def test_openai_compatible_thinking_uses_patched_openai(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "qwen3-235b",
            "api_key": "sk-qw",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_openai:PatchedChatOpenAI"

    def test_anthropic_thinking_uses_standard_class(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "langchain_anthropic:ChatAnthropic"
        assert entry["supports_thinking"] is True


class TestThinkingConfig:
    def test_deepseek_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "deepseek-r1",
            "api_key": "sk-ds",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {"extra_body": {"thinking": {"type": "enabled"}}}
        assert entry["when_thinking_disabled"] == {"extra_body": {"thinking": {"type": "disabled"}}}

    def test_openai_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "o1-preview",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {"extra_body": {"enable_thinking": True}}
        assert entry["when_thinking_disabled"] == {"extra_body": {"enable_thinking": False}}

    def test_anthropic_thinking_config(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {"thinking": {"type": "enabled", "budget_tokens": 10000}}
        assert entry["when_thinking_disabled"] == {"thinking": {"type": "disabled"}}

    def test_no_thinking_config_when_not_supported(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation"],
        })
        assert "when_thinking_enabled" not in entry
        assert "when_thinking_disabled" not in entry


class TestBaseUrlHandling:
    def test_includes_base_url_when_provided(self):
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "glm-4",
            "api_key": "sk-glm",
            "ai_base_url": "https://api.example.com/v1",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["base_url"] == "https://api.example.com/v1"

    def test_omits_base_url_when_empty(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-x",
            "model_1_capabilities": ["text_generation"],
        })
        assert "base_url" not in entry

    def test_omits_base_url_when_none(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-x",
            "ai_base_url": None,
            "model_1_capabilities": ["text_generation"],
        })
        assert "base_url" not in entry


class TestLegacyThinkingFlag:
    def test_legacy_thinking_supported_true(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "thinking_supported": True,
        })
        assert entry["supports_thinking"] is True
        assert "when_thinking_enabled" in entry

    def test_legacy_thinking_supported_false(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "thinking_supported": False,
        })
        assert entry["supports_thinking"] is False

    def test_model_1_capabilities_takes_precedence_over_legacy(self):
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-haiku-4-5",
            "api_key": "sk-ant",
            "thinking_supported": True,
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["supports_thinking"] is False


class TestMissingModelId:
    def test_raises_on_missing_model_id(self):
        with pytest.raises(ValueError, match="ai_model_id"):
            build_model_entry({
                "ai_provider": "openai",
                "api_key": "sk-x",
                "model_1_capabilities": ["text_generation"],
            })

    def test_raises_on_empty_model_id(self):
        with pytest.raises(ValueError, match="ai_model_id"):
            build_model_entry({
                "ai_provider": "openai",
                "ai_model_id": "",
                "api_key": "sk-x",
                "model_1_capabilities": ["text_generation"],
            })
