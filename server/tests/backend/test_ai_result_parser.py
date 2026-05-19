"""Tests for AI result parser service."""

import pytest

from apps.backend.app.services.ai_result_parser import (
    _extract_bare_json,
    _extract_structured_block,
    _validate_json,
    parse_capability_result,
)


class TestExtractStructuredBlock:
    """Tests for _extract_structured_block — returns (block, method) tuple."""

    def test_extract_html_comment_carrier(self):
        answer = """
        Here is my analysis...

        <!-- STRUCTURED_DATA
        [{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]
        -->
        """
        block, method = _extract_structured_block(answer)
        assert block == '[{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]'
        assert method == "regex_html"

    def test_extract_missing_delimiter_falls_through(self):
        answer = "Just plain text without structured data"
        block, method = _extract_structured_block(answer)
        assert block is None
        assert method == "regex_failed"

    def test_extract_empty_html_block(self):
        answer = "<!-- STRUCTURED_DATA -->"
        block, method = _extract_structured_block(answer)
        # Empty content matches HTML carrier first
        assert block == ""
        assert method == "regex_html"

    def test_extract_multiline_json_in_html(self):
        answer = """
        <!-- STRUCTURED_DATA
        {
          "overall_score": 85,
          "narrative": "Good health"
        }
        -->
        """
        block, method = _extract_structured_block(answer)
        assert block is not None and "overall_score" in block
        assert method == "regex_html"

    def test_extract_json_fence_carrier(self):
        answer = """Some narrative text.

```json
[{"asset_name": "Bike", "alert_type": "aging", "severity": "low"}]
```

End of analysis."""
        block, method = _extract_structured_block(answer)
        assert block is not None
        assert "Bike" in block
        assert method == "regex_fence"

    def test_extract_json_fence_object(self):
        answer = """Report:

```json
{"has_significant_drift": false, "narrative": "stable"}
```
"""
        block, method = _extract_structured_block(answer)
        assert block is not None
        assert "has_significant_drift" in block
        assert method == "regex_fence"

    def test_extract_bare_json_array(self):
        answer = 'Final answer: [{"asset_name": "Phone", "alert_type": "idle_cost", "severity": "medium"}]'
        block, method = _extract_structured_block(answer)
        assert block is not None
        assert "Phone" in block
        assert method == "regex_bare"

    def test_extract_bare_json_object(self):
        answer = 'My summary follows. {"has_significant_drift": true, "narrative": "drift detected"}'
        block, method = _extract_structured_block(answer)
        assert block is not None
        assert "has_significant_drift" in block
        assert method == "regex_bare"

    def test_html_takes_priority_over_fence(self):
        answer = """
        ```json
        [{"x": 1}]
        ```
        <!-- STRUCTURED_DATA
        [{"asset_name": "Real", "alert_type": "aging", "severity": "high"}]
        -->
        """
        block, method = _extract_structured_block(answer)
        assert "Real" in block
        assert method == "regex_html"

    def test_fence_takes_priority_over_bare(self):
        answer = """
        ```json
        [{"asset_name": "Fence", "alert_type": "aging", "severity": "high"}]
        ```
        Trailing data: [{"asset_name": "Bare", "alert_type": "aging", "severity": "low"}]
        """
        block, method = _extract_structured_block(answer)
        assert "Fence" in block
        assert method == "regex_fence"

    def test_bare_balanced_with_string_containing_brace(self):
        # `}` inside a string literal must not break depth count
        answer = 'analysis {"x": "value with } inside", "y": 1}'
        block, method = _extract_structured_block(answer)
        assert block is not None
        assert method == "regex_bare"
        assert '"value with } inside"' in block

    def test_no_carrier_at_all(self):
        block, method = _extract_structured_block("plain prose with no JSON whatsoever")
        assert block is None
        assert method == "regex_failed"


class TestExtractBareJson:
    def test_simple_array(self):
        assert _extract_bare_json("text [1, 2, 3]") == "[1, 2, 3]"

    def test_simple_object(self):
        assert _extract_bare_json('text {"a": 1}') == '{"a": 1}'

    def test_nested(self):
        assert _extract_bare_json('text {"a": [1, 2], "b": {"c": 3}}') == '{"a": [1, 2], "b": {"c": 3}}'

    def test_unbalanced_returns_none(self):
        assert _extract_bare_json("text {unbalanced") is None

    def test_empty_returns_none(self):
        assert _extract_bare_json("") is None
        assert _extract_bare_json("plain text only") is None

    def test_string_with_escaped_quote(self):
        # Escaped quote should not toggle string state
        result = _extract_bare_json(r'data {"a": "he said \"hi\"", "b": 2}')
        assert result == r'{"a": "he said \"hi\"", "b": 2}'


class TestValidateJson:
    """Tests for _validate_json schema validation (unchanged from existing behavior)."""

    def test_validate_array_type_valid(self):
        data = [{"asset_name": "Car", "alert_type": "aging", "severity": "high"}]
        assert _validate_json(data, "alerts") is True

    def test_validate_array_type_missing_required(self):
        data = [{"asset_name": "Car"}]
        assert _validate_json(data, "alerts") is False

    def test_validate_array_type_not_array(self):
        data = {"asset_name": "Car"}
        assert _validate_json(data, "alerts") is False

    def test_validate_object_type_valid(self):
        data = {"has_significant_drift": True, "narrative": "Some drift"}
        assert _validate_json(data, "allocation") is True

    def test_validate_object_type_missing_required(self):
        data = {"narrative": "Some text"}
        assert _validate_json(data, "allocation") is False

    def test_validate_object_type_not_object(self):
        data = [{"has_significant_drift": True}]
        assert _validate_json(data, "allocation") is False

    def test_validate_unknown_capability(self):
        data = {"anything": "value"}
        assert _validate_json(data, "unknown_capability") is True


class TestParseCapabilityResult:
    """Tests for parse_capability_result — returns (data, method) tuple."""

    async def test_parse_valid_alerts_html(self, db_session, test_family):
        answer = """
        Analysis complete.

        <!-- STRUCTURED_DATA
        [{"asset_name": "Car", "alert_type": "aging", "severity": "high", "suggestion": "Replace soon"}]
        -->
        """
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is not None
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["asset_name"] == "Car"
        assert method == "regex_html"

    async def test_parse_valid_allocation(self, db_session, test_family):
        answer = """
        <!-- STRUCTURED_DATA
        {"has_significant_drift": true, "drifts": [{"category": "stocks", "drift": 5.2}]}
        -->
        """
        data, method = await parse_capability_result("allocation", answer, test_family.id, db_session)
        assert data is not None
        assert isinstance(data, dict)
        assert data["has_significant_drift"] is True
        assert method == "regex_html"

    async def test_parse_via_fence(self, db_session, test_family):
        answer = """Analysis:

```json
[{"asset_name": "Bike", "alert_type": "aging", "severity": "low"}]
```
"""
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is not None
        assert method == "regex_fence"

    async def test_parse_via_bare(self, db_session, test_family):
        answer = 'Done: [{"asset_name": "X", "alert_type": "aging", "severity": "medium"}]'
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is not None
        assert method == "regex_bare"

    async def test_parse_missing_block_returns_failed(self, db_session, test_family):
        answer = "No structured data here"
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is None
        assert method == "failed"

    async def test_parse_invalid_json_returns_failed(self, db_session, test_family):
        answer = """
        <!-- STRUCTURED_DATA
        {not valid json}
        -->
        """
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is None
        assert method == "failed"

    async def test_parse_schema_mismatch_returns_failed(self, db_session, test_family):
        answer = """
        <!-- STRUCTURED_DATA
        [{"asset_name": "Car"}]
        -->
        """
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is None
        assert method == "failed"


class TestLLMFallback:
    """Tests for LLM fallback path — patches _call_llm to return scripted text."""

    async def test_no_provider_returns_failed(self, db_session, test_family):
        # No AIProviderConfig in DB → fallback returns None → method='failed'
        answer = "narrative only, no JSON anywhere"
        data, method = await parse_capability_result("alerts", answer, test_family.id, db_session)
        assert data is None
        assert method == "failed"

    async def test_fallback_hit_when_regex_fails(self, db_session, test_family, monkeypatch):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="test-provider",
            provider="openai",
            api_key_encrypted="dummy-encrypted",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()

        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def fake_call(*args, **kwargs):
            return '[{"asset_name": "FromLLM", "alert_type": "aging", "severity": "high"}]'

        monkeypatch.setattr(ai_result_parser, "_call_llm", fake_call)

        answer = "Some prose with no STRUCTURED_DATA block at all, no fence, just words."
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert method == "llm_fallback_hit"
        assert data == [{"asset_name": "FromLLM", "alert_type": "aging", "severity": "high"}]

    async def test_fallback_with_markdown_fence_wrapping(
        self, db_session, test_family, monkeypatch
    ):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="e",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def fake_call(*args, **kwargs):
            return '```json\n[{"asset_name": "Y", "alert_type": "aging", "severity": "low"}]\n```'

        monkeypatch.setattr(ai_result_parser, "_call_llm", fake_call)

        answer = "narrative without structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert method == "llm_fallback_hit"
        assert data[0]["asset_name"] == "Y"

    async def test_fallback_timeout_returns_failed(
        self, db_session, test_family, monkeypatch
    ):
        import asyncio

        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="e",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def slow_call(*args, **kwargs):
            await asyncio.sleep(10)
            return "[]"

        monkeypatch.setattr(ai_result_parser, "_call_llm", slow_call)
        monkeypatch.setattr(ai_result_parser, "LLM_FALLBACK_TIMEOUT_SECONDS", 0.1)

        answer = "no structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert data is None
        assert method == "failed"

    async def test_fallback_invalid_json_returns_failed(
        self, db_session, test_family, monkeypatch
    ):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="e",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def fake_call(*args, **kwargs):
            return "this is not valid JSON {{ broken"

        monkeypatch.setattr(ai_result_parser, "_call_llm", fake_call)

        answer = "no structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert data is None
        assert method == "failed"

    async def test_fallback_schema_mismatch_returns_failed(
        self, db_session, test_family, monkeypatch
    ):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="e",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        async def fake_call(*args, **kwargs):
            # Missing required keys for alerts
            return '[{"asset_name": "X"}]'

        monkeypatch.setattr(ai_result_parser, "_call_llm", fake_call)

        answer = "no structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert data is None
        assert method == "failed"

    async def test_fallback_api_key_decrypt_fails(
        self, db_session, test_family, monkeypatch
    ):
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="bad",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()

        # decrypt returns falsy → bail early
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "")

        answer = "no structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert data is None
        assert method == "failed"

    async def test_fallback_call_args_max_tokens_and_temperature(
        self, db_session, test_family, monkeypatch
    ):
        """Verify max_tokens=800 / temperature=0.1 are actually passed."""
        from apps.backend.app.models.ai_provider_config import AIProviderConfig
        from apps.backend.app.services import ai_result_parser
        from apps.backend.app.utils.snowflake import next_id

        cfg = AIProviderConfig(
            id=next_id(),
            family_id=test_family.id,
            name="t",
            provider="openai",
            api_key_encrypted="e",
            model_id="gpt-4o-mini",
            is_active=True,
            display_order=1,
        )
        db_session.add(cfg)
        db_session.commit()
        monkeypatch.setattr(ai_result_parser, "decrypt_api_key", lambda _: "sk-fake")

        # Inspect the values passed into the AsyncOpenAI client
        captured: dict = {}

        class FakeChat:
            class FakeCompletions:
                async def create(self, **kwargs):
                    captured.update(kwargs)

                    class Msg:
                        content = '[{"asset_name": "Z", "alert_type": "aging", "severity": "low"}]'

                    class Choice:
                        message = Msg()

                    class Resp:
                        choices = [Choice()]

                    return Resp()

            completions = FakeCompletions()

        class FakeOpenAI:
            def __init__(self, **kwargs):
                pass

            chat = FakeChat()

            async def close(self):
                pass

        # Patch the dynamic import inside _call_llm
        import sys
        import types

        fake_module = types.ModuleType("openai")
        fake_module.AsyncOpenAI = FakeOpenAI
        monkeypatch.setitem(sys.modules, "openai", fake_module)

        answer = "no structured block"
        data, method = await parse_capability_result(
            "alerts", answer, test_family.id, db_session
        )
        assert method == "llm_fallback_hit"
        assert captured["max_tokens"] == 800
        assert captured["temperature"] == 0.1
        assert captured["model"] == "gpt-4o-mini"
