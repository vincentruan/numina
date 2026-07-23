"""Unit tests for ai_result_parser envelope unwrapping + markdown-table detection.

Ported from the former apps/backend/tests/unit/test_ai_result_parser.py (U4 era).
These cover ``_unwrap_agent_envelope`` and ``_contains_markdown_table``, which the
companion ``tests/backend/test_ai_result_parser.py`` does not exercise (it covers
``_extract_structured_block`` / ``_extract_bare_json`` / ``parse_capability_result``
/ the LLM-fallback path).
"""

from apps.backend.app.services.ai_result_parser import (
    _contains_markdown_table,
    _unwrap_agent_envelope,
    _validate_json,
)


class TestUnwrapAgentEnvelope:
    """Test suite for _unwrap_agent_envelope function."""

    def test_unwrap_backend_style_envelope_report(self):
        """Unwrap {'code': 'OK', 'data': {'report': {...}}} format for report capability."""
        wrapped = {
            "code": "OK",
            "message": "",
            "data": {
                "report": {
                    "overall_score": 65,
                    "data_completeness_score": 80,
                    "summary": "Test summary",
                    "indicators": [
                        {"key": "net_worth_health", "label": "净资产健康度", "score": 4, "narrative": "Test"}
                    ],
                }
            },
        }
        result = _unwrap_agent_envelope(wrapped, "report")
        assert result is not None
        assert result["overall_score"] == 65
        assert "indicators" in result
        assert result["indicators"][0]["key"] == "net_worth_health"

    def test_unwrap_envelope_nested_in_data(self):
        """Unwrap envelope where data directly contains required fields."""
        wrapped = {
            "code": "OK",
            "data": {
                "overall_score": 70,
                "indicators": [
                    {"key": "test", "label": "Test", "score": 3, "narrative": "Test narrative"}
                ],
            },
        }
        result = _unwrap_agent_envelope(wrapped, "report")
        assert result is not None
        assert result["overall_score"] == 70

    def test_no_unwrap_for_direct_format(self):
        """Direct format (no envelope) is returned unchanged."""
        direct = {
            "overall_score": 55,
            "indicators": [
                {"key": "test", "label": "Test", "score": 2, "narrative": "Test"}
            ],
        }
        result = _unwrap_agent_envelope(direct, "report")
        assert result == direct

    def test_no_unwrap_for_non_report_capability(self):
        """Non-report capability without envelope is returned unchanged."""
        alerts_data = [
            {"asset_name": "Test Asset", "alert_type": "aging", "severity": "high"}
        ]
        result = _unwrap_agent_envelope({"alerts": alerts_data}, "alerts")
        # Should return original since no envelope detected
        assert result == {"alerts": alerts_data}

    def test_unwrap_preserves_nested_data(self):
        """Unwrapping preserves all nested fields correctly."""
        wrapped = {
            "code": "OK",
            "message": "",
            "data": {
                "report": {
                    "overall_score": 35,
                    "data_completeness_score": 0.85,
                    "summary": "Test summary",
                    "narrative": "Test narrative",
                    "sections": {"executive_summary": "Test"},
                    "indicators": [
                        {
                            "key": "net_worth_health",
                            "label": "净资产健康度",
                            "score": 3,
                            "narrative": "Test narrative",
                            "suggestions": ["建议1", "建议2"],
                            "data": {"net_worth": 1000000},
                        }
                    ],
                }
            },
        }
        result = _unwrap_agent_envelope(wrapped, "report")
        assert result["overall_score"] == 35
        assert result["data_completeness_score"] == 0.85
        assert len(result["indicators"]) == 1
        assert result["indicators"][0]["suggestions"] == ["建议1", "建议2"]

    def test_validate_json_with_envelope(self):
        """Validation works with envelope-wrapped data."""
        wrapped = {
            "code": "OK",
            "data": {
                "report": {
                    "overall_score": 60,
                    "indicators": [
                        {"key": "test", "label": "Test", "score": 3, "narrative": "Test"}
                    ],
                }
            },
        }
        # _validate_json should unwrap internally and pass validation
        assert _validate_json(wrapped, "report") is True

    def test_validate_json_direct_format(self):
        """Validation works with direct format data."""
        direct = {
            "overall_score": 50,
            "indicators": [
                {"key": "test", "label": "Test", "score": 2, "narrative": "Test"}
            ],
        }
        assert _validate_json(direct, "report") is True

    def test_validate_json_missing_required_field(self):
        """Validation fails when required fields are missing."""
        data = {"overall_score": 50}  # Missing 'indicators'
        assert _validate_json(data, "report") is False

    def test_unwrap_invalid_envelope_structure(self):
        """Invalid envelope structure returns original data."""
        invalid = {"code": "OK", "data": "not a dict"}
        result = _unwrap_agent_envelope(invalid, "report")
        assert result == invalid

    def test_unwrap_missing_report_key_for_report_capability(self):
        """Envelope without 'report' key for report capability checks direct data."""
        wrapped = {
            "code": "OK",
            "data": {
                "overall_score": 65,
                "indicators": [
                    {"key": "test", "label": "Test", "score": 4, "narrative": "Test"}
                ],
            },
        }
        result = _unwrap_agent_envelope(wrapped, "report")
        # Should unwrap to data directly since it has required fields
        assert result is not None
        assert result["overall_score"] == 65


class TestContainsMarkdownTable:
    """Test suite for _contains_markdown_table function."""

    def test_contains_markdown_table_full_table(self):
        """Full table with both leading and trailing pipes returns True."""
        data = {
            "net_worth_health": {
                "narrative": "Here is a table:\n| Header 1 | Header 2 | Header 3 |\n|----------|----------|----------|\n| Cell 1   | Cell 2   | Cell 3   |"
            }
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_partial_table(self):
        """Partial table without trailing pipe returns True."""
        data = {
            "allocation_analysis": {
                "narrative": "资产分配情况:\n| 类型 | 占比\n| 房产 | 95%\n| 金融 | 3%"
            }
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_no_table(self):
        """Normal list without table patterns returns False."""
        data = {
            "liability_pressure": {
                "narrative": "以下是建议:\n- 降低负债\n- 增加收入\n- 减少支出"
            }
        }
        assert _contains_markdown_table(data) is False

    def test_contains_markdown_table_pipe_in_sentence(self):
        """Multiple pipe separators in sentence returns True."""
        data = {
            "asset_efficiency": {
                "narrative": "资产配置: 房产 | 金融 95% | 3%"
            }
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_in_summary(self):
        """Table in summary field returns True."""
        data = {
            "summary": "总体情况:\n| 项目 | 金额 |\n|------|------|\n| 总资产 | 100万 |"
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_no_leading_pipe(self):
        """Table without leading pipe but multiple separators returns True."""
        data = {
            "net_worth_health": {
                "narrative": "资产分布:\n房产 | 60% | 金融资产 | 30% | 其他 | 10%"
            }
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_single_pipe(self):
        """Single pipe in text returns False (not a table)."""
        data = {
            "allocation_analysis": {
                "narrative": "这是一个分隔符 | 只是普通文本"
            }
        }
        # Single pipe should NOT match - no table pattern
        assert _contains_markdown_table(data) is False

    def test_contains_markdown_table_empty_narrative(self):
        """Empty narrative returns False."""
        data = {
            "net_worth_health": {
                "narrative": ""
            }
        }
        assert _contains_markdown_table(data) is False

    def test_contains_markdown_table_missing_narrative(self):
        """Missing narrative field returns False."""
        data = {
            "net_worth_health": {}
        }
        assert _contains_markdown_table(data) is False

    def test_contains_markdown_table_empty_data(self):
        """Empty data dict returns False."""
        data = {}
        assert _contains_markdown_table(data) is False

    def test_contains_markdown_table_multiple_sections(self):
        """Table in later section is detected."""
        data = {
            "net_worth_health": {
                "narrative": "No table here."
            },
            "allocation_analysis": {
                "narrative": "No table either."
            },
            "liability_pressure": {
                "narrative": "| 列1 | 列2 |"
            }
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_complex_table(self):
        """Complex multi-row table is detected."""
        data = {
            "summary": "详细分析:\n| 资产类型 | 金额 | 占比 |\n|----------|------|------|\n| 房产 | 200万 | 80% |\n| 基金 | 30万 | 12% |\n| 存款 | 20万 | 8% |"
        }
        assert _contains_markdown_table(data) is True

    def test_contains_markdown_table_inline_pipe_usage(self):
        """Inline pipe usage in Chinese text with multiple separators returns True."""
        data = {
            "asset_efficiency": {
                "narrative": "配置建议: 股票 | 债券 | 现金 | 其他"
            }
        }
        assert _contains_markdown_table(data) is True
