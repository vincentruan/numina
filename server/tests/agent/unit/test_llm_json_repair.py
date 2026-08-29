"""Tests for llm_json_repair — validators and generic repair loop."""

from __future__ import annotations

import asyncio

import pytest

from apps.agent.services.runtime.llm_json_repair import (
    run_json_repair_loop,
    validate_coach_json,
    validate_report_json,
    validate_wish_advice_json,
)

# ---------------------------------------------------------------------------
# validate_wish_advice_json
# ---------------------------------------------------------------------------


class TestValidateWishAdviceJson:
    """wish-advice schema validation (W4 advice contract)."""

    def _valid_data(self) -> dict:
        return {
            "primary_wish_id": "1234567890",
            "reason": "目标日期临近，缺口较大",
            "suggested_monthly": 2500,
            "redistribution": [
                {"wish_id": "1234567890", "suggested_amount": 2000, "note": "优先加速"},
                {"wish_id": "9876543210", "suggested_amount": 500, "note": "维持现有"},
            ],
        }

    def test_valid_data_returns_empty(self):
        assert validate_wish_advice_json(self._valid_data()) == []

    def test_empty_redistribution_is_valid(self):
        data = {
            "primary_wish_id": "",
            "reason": "数据不足",
            "suggested_monthly": 0,
            "redistribution": [],
        }
        assert validate_wish_advice_json(data) == []

    def test_missing_primary_wish_id(self):
        data = self._valid_data()
        del data["primary_wish_id"]
        errors = validate_wish_advice_json(data)
        assert any("primary_wish_id" in e for e in errors)

    def test_missing_reason(self):
        data = self._valid_data()
        del data["reason"]
        errors = validate_wish_advice_json(data)
        assert any("reason" in e for e in errors)

    def test_missing_suggested_monthly(self):
        data = self._valid_data()
        del data["suggested_monthly"]
        errors = validate_wish_advice_json(data)
        assert any("suggested_monthly" in e for e in errors)

    def test_negative_suggested_monthly(self):
        data = self._valid_data()
        data["suggested_monthly"] = -100
        errors = validate_wish_advice_json(data)
        assert any("suggested_monthly" in e and "≥ 0" in e for e in errors)

    def test_non_numeric_suggested_monthly(self):
        data = self._valid_data()
        data["suggested_monthly"] = "not a number"
        errors = validate_wish_advice_json(data)
        assert any("suggested_monthly" in e and "数字" in e for e in errors)

    def test_missing_redistribution(self):
        data = self._valid_data()
        del data["redistribution"]
        errors = validate_wish_advice_json(data)
        assert any("redistribution" in e for e in errors)

    def test_redistribution_not_a_list(self):
        data = self._valid_data()
        data["redistribution"] = "not a list"
        errors = validate_wish_advice_json(data)
        assert any("redistribution" in e and "数组" in e for e in errors)

    def test_redistribution_item_missing_wish_id(self):
        data = self._valid_data()
        data["redistribution"][0] = {"suggested_amount": 100, "note": "no wish_id"}
        errors = validate_wish_advice_json(data)
        assert any("wish_id" in e for e in errors)

    def test_redistribution_item_negative_amount(self):
        data = self._valid_data()
        data["redistribution"][0]["suggested_amount"] = -50
        errors = validate_wish_advice_json(data)
        assert any("suggested_amount" in e and "≥ 0" in e for e in errors)

    def test_redistribution_item_non_numeric_amount(self):
        data = self._valid_data()
        data["redistribution"][0]["suggested_amount"] = "abc"
        errors = validate_wish_advice_json(data)
        assert any("suggested_amount" in e and "数字" in e for e in errors)

    def test_non_dict_input(self):
        assert validate_wish_advice_json("not a dict") != []  # type: ignore[arg-type]
        assert validate_wish_advice_json(None) != []
        assert validate_wish_advice_json(42) != []  # type: ignore[arg-type]

    def test_empty_dict(self):
        errors = validate_wish_advice_json({})
        # Should report missing required fields
        assert (
            len(errors) >= 4
        )  # primary_wish_id, reason, suggested_monthly, redistribution


# ---------------------------------------------------------------------------
# Smoke tests for moved validators (verify they work after move)
# ---------------------------------------------------------------------------


class TestMovedValidators:
    """Smoke tests: validate_report_json and validate_coach_json still work after move."""

    def test_validate_report_json_valid(self):
        data = {
            "indicators": [
                {
                    "key": "test",
                    "label": "Test",
                    "score": 3,
                    "narrative": "narrative",
                    "data": {
                        "items": [{"key": "a", "zh": "A", "en": "A", "value": 50}]
                    },
                }
            ]
        }
        assert validate_report_json(data) == []

    def test_validate_coach_json_valid(self):
        data = {
            "suggestions": [
                {
                    "id": "1",
                    "severity": "high",
                    "title": "Title",
                    "action": "Action",
                    "target_type": "liability",
                    "target_id": "123",
                    "cta_label": "查看",
                }
            ]
        }
        assert validate_coach_json(data) == []

    def test_validate_coach_json_empty_suggestions(self):
        assert validate_coach_json({"suggestions": []}) == []

    def test_validate_coach_json_invalid_severity(self):
        data = {
            "suggestions": [
                {
                    "id": "1",
                    "severity": "critical",  # invalid
                    "title": "Title",
                    "action": "Action",
                    "target_type": "liability",
                    "target_id": "123",
                    "cta_label": "查看",
                }
            ]
        }
        errors = validate_coach_json(data)
        assert any("severity" in e for e in errors)


# ---------------------------------------------------------------------------
# run_json_repair_loop
# ---------------------------------------------------------------------------


class TestRunJsonRepairLoop:
    """Generic validate→repair loop tests."""

    @pytest.mark.asyncio
    async def test_valid_input_no_retries(self):
        """Validator returns empty → loop exits immediately."""
        parsed = {"key": "value"}

        def validator(_d):
            return []

        repair_fn = None  # should not be called
        events_published = []

        async def publish(attempt):
            events_published.append(attempt)

        result, count = await run_json_repair_loop(
            parsed,
            "ai text",
            validator=validator,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
        )
        assert result == parsed
        assert count == 0
        assert events_published == []

    @pytest.mark.asyncio
    async def test_none_input_attempts_repair(self):
        """Parsed is None → repair IS attempted (not skipped).

        When parse_report_json returns None (unparseable output), the repair
        loop should still attempt LLM repair instead of giving up immediately.
        This covers agent recursion limit hits and severely malformed output.
        """
        repaired = {
            "indicators": [
                {
                    "key": "k",
                    "score": 3,
                    "data": {"items": [{"key": "i", "zh": "z", "en": "e", "value": 1}]},
                }
            ]
        }

        async def repair_fn(text, errors):
            return repaired

        events_published = []

        async def publish(attempt):
            events_published.append(attempt)

        result, count = await run_json_repair_loop(
            None,
            "unparseable ai text",
            validator=validate_report_json,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
        )
        assert result is not None
        assert count == 1
        assert len(events_published) == 1  # one retry event published

    @pytest.mark.asyncio
    async def test_none_input_repair_fails_returns_none(self):
        """Parsed is None AND repair fails → return (None, retry_count)."""

        async def repair_fn(text, errors):
            return None

        async def publish(attempt):
            pass

        result, count = await run_json_repair_loop(
            None,
            "garbage",
            validator=validate_report_json,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
        )
        assert result is None
        assert count == 1  # repair was attempted once

    @pytest.mark.asyncio
    async def test_repair_succeeds_on_first_retry(self):
        """Validator fails → repair succeeds → return repaired dict with count=1."""
        parsed = {"bad": "data"}
        repaired = {"good": "data"}
        call_count = 0

        def validator(d):
            if d.get("good"):
                return []
            return ["bad field"]

        async def repair_fn(ai_text, errors):
            nonlocal call_count
            call_count += 1
            return repaired

        async def publish(attempt):
            pass

        result, count = await run_json_repair_loop(
            parsed,
            "ai text",
            validator=validator,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
        )
        assert result == repaired
        assert count == 1
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_all_retries_fail(self):
        """Validator fails and repair keeps returning bad data → exhausts retries."""
        bad_data = {"bad": "data"}

        def validator(d):
            return ["always invalid"]

        async def repair_fn(ai_text, errors):
            return bad_data  # repair returns same bad data

        async def publish(attempt):
            pass

        result, count = await run_json_repair_loop(
            bad_data,
            "ai text",
            validator=validator,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
            max_retries=3,
        )
        assert count == 3  # exhausted all retries

    @pytest.mark.asyncio
    async def test_repair_returns_none_breaks_early(self):
        """Repair returns None → loop breaks, returns last parsed."""
        parsed = {"initial": "data"}

        def validator(d):
            return ["invalid"]

        async def repair_fn(ai_text, errors):
            return None  # repair failed

        async def publish(attempt):
            pass

        result, count = await run_json_repair_loop(
            parsed,
            "ai text",
            validator=validator,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
        )
        assert result == parsed  # original parsed returned
        assert count == 1  # only one attempt before None break

    @pytest.mark.asyncio
    async def test_publish_retry_event_called_per_attempt(self):
        """Retry events are published with correct attempt numbers."""
        parsed = {"bad": "data"}
        attempts = []

        def validator(d):
            return ["invalid"]

        async def repair_fn(ai_text, errors):
            return parsed  # keeps failing

        async def publish(attempt):
            attempts.append(attempt)

        await run_json_repair_loop(
            parsed,
            "ai text",
            validator=validator,
            repair_fn=repair_fn,
            publish_retry_event=publish,
            app_name="test",
            max_retries=2,
        )
        assert attempts == [1, 2]

    @pytest.mark.asyncio
    async def test_timeout(self):
        """Loop respects budget_seconds timeout."""
        parsed = {"bad": "data"}

        def validator(d):
            return ["invalid"]

        async def slow_repair(ai_text, errors):
            await asyncio.sleep(10)
            return parsed

        async def publish(attempt):
            pass

        result, count = await run_json_repair_loop(
            parsed,
            "ai text",
            validator=validator,
            repair_fn=slow_repair,
            publish_retry_event=publish,
            app_name="test",
            max_retries=5,
            budget_seconds=1,
        )
        # Should have timed out before exhausting all retries
        assert count < 5


# ---------------------------------------------------------------------------
# extract_json_via_llm
# ---------------------------------------------------------------------------


class TestExtractJsonViaLlm:
    """Final fallback: standalone LLM JSON extraction."""

    @pytest.mark.asyncio
    async def test_none_provider_returns_none(self):
        from apps.agent.services.runtime.llm_json_repair import extract_json_via_llm

        result = await extract_json_via_llm("text", "prompt", None)
        assert result is None

    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """LLM returns valid JSON → extract_json_via_llm returns parsed dict."""
        from unittest.mock import AsyncMock, patch

        from apps.agent.services.runtime.llm_json_repair import extract_json_via_llm

        valid_json = '{"indicators": [{"key": "k", "score": 3, "data": {"items": [{"key": "i", "zh": "z", "en": "e", "value": 1}]}}]}'
        mock_llm = AsyncMock()
        mock_llm.complete_json = AsyncMock(return_value=valid_json)

        with patch(
            "apps.agent.core.llm.get_llm_client",
            return_value=mock_llm,
        ):
            result = await extract_json_via_llm(
                "some ai text",
                "repair prompt",
                {"ai_provider": "openai", "api_key": "k", "ai_model_id": "m"},
            )
        assert result is not None
        assert "indicators" in result
        mock_llm.complete_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_llm_failure_returns_none(self):
        """LLM call fails → extract_json_via_llm returns None (not raises)."""
        from unittest.mock import AsyncMock, patch

        from apps.agent.services.runtime.llm_json_repair import extract_json_via_llm

        mock_llm = AsyncMock()
        mock_llm.complete_json = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "apps.agent.core.llm.get_llm_client",
            return_value=mock_llm,
        ):
            result = await extract_json_via_llm(
                "text",
                "prompt",
                {"ai_provider": "openai", "api_key": "k", "ai_model_id": "m"},
            )
        assert result is None
