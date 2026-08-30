"""Tests for llm_json_repair — validators and generic repair loop."""

from __future__ import annotations

import asyncio

import pytest

from apps.agent.services.runtime.llm_json_repair import (
    extract_coach_snapshot_ids,
    filter_coach_suggestions_by_ids,
    run_json_repair_loop,
    validate_coach_json,
    validate_health_report_json,
    validate_import_parse_json,
    validate_report_json,
    validate_suggestions,
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
# extract_coach_snapshot_ids / filter_coach_suggestions_by_ids
# ---------------------------------------------------------------------------


class TestCoachSnapshotIdFiltering:
    """Anti-hallucination: sanitise suggestions with fabricated target_id."""

    SNAPSHOT = {
        "currency": "CNY",
        "net_worth": 500000.0,
        "total_liabilities": 100000.0,
        "high_interest_debts": [{"id": "111", "category": "credit_card", "rate": 18.0, "monthly_interest": 1500.0}],
        "idle_assets": [{"id": "222", "category": "cash", "daily_cost": 50.0}],
        "top_daily_cost_assets": [{"id": "333", "category": "vehicle", "daily_cost": 120.0}],
        "wishes": [{"id": "444", "price": 30000.0, "saved": 5000.0, "monthly_saving": 2000.0}],
    }

    def _make_suggestion(self, target_id: str, target_type: str = "liability") -> dict:
        return {
            "id": "s1",
            "severity": "high",
            "title": "Test",
            "action": "Test action",
            "target_type": target_type,
            "target_id": target_id,
            "cta_label": "查看",
        }

    def test_extract_ids_from_snapshot_json(self):
        import json
        ids = extract_coach_snapshot_ids(json.dumps(self.SNAPSHOT))
        assert ids == {"111", "222", "333", "444"}

    def test_extract_ids_empty_on_garbage(self):
        assert extract_coach_snapshot_ids("not json") == set()
        assert extract_coach_snapshot_ids("") == set()
        assert extract_coach_snapshot_ids(None) == set()  # type: ignore[arg-type]

    def test_extract_ids_empty_on_non_dict_json(self):
        assert extract_coach_snapshot_ids("[1,2,3]") == set()

    def test_filter_sanitises_hallucinated_ids(self):
        """Hallucinated target_id is cleared; target_type is preserved for list-tab fallback."""
        valid_ids = {"111", "222", "333", "444"}
        data = {
            "suggestions": [
                self._make_suggestion("111"),   # real — kept as-is
                self._make_suggestion("999"),   # hallucinated — target_id cleared
                self._make_suggestion("222", "asset"),  # real — kept as-is
            ]
        }
        result, count = filter_coach_suggestions_by_ids(data, valid_ids)
        assert count == 1
        # All 3 suggestions are kept (not dropped).
        assert len(result["suggestions"]) == 3
        # Hallucinated one has target_id cleared but target_type preserved.
        sanited = result["suggestions"][1]
        assert sanited["target_id"] == ""
        assert sanited["target_type"] == "liability"  # kept for list-tab nav
        assert sanited["title"] == "Test"   # text preserved
        # Valid ones unchanged.
        assert result["suggestions"][0]["target_id"] == "111"
        assert result["suggestions"][2]["target_id"] == "222"

    def test_filter_noop_when_valid_ids_empty(self):
        """Empty valid_ids means we can't filter — pass through unchanged."""
        data = {"suggestions": [self._make_suggestion("999")]}
        result, count = filter_coach_suggestions_by_ids(data, set())
        assert count == 0
        assert result is data  # same object, no copy

    def test_filter_all_valid_noop(self):
        valid_ids = {"111"}
        data = {"suggestions": [self._make_suggestion("111")]}
        result, count = filter_coach_suggestions_by_ids(data, valid_ids)
        assert count == 0
        assert result is data

    def test_filter_empty_suggestions(self):
        valid_ids = {"111"}
        data = {"suggestions": []}
        result, count = filter_coach_suggestions_by_ids(data, valid_ids)
        assert count == 0

    def test_filter_does_not_mutate_original(self):
        valid_ids = {"111"}
        original_suggestions = [
            self._make_suggestion("111"),
            self._make_suggestion("999"),
        ]
        data = {"suggestions": original_suggestions}
        result, count = filter_coach_suggestions_by_ids(data, valid_ids)
        assert count == 1
        # Original list unchanged (still 2 items, original target_id intact).
        assert len(data["suggestions"]) == 2
        assert data["suggestions"][1]["target_id"] == "999"
        # New dict has sanitised list (same length, bad target_id cleared, target_type kept).
        assert len(result["suggestions"]) == 2
        assert result["suggestions"][1]["target_id"] == ""
        assert result["suggestions"][1]["target_type"] == "liability"


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


# ---------------------------------------------------------------------------
# New validators: import-parse, suggestions, health-report
# ---------------------------------------------------------------------------


class TestValidateImportParseJson:
    """import-parse schema validation."""

    def test_valid_data(self):
        data = {
            "source": "test doc",
            "report_date": "2026-01-01",
            "items": [{"name": "Stock A", "current_value": 10000}],
        }
        assert validate_import_parse_json(data) == []

    def test_missing_source(self):
        data = {"items": [{"name": "A"}]}
        errors = validate_import_parse_json(data)
        assert any("source" in e for e in errors)

    def test_empty_items(self):
        data = {"source": "doc", "items": []}
        errors = validate_import_parse_json(data)
        assert any("items" in e and "空" in e for e in errors)

    def test_item_missing_name(self):
        data = {"source": "doc", "items": [{"current_value": 100}]}
        errors = validate_import_parse_json(data)
        assert any("name" in e for e in errors)

    def test_non_dict_input(self):
        assert validate_import_parse_json(None) != []
        assert validate_import_parse_json("str") != []


class TestValidateSuggestions:
    """suggestions schema validation."""

    def test_valid_array(self):
        assert validate_suggestions(["q1", "q2", "q3"]) == []

    def test_wrapped_in_dict(self):
        assert validate_suggestions({"suggestions": ["a", "b"]}) == []

    def test_empty_array(self):
        errors = validate_suggestions([])
        assert len(errors) > 0

    def test_non_string_item(self):
        errors = validate_suggestions(["ok", 123, "ok"])
        assert any("非空字符串" in e for e in errors)

    def test_too_long_string(self):
        errors = validate_suggestions(["ok", "x" * 81, "ok"])
        assert any("过长" in e for e in errors)

    def test_not_a_list(self):
        assert validate_suggestions("not a list") != []
        assert validate_suggestions(None) != []


class TestValidateHealthReportJson:
    """health-report schema validation."""

    def _valid_data(self) -> dict:
        section = {"score": 4, "narrative": "Analysis text", "suggestions": ["tip"]}
        return {
            "net_worth_health": section,
            "allocation_analysis": section,
            "liability_pressure": section,
            "asset_efficiency": section,
            "overall_score": 80,
            "summary": "Summary text",
        }

    def test_valid_data(self):
        assert validate_health_report_json(self._valid_data()) == []

    def test_missing_section(self):
        data = self._valid_data()
        del data["net_worth_health"]
        errors = validate_health_report_json(data)
        assert any("net_worth_health" in e for e in errors)

    def test_score_out_of_range(self):
        data = self._valid_data()
        data["net_worth_health"]["score"] = 10
        errors = validate_health_report_json(data)
        assert any("1-5" in e for e in errors)

    def test_empty_narrative(self):
        data = self._valid_data()
        data["allocation_analysis"]["narrative"] = ""
        errors = validate_health_report_json(data)
        assert any("narrative" in e for e in errors)

    def test_overall_score_out_of_range(self):
        data = self._valid_data()
        data["overall_score"] = 5
        errors = validate_health_report_json(data)
        assert any("overall_score" in e for e in errors)

    def test_non_dict_input(self):
        assert validate_health_report_json(None) != []
        assert validate_health_report_json([]) != []
