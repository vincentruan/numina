"""Tests for asset_report_middleware — parse_report_json + llm_json_repair validators."""

from apps.agent.services.runtime.asset_report_middleware import parse_report_json
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
