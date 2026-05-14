"""Unit tests for services/output_mapper.py and schemas/response.py."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from apps.agent.schemas.response import AgentResponse, Scorecard, RiskFlag, Recommendation, Finding
from apps.agent.services.output_mapper import OutputMapper


class TestOutputMapperFromDeerflow:
    def setup_method(self):
        self.mapper = OutputMapper()

    def test_valid_json_string_produces_full_response(self):
        raw = json.dumps({
            "summary": "资产状况良好",
            "scorecards": [{"name": "净资产", "score": 4.0, "max_score": 5.0}],
            "risk_flags": [{"level": "low", "title": "轻微风险"}],
        })
        result = self.mapper.from_deerflow(raw, "report", "audit-1")
        assert result.summary == "资产状况良好"
        assert len(result.scorecards) == 1
        assert result.scorecards[0].name == "净资产"
        assert len(result.risk_flags) == 1
        assert result.fallback_used is False

    def test_json_in_code_fence_extracted(self):
        raw = '```json\n{"summary": "分析完成"}\n```'
        result = self.mapper.from_deerflow(raw, "report", "audit-1")
        assert result.summary == "分析完成"

    def test_plain_text_produces_summary_only(self):
        raw = "这是一段普通文本分析结果"
        result = self.mapper.from_deerflow(raw, "chat", "audit-1")
        assert result.summary == raw
        assert result.scorecards == []
        assert result.fallback_used is False

    def test_empty_string_produces_empty_summary(self):
        result = self.mapper.from_deerflow("", "report", "audit-1")
        assert result.summary == ""
        assert result.fallback_used is False

    def test_audit_id_preserved(self):
        result = self.mapper.from_deerflow("{}", "report", "my-audit-id")
        assert result.audit_id == "my-audit-id"

    def test_capability_preserved(self):
        result = self.mapper.from_deerflow("{}", "liability", "audit-1")
        assert result.capability == "liability"

    def test_response_serializes_to_json(self):
        raw = json.dumps({"summary": "ok"})
        result = self.mapper.from_deerflow(raw, "report", "audit-1")
        dumped = result.model_dump()
        assert isinstance(json.dumps(dumped), str)


class TestOutputMapperFromLegacy:
    def setup_method(self):
        self.mapper = OutputMapper()

    def test_wraps_legacy_dict(self):
        legacy = {"summary": "旧版报告", "scorecards": []}
        result = self.mapper.from_legacy(legacy, "report", "audit-1")
        assert result.summary == "旧版报告"
        assert isinstance(result, AgentResponse)

    def test_fallback_used_false_by_default(self):
        result = self.mapper.from_legacy({}, "report", "audit-1")
        assert result.fallback_used is False

    def test_fallback_used_true_when_specified(self):
        result = self.mapper.from_legacy({}, "report", "audit-1", fallback_used=True)
        assert result.fallback_used is True

    def test_normal_legacy_path_not_fallback(self):
        """When USE_DEERFLOW=False, legacy is the normal path — fallback_used must be False."""
        result = self.mapper.from_legacy({"summary": "正常结果"}, "report", "audit-1", fallback_used=False)
        assert result.fallback_used is False


class TestOutputMapperFromError:
    def setup_method(self):
        self.mapper = OutputMapper()

    def test_error_response_fallback_used_true(self):
        result = self.mapper.from_error(RuntimeError("timeout"), "report", "audit-1")
        assert result.fallback_used is True

    def test_error_response_has_safe_summary(self):
        result = self.mapper.from_error(Exception("fail"), "report", "audit-1")
        assert len(result.summary) > 0

    def test_error_response_has_disclaimer(self):
        result = self.mapper.from_error(Exception("fail"), "report", "audit-1")
        assert len(result.disclaimers) > 0

    def test_error_response_no_exception_raised(self):
        # Must never raise
        result = self.mapper.from_error(ValueError("bad"), "chat", "audit-1")
        assert isinstance(result, AgentResponse)


class TestAgentResponseSchema:
    def test_default_fallback_used_false(self):
        r = AgentResponse(capability="report")
        assert r.fallback_used is False

    def test_audit_id_auto_generated(self):
        import uuid
        r = AgentResponse(capability="report")
        uuid.UUID(r.audit_id, version=4)  # must not raise

    def test_all_list_fields_default_empty(self):
        r = AgentResponse(capability="report")
        assert r.scorecards == []
        assert r.risk_flags == []
        assert r.recommendations == []
        assert r.disclaimers == []
        assert r.rule_based_findings == []
        assert r.ai_inferences == []

    def test_serializes_without_error(self):
        r = AgentResponse(
            capability="report",
            summary="test",
            scorecards=[Scorecard(name="净资产", score=4.0)],
            risk_flags=[RiskFlag(level="low", title="轻微")],
        )
        data = r.model_dump()
        assert json.dumps(data)  # must be JSON-serializable
