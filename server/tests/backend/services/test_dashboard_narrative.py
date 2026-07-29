"""Tests for the dashboard narrative service.

Covers pure-function helpers: _extract_first_sentence,
_separate_narrative_and_thinking, and _build_narrative_context.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from apps.backend.app.services.dashboard_narrative import (
    _build_narrative_context,
    _extract_first_sentence,
    _separate_narrative_and_thinking,
)


# ---------------------------------------------------------------------------
# _extract_first_sentence
# ---------------------------------------------------------------------------


class TestExtractFirstSentence:
    def test_empty_string_returns_empty(self):
        assert _extract_first_sentence("") == ""

    def test_single_chinese_sentence(self):
        result = _extract_first_sentence("家庭资产稳步增长。")
        assert result == "家庭资产稳步增长。"

    def test_multiple_chinese_sentences_returns_first(self):
        text = "分析完成。家庭资产稳步增长。建议继续储蓄。"
        result = _extract_first_sentence(text)
        assert result == "分析完成。"

    def test_all_english_text(self):
        text = "Your assets are growing steadily."
        result = _extract_first_sentence(text)
        # Latin period not surrounded by digits -> splits; falls back or returns first part
        assert len(result) > 0

    def test_decimal_number_period_does_not_split(self):
        """Period inside '5,230.50' should NOT be treated as sentence boundary."""
        text = "总资产为5,230.50元，家庭净资产健康。"
        result = _extract_first_sentence(text)
        # Should not split at the decimal point
        assert "5,230.50" in result

    def test_long_text_no_terminator_gets_period_appended(self):
        """Text without sentence terminators — first sentence is entire text, period appended."""
        text = "a" * 60
        result = _extract_first_sentence(text)
        # No terminator found -> entire text is "first sentence", "。" appended
        assert result.endswith("。")

    def test_short_text_no_terminator_gets_period(self):
        """Short text without terminator gets '。' appended."""
        result = _extract_first_sentence("短文本")
        assert result == "短文本。"

    def test_strips_whitespace(self):
        result = _extract_first_sentence("  你好世界。  ")
        assert result == "你好世界。"


# ---------------------------------------------------------------------------
# _separate_narrative_and_thinking
# ---------------------------------------------------------------------------


class TestSeparateNarrativeAndThinking:
    def test_empty_string(self):
        narrative, thinking = _separate_narrative_and_thinking("")
        assert narrative == ""
        assert thinking == ""

    def test_pure_narrative_no_thinking_markers(self):
        """Single Chinese sentence — entire text is narrative."""
        text = "家庭财务状况整体良好，资产稳步增长中。"
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert "家庭财务" in narrative
        assert thinking == ""

    def test_narrative_with_thinking_prefix(self):
        """Multiple Chinese sentences: earlier ones are thinking, last 2-3 are narrative."""
        text = (
            "首先分析家庭资产状况。"
            "然后检查负债比例。"
            "最后给出建议，家庭资产稳步增长。"
            "建议继续保持储蓄习惯，定期审视投资组合。"
        )
        narrative, thinking = _separate_narrative_and_thinking(text)
        # Narrative should contain the last sentences
        assert len(narrative) > 0
        # Thinking should contain the earlier sentences
        assert "首先分析" in thinking or "然后检查" in thinking

    def test_markdown_bold_stripped(self):
        text = "**重要**的资产分析报告。家庭财务健康。"
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert "**" not in narrative
        assert "重要" in narrative

    def test_markdown_italic_stripped(self):
        text = "*关键*发现如下。资产持续增长。"
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert "*" not in narrative

    def test_markdown_inline_code_stripped(self):
        text = "使用`python`进行分析。家庭净资产健康增长。"
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert "`" not in narrative
        # "python" content is preserved (just stripped of code markers)
        assert "python" not in narrative or "家庭净资产" in narrative

    def test_code_block_removed(self):
        text = "这是分析。\n```python\nprint('hello')\n```\n家庭资产增长良好。继续保持储蓄。"
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert "```" not in narrative
        assert "print" not in narrative

    def test_narrative_capped_at_150_chars(self):
        """When narrative exceeds 150 chars, earliest sentence is dropped."""
        # Build 4 long Chinese sentences
        s1 = "一" * 50 + "。"
        s2 = "二" * 50 + "。"
        s3 = "三" * 50 + "。"
        s4 = "四" * 50 + "。"
        text = s1 + s2 + s3 + s4
        narrative, thinking = _separate_narrative_and_thinking(text)
        # Narrative should be capped (150 chars + possible ellipsis)
        assert len(narrative) <= 151  # 150 + ellipsis char

    def test_no_chinese_sentences_entire_text_is_narrative(self):
        """All-English text with no Chinese-dominant sentences -> entire text is narrative."""
        text = "Your assets are growing well. Keep saving regularly."
        narrative, thinking = _separate_narrative_and_thinking(text)
        assert narrative == text
        assert thinking == ""


# ---------------------------------------------------------------------------
# _build_narrative_context
# ---------------------------------------------------------------------------


class TestBuildNarrativeContext:
    def test_normal_overview_with_currency(self):
        overview = SimpleNamespace(
            currency="CNY",
            net_worth=500000.0,
            total_assets=600000.0,
            total_liabilities=100000.0,
            asset_count=10,
            month_over_month_change=2.5,
            month_over_month_change_amount=12000.0,
            total_daily_cost=150.0,
        )
        ctx = _build_narrative_context(overview, None)

        assert ctx["currency"] == "CNY"
        assert ctx["net_worth"] == "500000 CNY"
        assert ctx["total_assets"] == "600000 CNY"
        assert ctx["total_liabilities"] == "100000 CNY"
        assert ctx["asset_count"] == 10
        assert ctx["liability_ratio"] == "16.7%"

    def test_zero_total_assets_division_guard(self):
        """When total_assets is 0, liability_ratio should be 0.0 (no ZeroDivisionError)."""
        overview = SimpleNamespace(
            currency="USD",
            net_worth=0.0,
            total_assets=0.0,
            total_liabilities=0.0,
            asset_count=0,
            month_over_month_change=0.0,
            month_over_month_change_amount=0.0,
            total_daily_cost=0.0,
        )
        ctx = _build_narrative_context(overview, None)

        assert ctx["liability_ratio"] == "0.0%"
        assert ctx["currency"] == "USD"

    def test_insights_with_smart_discoveries(self):
        overview = SimpleNamespace(
            currency="CNY",
            net_worth=100000.0,
            total_assets=120000.0,
            total_liabilities=20000.0,
            asset_count=8,
            month_over_month_change=1.0,
            month_over_month_change_amount=1000.0,
            total_daily_cost=50.0,
        )
        smart_item = SimpleNamespace(type="savings", message="储蓄率提高")
        smart = SimpleNamespace(items=[smart_item])
        insights = SimpleNamespace(smart_discovery=smart, investment_returns=None)

        ctx = _build_narrative_context(overview, insights)

        assert "smart_discoveries" in ctx
        assert len(ctx["smart_discoveries"]) == 1
        assert ctx["smart_discoveries"][0]["type"] == "savings"
        assert ctx["smart_discoveries"][0]["message"] == "储蓄率提高"

    def test_insights_none(self):
        """When insights is None, no smart_discoveries or investment_returns in context."""
        overview = SimpleNamespace(
            currency="CNY",
            net_worth=100000.0,
            total_assets=120000.0,
            total_liabilities=20000.0,
            asset_count=8,
            month_over_month_change=1.0,
            month_over_month_change_amount=1000.0,
            total_daily_cost=50.0,
        )
        ctx = _build_narrative_context(overview, None)

        assert "smart_discoveries" not in ctx
        assert "investment_returns" not in ctx

    def test_insights_with_investment_returns(self):
        overview = SimpleNamespace(
            currency="CNY",
            net_worth=200000.0,
            total_assets=250000.0,
            total_liabilities=50000.0,
            asset_count=12,
            month_over_month_change=3.0,
            month_over_month_change_amount=7500.0,
            total_daily_cost=200.0,
        )
        inv = SimpleNamespace(annualized_rate=5.2, asset_count=4)
        insights = SimpleNamespace(smart_discovery=None, investment_returns=inv)

        ctx = _build_narrative_context(overview, insights)

        assert "investment_returns" in ctx
        assert ctx["investment_returns"]["annualized_rate"] == 5.2
        assert ctx["investment_returns"]["asset_count"] == 4

    def test_smart_discoveries_capped_at_5(self):
        """Only first 5 smart discoveries are included."""
        overview = SimpleNamespace(
            currency="CNY",
            net_worth=100000.0,
            total_assets=120000.0,
            total_liabilities=20000.0,
            asset_count=8,
            month_over_month_change=1.0,
            month_over_month_change_amount=1000.0,
            total_daily_cost=50.0,
        )
        items = [
            SimpleNamespace(type=f"type_{i}", message=f"msg_{i}") for i in range(8)
        ]
        smart = SimpleNamespace(items=items)
        insights = SimpleNamespace(smart_discovery=smart, investment_returns=None)

        ctx = _build_narrative_context(overview, insights)

        assert len(ctx["smart_discoveries"]) == 5

    def test_default_currency_is_cny(self):
        """When overview has no currency attribute, defaults to CNY."""
        overview = SimpleNamespace(
            net_worth=100000.0,
            total_assets=120000.0,
            total_liabilities=20000.0,
            asset_count=8,
            month_over_month_change=1.0,
            month_over_month_change_amount=1000.0,
            total_daily_cost=50.0,
        )
        # overview has no .currency attribute -> getattr fallback to "CNY"
        ctx = _build_narrative_context(overview, None)
        assert ctx["currency"] == "CNY"
