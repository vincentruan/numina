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

    def test_openai_thinking_uses_stock_chatopenai(self):
        """Native OpenAI (no base_url) uses stock ChatOpenAI. The reasoning
        is delivered via the Responses API + supports_reasoning_effort, not
        via vendor reasoning_content streams that need a patched class."""
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-5",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "langchain_openai:ChatOpenAI"
        assert "PatchedChatOpenAI" not in entry["use"]
        assert "ReasoningChatOpenAI" not in entry["use"]

    def test_openai_with_base_url_uses_patched_openai(self):
        """OpenAI-compatible gateway (custom base_url) needs the patched class
        to capture reasoning_content from vendor-specific streaming deltas."""
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "qwen3-32b",
            "api_key": "sk-x",
            "ai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["use"] == "deerflow.models.patched_openai:PatchedChatOpenAI"

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

    def test_openai_thinking_config_emits_top_level_reasoning_effort(self):
        """Replaces obsolete extra_body.enable_thinking on native OpenAI.

        Native OpenAI (gpt-5/o-series) does NOT accept the vendor-extension
        enable_thinking flag — it uses top-level reasoning_effort which
        DeerFlow harness emits when supports_reasoning_effort is set.
        """
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-5",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert "extra_body" not in entry.get("when_thinking_enabled", {})
        assert entry["when_thinking_enabled"] == {"reasoning_effort": "high"}
        assert entry["when_thinking_disabled"] == {"reasoning_effort": "low"}

    def test_native_openai_thinking_config_responses_api(self):
        """Native OpenAI emits supports_reasoning_effort + top-level
        reasoning_effort. DeerFlow harness translates to reasoning.effort
        when use_responses_api is also set."""
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-5",
            "api_key": "sk-o1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["supports_reasoning_effort"] is True
        assert entry["when_thinking_enabled"] == {"reasoning_effort": "high"}
        assert entry["when_thinking_disabled"] == {"reasoning_effort": "low"}
        # Native OpenAI also opts into Responses API.
        assert entry["use_responses_api"] is True
        assert entry["output_version"] == "responses/v1"

    def test_openai_compatible_gateway_thinking_config(self):
        """OpenAI-compatible gateways keep extra_body.enable_thinking vendor extension."""
        entry = build_model_entry({
            "ai_provider": "openai_compatible",
            "ai_model_id": "qwen3-32b",
            "api_key": "sk-qw",
            "ai_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {"extra_body": {"enable_thinking": True}}
        assert entry["when_thinking_disabled"] == {"extra_body": {"enable_thinking": False}}
        # OpenAI-compatible gateways do NOT opt into Responses API.
        assert "use_responses_api" not in entry
        assert "output_version" not in entry

    def test_anthropic_thinking_config_dynamic_budget(self):
        """Anthropic budget_tokens is computed as fraction of resolved max_tokens.
        claude-sonnet-4-6 → yaml prefix 'claude-sonnet-4' → 64000 * 0.60 = 38400."""
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {
            "thinking": {"type": "enabled", "budget_tokens": 38400}
        }
        assert entry["when_thinking_disabled"] == {"thinking": {"type": "disabled"}}

    def test_anthropic_explicit_max_tokens_overrides_yaml(self):
        """User-set max_tokens in DB overrides yaml prefix lookup; budget recomputed."""
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "claude-sonnet-4-6",
            "api_key": "sk-ant",
            "max_tokens": 8192,
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["max_tokens"] == 8192
        # 8192 * 0.60 = 4915, > 1024 floor → enabled with this budget
        assert entry["when_thinking_enabled"] == {
            "thinking": {"type": "enabled", "budget_tokens": 4915}
        }

    def test_anthropic_too_small_max_tokens_falls_back_to_disabled(self):
        """When max_tokens is too small to satisfy budget>=1024, both branches
        emit thinking.type=disabled (graceful degrade, no API error)."""
        entry = build_model_entry({
            "ai_provider": "anthropic",
            "ai_model_id": "some-tiny-model",
            "api_key": "sk-ant",
            "max_tokens": 1500,  # 1500 * 0.60 = 900 < 1024 floor → None
            "model_1_capabilities": ["text_generation", "deep_thinking"],
        })
        assert entry["when_thinking_enabled"] == {"thinking": {"type": "disabled"}}
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


# ── Pure helper tests ──────────────────────────────────────────────


class TestComputeAnthropicThinkingBudget:
    """Unit tests for _compute_anthropic_thinking_budget arithmetic."""

    def test_normal_path_64k(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # 64000 * 0.60 = 38400, capped to min(38400, 64000-256)=38400
        assert _compute_anthropic_thinking_budget(64000, 0.60) == 38400

    def test_normal_path_8k(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # 8192 * 0.60 = 4915
        assert _compute_anthropic_thinking_budget(8192, 0.60) == 4915

    def test_normal_path_4k(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # DeerFlow Sonnet 4.6 example default
        assert _compute_anthropic_thinking_budget(4096, 0.60) == 2457

    def test_haiku_tight_2k(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # 2048 * 0.60 = 1228, capped to min(1228, 2048-256)=1228, >= 1024 ✓
        assert _compute_anthropic_thinking_budget(2048, 0.60) == 1228

    def test_under_min_floor_returns_none(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # 1500 * 0.60 = 900, capped to min(900, 1244)=900, < 1024 → None
        assert _compute_anthropic_thinking_budget(1500, 0.60) is None

    def test_zero_max_tokens_returns_none(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        assert _compute_anthropic_thinking_budget(0, 0.60) is None

    def test_negative_max_tokens_returns_none(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        assert _compute_anthropic_thinking_budget(-1, 0.60) is None

    def test_zero_fraction_returns_none(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        assert _compute_anthropic_thinking_budget(64000, 0.0) is None

    def test_negative_fraction_returns_none(self):
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        assert _compute_anthropic_thinking_budget(64000, -0.5) is None

    def test_headroom_caps_high_fraction(self):
        """When raw > max_tokens-headroom, the cap kicks in."""
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # 1000 * 0.99 = 990, capped to min(990, 1000-256)=744, < 1024 → None
        # Use larger numbers to test the cap doesn't trip the floor:
        # 4096 * 0.99 = 4055, capped to min(4055, 3840)=3840
        assert _compute_anthropic_thinking_budget(4096, 0.99) == 3840

    def test_exact_min_floor(self):
        """budget = exactly 1024 should return 1024 (>=, not >)."""
        from packages.core.model_entry import _compute_anthropic_thinking_budget
        # We need max_tokens such that floor(max*frac) == 1024 AND
        # min(1024, max-256) == 1024, i.e. max >= 1280.
        # 1707 * 0.60 = 1024 exact (1707*0.6=1024.2 → 1024 with int)
        # min(1024, 1707-256)=1024, >= 1024 ✓
        assert _compute_anthropic_thinking_budget(1707, 0.60) == 1024


class TestResolveMaxTokens:
    """Unit tests for _resolve_max_tokens three-tier priority."""

    def test_explicit_user_value_wins(self):
        from packages.core.model_entry import _resolve_max_tokens
        assert _resolve_max_tokens({
            "max_tokens": 2048,
            "ai_model_id": "gpt-5",
        }) == 2048

    def test_yaml_default_when_no_explicit(self):
        from packages.core.model_entry import _resolve_max_tokens
        # gpt-5 prefix in system-config.yaml → 128000
        assert _resolve_max_tokens({"ai_model_id": "gpt-5"}) == 128000

    def test_negative_explicit_falls_back_to_yaml(self):
        from packages.core.model_entry import _resolve_max_tokens
        assert _resolve_max_tokens({
            "max_tokens": -1,
            "ai_model_id": "gpt-5",
        }) == 128000

    def test_zero_explicit_falls_back_to_yaml(self):
        from packages.core.model_entry import _resolve_max_tokens
        assert _resolve_max_tokens({
            "max_tokens": 0,
            "ai_model_id": "gpt-5",
        }) == 128000

    def test_unknown_model_returns_none(self):
        from packages.core.model_entry import _resolve_max_tokens
        assert _resolve_max_tokens({"ai_model_id": "some-unknown-fine-tune"}) is None

    def test_empty_model_id_returns_none(self):
        from packages.core.model_entry import _resolve_max_tokens
        assert _resolve_max_tokens({"ai_model_id": ""}) is None
        assert _resolve_max_tokens({}) is None


class TestMaxTokensEmission:
    """build_model_entry should emit max_tokens key when resolved."""

    def test_explicit_user_max_tokens_emitted(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-4o",
            "api_key": "sk-x",
            "max_tokens": 8192,
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["max_tokens"] == 8192

    def test_yaml_default_emitted_when_no_explicit(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "gpt-5-mini",
            "api_key": "sk-x",
            "model_1_capabilities": ["text_generation"],
        })
        assert entry["max_tokens"] == 128000

    def test_unknown_model_no_max_tokens_key(self):
        entry = build_model_entry({
            "ai_provider": "openai",
            "ai_model_id": "my-private-model-v1",
            "api_key": "sk-x",
            "ai_base_url": "https://internal.example.com/v1",
            "model_1_capabilities": ["text_generation"],
        })
        assert "max_tokens" not in entry
