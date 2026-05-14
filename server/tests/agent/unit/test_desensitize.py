"""Unit tests for core/desensitize.py — Bug fix: remaining_amount_range_mid."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.core.desensitize import (
    desensitize_liabilities,
    desensitize_assets,
    desensitize_members,
    _amount_to_range_mid,
)


class TestDesensitizeLiabilitiesMidpoint:
    def test_midpoint_field_present(self):
        result = desensitize_liabilities([{"remaining_amount": 800}])
        assert "remaining_amount_range_mid" in result[0]

    def test_midpoint_is_float(self):
        result = desensitize_liabilities([{"remaining_amount": 800}])
        assert isinstance(result[0]["remaining_amount_range_mid"], float)

    def test_midpoint_value_500_1000_range(self):
        result = desensitize_liabilities([{"remaining_amount": 800}])
        assert result[0]["remaining_amount_range_mid"] == 750.0
        assert result[0]["remaining_amount_range"] == "500-1000"

    def test_midpoint_none_amount(self):
        result = desensitize_liabilities([{"remaining_amount": None}])
        assert result[0]["remaining_amount_range_mid"] == 0.0

    def test_midpoint_missing_amount(self):
        result = desensitize_liabilities([{}])
        assert result[0]["remaining_amount_range_mid"] == 0.0

    def test_midpoint_boundary_exactly_500(self):
        # 500 falls in the 500-1000 bucket
        assert _amount_to_range_mid(500) == 750.0

    def test_midpoint_boundary_exactly_1000(self):
        # 1000 falls in the 1000-5000 bucket
        assert _amount_to_range_mid(1000) == 3000.0

    def test_midpoint_below_500(self):
        assert _amount_to_range_mid(100) == 250.0

    def test_midpoint_large_amount(self):
        assert _amount_to_range_mid(2_000_000) == 1_500_000.0

    def test_health_report_sum_uses_midpoint(self):
        """Regression: health_report sums remaining_amount_range_mid — must be numeric."""
        liabilities = [
            {"remaining_amount": 800},
            {"remaining_amount": 3000},
        ]
        result = desensitize_liabilities(liabilities)
        total = sum(li["remaining_amount_range_mid"] for li in result)
        assert total == 750.0 + 3000.0

    def test_empty_list(self):
        assert desensitize_liabilities([]) == []


class TestDesensitizeAssets:
    def test_strips_name(self):
        assets = [{"name": "我的车", "category_name": "车辆", "current_value": 100000}]
        result = desensitize_assets(assets)
        assert "name" not in result[0]
        assert result[0]["category"] == "车辆"

    def test_keeps_value_fields(self):
        assets = [{"category_name": "数码", "current_value": 5000, "purchase_price": 8000}]
        result = desensitize_assets(assets)
        assert result[0]["current_value"] == 5000
        assert result[0]["purchase_price"] == 8000

    def test_empty_list(self):
        assert desensitize_assets([]) == []


class TestDesensitizeMembers:
    def test_single_member_label(self):
        result = desensitize_members([{"name": "张三", "role": "admin"}])
        assert result[0]["label"] == "成员A"
        assert "name" not in result[0]

    def test_multiple_members_labels(self):
        members = [{"name": f"用户{i}"} for i in range(3)]
        result = desensitize_members(members)
        assert [r["label"] for r in result] == ["成员A", "成员B", "成员C"]

    def test_empty_list(self):
        assert desensitize_members([]) == []
