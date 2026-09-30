"""Tests for asset_report_middleware — parse_report_json + llm_json_repair validators."""

from apps.agent.services.runtime.asset_report_middleware import (
    normalize_report_json,
    parse_report_json,
)
from apps.agent.services.runtime.llm_json_repair import validate_report_json


class TestValidateReportJson:
    """Phase 4B (T12b): report JSON schema validation."""

    def test_valid_canonical_report_passes(self):
        data = {
            "overall_score": 85,
            "indicators": [
                {
                    "key": "asset_allocation",
                    "label": "资产配置",
                    "score": 4,
                    "narrative": "配置合理",
                    "data": {
                        "items": [
                            {"key": "cash", "zh": "现金", "en": "Cash", "value": 42.5}
                        ]
                    },
                }
            ],
        }
        assert validate_report_json(data) == []

    def test_name_as_key_alias_passes(self):
        """LLM often emits ``name`` instead of ``key`` — validate accepts it."""
        data = {
            "overall_score": 85,
            "indicators": [
                {
                    "name": "资产配置",
                    "score": 4,
                    "data": {
                        "items": [
                            {"key": "cash", "zh": "现金", "en": "Cash", "value": 42.5}
                        ]
                    },
                }
            ],
        }
        assert validate_report_json(data) == []

    def test_missing_indicators_fails(self):
        assert validate_report_json({"overall_score": 85}) != []

    def test_empty_indicators_fails(self):
        assert validate_report_json({"indicators": []}) != []

    def test_indicator_missing_items_fails(self):
        data = {"indicators": [{"name": "资产配置", "data": {"items": []}}]}
        errors = validate_report_json(data)
        assert errors != []
        assert any("items" in e for e in errors)

    def test_non_dict_fails(self):
        assert validate_report_json("not a dict") != []  # type: ignore[arg-type]


class TestParseReportJson:
    """parse_report_json — json_repair tolerant parsing."""

    def test_parses_fenced_json_with_indicators(self):
        text = '```json\n{"overall_score": 90, "indicators": [{"name": "x", "data": {"items": [{"key": "k", "zh": "z", "en": "e", "value": 1}]}}]}\n```'
        parsed = parse_report_json(text)
        assert parsed is not None
        assert "indicators" in parsed
        assert len(parsed["indicators"]) == 1

    def test_normalizes_non_canonical_items(self):
        # Non-canonical {category_name, percentage} → canonical {key, zh, en, value}
        text = (
            '{"overall_score": 80, "indicators": [{"name": "x", "data": '
            '{"items": [{"category_name": "cash", "percentage": 30}]}}]}'
        )
        parsed = parse_report_json(text)
        assert parsed is not None
        items = parsed["indicators"][0]["data"]["items"]
        assert items[0]["key"] == "cash"
        assert items[0]["value"] == 30.0

    def test_returns_none_on_garbage(self):
        assert parse_report_json("no json here at all") is None


class TestNormalizeReportJsonSafetyNet:
    """KTD-8 hardening: missing LLM fields get synthesized defaults so the
    user always sees a meaningful report (summary, completeness, suggestions)."""

    def test_missing_summary_synthesized_from_indicators(self):
        data = {
            "overall_score": 65,
            "indicators": [
                {
                    "key": "net_worth_health",
                    "label": "净资产健康",
                    "score": 4,
                    "narrative": "净资产状况良好，具备较好的财富基础。",
                    "suggestions": ["增加流动性资产配置"],
                    "data": {"items": [{"key": "net_worth", "zh": "净资产", "en": "Net Worth", "value": 4660000}]},
                },
            ],
        }
        result = normalize_report_json(data)
        assert result["summary"]  # non-empty synthesized summary
        assert "净资产健康" in result["summary"]

    def test_existing_summary_not_overwritten(self):
        data = {
            "overall_score": 65,
            "summary": "LLM 生成的原始摘要",
            "indicators": [
                {
                    "key": "net_worth_health",
                    "label": "净资产健康",
                    "score": 4,
                    "narrative": "ok",
                    "data": {"items": [{"key": "net_worth", "zh": "净资产", "en": "Net Worth", "value": 100}]},
                },
            ],
        }
        result = normalize_report_json(data)
        assert result["summary"] == "LLM 生成的原始摘要"

    def test_missing_completeness_score_computed(self):
        data = {
            "overall_score": 65,
            "indicators": [
                {
                    "key": "a",
                    "label": "A",
                    "score": 4,
                    "narrative": "ok",
                    "suggestions": ["s1"],
                    "data": {"items": [{"key": "k", "zh": "中", "en": "En", "value": 1}]},
                },
                {
                    "key": "b",
                    "label": "B",
                    "score": 3,
                    "narrative": "ok",
                    "suggestions": ["s2"],
                    "data": {"items": [{"key": "k", "zh": "中", "en": "En", "value": 2}]},
                },
            ],
        }
        result = normalize_report_json(data)
        score = result["data_completeness_score"]
        # 2 indicators × 10 base + 30 suggestion coverage = 50.0
        assert score == 50.0

    def test_existing_completeness_score_not_overwritten(self):
        data = {
            "overall_score": 65,
            "data_completeness_score": 92,
            "indicators": [
                {
                    "key": "a",
                    "label": "A",
                    "score": 4,
                    "narrative": "ok",
                    "data": {"items": [{"key": "k", "zh": "中", "en": "En", "value": 1}]},
                },
            ],
        }
        result = normalize_report_json(data)
        assert result["data_completeness_score"] == 92

    def test_missing_suggestions_default_to_empty_list(self):
        data = {
            "overall_score": 65,
            "indicators": [
                {
                    "key": "a",
                    "label": "A",
                    "score": 4,
                    "narrative": "ok",
                    "data": {"items": [{"key": "k", "zh": "中", "en": "En", "value": 1}]},
                },
            ],
        }
        result = normalize_report_json(data)
        assert result["indicators"][0]["suggestions"] == []

    def test_parse_report_json_applies_safety_net(self):
        """End-to-end: JSON missing summary/completeness gets defaults after parse."""
        text = (
            '{"overall_score": 65, "indicators": [{"key": "a", "label": "A", "score": 4, '
            '"narrative": "ok", "data": {"items": [{"key": "k", "zh": "中", "en": "En", "value": 1}]}}]}'
        )
        parsed = parse_report_json(text)
        assert parsed is not None
        assert parsed["summary"]
        assert parsed["data_completeness_score"] is not None
        # Must also pass the canonical validator afterwards
        assert validate_report_json(parsed) == []
