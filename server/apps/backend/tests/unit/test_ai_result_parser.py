"""Unit tests for ai_result_parser table detection."""

from apps.backend.app.services.ai_result_parser import _contains_markdown_table


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