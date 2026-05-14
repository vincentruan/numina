"""Unit tests for services/pii_redactor.py and schemas/context.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.schemas.context import FamilyContext, RedactedContext
from apps.agent.services.pii_redactor import PIIRedactor, _redact_free_text


class TestPIIRedactorStructured:
    def setup_method(self):
        self.redactor = PIIRedactor()

    def _make_ctx(self, **kwargs) -> FamilyContext:
        return FamilyContext(family_id="fam-1", **kwargs)

    def test_asset_names_stripped(self):
        ctx = self._make_ctx(assets=[{"name": "我的车", "category_name": "车辆", "current_value": 100000}])
        result = self.redactor.redact(ctx)
        assert all("name" not in a for a in result.assets)
        assert result.assets[0]["category"] == "车辆"

    def test_member_names_replaced_with_labels(self):
        ctx = self._make_ctx(members=[
            {"name": "张三", "role": "admin"},
            {"name": "李四", "role": "member"},
        ])
        result = self.redactor.redact(ctx)
        assert result.members[0]["label"] == "成员A"
        assert result.members[1]["label"] == "成员B"
        assert all("name" not in m for m in result.members)

    def test_single_member_label(self):
        ctx = self._make_ctx(members=[{"name": "王五"}])
        result = self.redactor.redact(ctx)
        assert result.members[0]["label"] == "成员A"

    def test_liability_amounts_converted_to_ranges(self):
        ctx = self._make_ctx(liabilities=[{"remaining_amount": 800, "monthly_payment": 200}])
        result = self.redactor.redact(ctx)
        assert result.liabilities[0]["remaining_amount_range"] == "500-1000"
        assert result.liabilities[0]["remaining_amount_range_mid"] == 750.0

    def test_empty_assets_list(self):
        ctx = self._make_ctx(assets=[])
        result = self.redactor.redact(ctx)
        assert result.assets == []

    def test_empty_members_list(self):
        ctx = self._make_ctx(members=[])
        result = self.redactor.redact(ctx)
        assert result.members == []

    def test_redaction_log_populated(self):
        ctx = self._make_ctx(
            assets=[{"name": "手机", "category_name": "数码"}],
            members=[{"name": "张三"}],
            liabilities=[{"remaining_amount": 1000}],
        )
        result = self.redactor.redact(ctx)
        assert len(result.redaction_log) > 0
        assert any("assets" in entry for entry in result.redaction_log)
        assert any("members" in entry for entry in result.redaction_log)

    def test_redaction_log_not_in_free_text_when_none(self):
        ctx = self._make_ctx()
        result = self.redactor.redact(ctx)
        assert not any("free_text" in entry for entry in result.redaction_log)

    def test_family_id_preserved(self):
        ctx = self._make_ctx()
        result = self.redactor.redact(ctx)
        assert result.family_id == "fam-1"

    def test_dashboard_data_passed_through(self):
        ctx = self._make_ctx(dashboard_overview={"net_worth": 500000})
        result = self.redactor.redact(ctx)
        assert result.dashboard_overview["net_worth"] == 500000


class TestPIIRedactorFreeText:
    def setup_method(self):
        self.redactor = PIIRedactor()

    def _make_ctx(self, free_text: str) -> FamilyContext:
        return FamilyContext(family_id="fam-1", free_text=free_text)

    def test_phone_number_redacted(self):
        ctx = self._make_ctx("我的手机是13812345678，请联系我")
        result = self.redactor.redact(ctx)
        assert "13812345678" not in result.free_text
        assert "[已脱敏]" in result.free_text

    def test_id_card_redacted(self):
        ctx = self._make_ctx("身份证号码是110101199001011234")
        result = self.redactor.redact(ctx)
        assert "110101199001011234" not in result.free_text
        assert "[已脱敏]" in result.free_text

    def test_bank_card_redacted(self):
        ctx = self._make_ctx("银行卡号6222021234567890")
        result = self.redactor.redact(ctx)
        assert "6222021234567890" not in result.free_text
        assert "[已脱敏]" in result.free_text

    def test_no_pii_passes_through_unchanged(self):
        text = "我想了解家庭资产配置情况"
        ctx = self._make_ctx(text)
        result = self.redactor.redact(ctx)
        assert result.free_text == text

    def test_free_text_none_no_error(self):
        ctx = FamilyContext(family_id="fam-1", free_text=None)
        result = self.redactor.redact(ctx)
        assert result.free_text is None

    def test_redaction_log_records_pii_type(self):
        ctx = self._make_ctx("手机13812345678")
        result = self.redactor.redact(ctx)
        assert any("free_text" in entry for entry in result.redaction_log)

    def test_no_pii_no_free_text_log_entry(self):
        ctx = self._make_ctx("普通问题")
        result = self.redactor.redact(ctx)
        assert not any("free_text" in entry for entry in result.redaction_log)
