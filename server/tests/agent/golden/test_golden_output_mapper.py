"""Golden case tests for OutputMapper — verify stable JSON contract shapes.

These tests use realistic DeerFlow-style JSON output strings and verify that
OutputMapper produces correctly structured AgentResponse objects.
"""

import json
import pytest

from apps.agent.services.output_mapper import output_mapper
from tests.agent.golden.fixtures import (
    assert_valid_agent_response,
    assert_has_risk_flags,
    assert_has_recommendations,
    assert_distinguishes_rule_vs_ai,
)


GOLDEN_ASSET_CHECKUP_JSON = json.dumps({
    "summary": "家庭资产总额约42万元，净资产为负，主要由房贷和车贷构成。流动资产占比约35%，资产集中度偏高（车辆占43%）。数据可能不完整，分析仅供参考。",
    "scorecards": [
        {"name": "净资产健康", "score": 1.5, "max_score": 5.0, "label": "需关注", "color": "red"},
        {"name": "资产配置", "score": 2.5, "max_score": 5.0, "label": "一般", "color": "yellow"},
        {"name": "负债压力", "score": 2.0, "max_score": 5.0, "label": "偏高", "color": "red"},
        {"name": "资产效率", "score": 3.0, "max_score": 5.0, "label": "一般", "color": "yellow"},
    ],
    "risk_flags": [
        {"level": "high", "title": "净资产为负", "description": "总负债超过总资产，净资产约为-40.7万元"},
        {"level": "medium", "title": "资产集中度偏高", "description": "车辆类资产占比超过40%"},
    ],
    "recommendations": [
        {"priority": "high", "title": "关注净资产改善", "body": "建议优先偿还高利率负债以改善净资产状况", "action_type": "suggestion"},
        {"priority": "medium", "title": "评估闲置数码资产", "body": "数码类资产使用频率为idle，建议评估是否处置", "action_type": "suggestion"},
    ],
    "rule_based_findings": [
        {"source": "rule", "content": "净资产为负（总负债82.5万 > 总资产41.8万）", "confidence": 1.0},
        {"source": "rule", "content": "1项资产使用频率为idle", "confidence": 1.0},
    ],
    "ai_inferences": [
        {"source": "ai", "content": "基于资产结构观察，流动性可能偏低，建议关注短期现金流", "confidence": 0.65},
    ],
    "disclaimers": [
        "本分析基于用户录入的脱敏数据，不构成投资建议",
        "实际财务状况可能与分析结果存在差异",
    ],
})

GOLDEN_LIABILITY_REVIEW_JSON = json.dumps({
    "summary": "家庭负债以房贷为主（约75万），车贷约7.5万，月供合计约4000-8000元。利率结构以固定利率为主，期限结构合理。以上分析仅供参考。",
    "scorecards": [
        {"name": "还款压力", "score": 2.5, "max_score": 5.0, "label": "偏高", "color": "yellow"},
        {"name": "利率水平", "score": 3.5, "max_score": 5.0, "label": "较好", "color": "green"},
        {"name": "期限结构", "score": 3.0, "max_score": 5.0, "label": "一般", "color": "yellow"},
    ],
    "risk_flags": [
        {"level": "medium", "title": "月供占比偏高", "description": "月供总额估算超过月收入35%（月收入未录入，基于估算）"},
    ],
    "recommendations": [
        {"priority": "medium", "title": "关注车贷到期安排", "body": "车贷预计2027年4月到期，建议提前规划还款资金", "action_type": "suggestion"},
    ],
    "rule_based_findings": [
        {"source": "rule", "content": "共2笔活跃负债，总额约82.5万元", "confidence": 1.0},
        {"source": "rule", "content": "车贷剩余36个月，利率5.8%高于房贷4.2%", "confidence": 1.0},
    ],
    "ai_inferences": [
        {"source": "ai", "content": "利率结构以固定利率为主，利率上升风险相对可控", "confidence": 0.6},
    ],
    "disclaimers": [
        "负债金额为区间估算，实际数值以合同为准",
        "本分析不构成贷款建议或债务重组建议",
    ],
})

GOLDEN_FIXED_ASSET_JSON = json.dumps({
    "summary": "共2项实物资产。车辆类资产已使用约6年，剩余寿命约4年。数码类资产长期闲置，日均持有成本约4.38元。资产寿命估算基于录入数据，实际情况以实物状态为准。",
    "risk_flags": [
        {"level": "medium", "title": "数码类资产长期闲置", "description": "使用频率为idle，日均成本持续产生"},
    ],
    "recommendations": [
        {"priority": "medium", "title": "评估闲置数码资产处置", "body": "闲置资产持续产生持有成本，建议评估处置可行性", "action_type": "suggestion"},
    ],
    "rule_based_findings": [
        {"source": "rule", "content": "1项资产使用频率为idle", "confidence": 1.0},
        {"source": "rule", "content": "车辆类资产已使用约2190天，预期寿命3650天", "confidence": 1.0},
    ],
    "ai_inferences": [
        {"source": "ai", "content": "闲置资产持有成本在未来12个月可能超过处置收益", "confidence": 0.6},
    ],
    "disclaimers": [
        "资产寿命估算基于录入数据，实际情况以实物状态为准",
        "处置建议仅供参考，不构成交易建议",
    ],
})


class TestGoldenAssetCheckup:
    def test_full_response_structure(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        assert_valid_agent_response(response, "report")
        assert_has_risk_flags(response)
        assert_has_recommendations(response)
        assert_distinguishes_rule_vs_ai(response)

    def test_scorecards_parsed(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        assert len(response.scorecards) == 4
        names = {s.name for s in response.scorecards}
        assert "净资产健康" in names
        assert "负债压力" in names

    def test_high_risk_flag_present(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        high_flags = [f for f in response.risk_flags if f.level == "high"]
        assert len(high_flags) >= 1

    def test_ai_confidence_within_cap(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        assert_distinguishes_rule_vs_ai(response)

    def test_rule_findings_have_confidence_1(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        for f in response.rule_based_findings:
            assert f.confidence == 1.0, f"Rule finding confidence should be 1.0, got {f.confidence}"

    def test_fallback_used_false(self):
        response = output_mapper.from_deerflow(GOLDEN_ASSET_CHECKUP_JSON, "report", "audit-g1")
        assert response.fallback_used is False


class TestGoldenLiabilityReview:
    def test_full_response_structure(self):
        response = output_mapper.from_deerflow(GOLDEN_LIABILITY_REVIEW_JSON, "liability", "audit-g2")
        assert_valid_agent_response(response, "liability")
        assert_distinguishes_rule_vs_ai(response)

    def test_scorecards_have_color(self):
        response = output_mapper.from_deerflow(GOLDEN_LIABILITY_REVIEW_JSON, "liability", "audit-g2")
        for sc in response.scorecards:
            assert sc.color in ("green", "yellow", "red", ""), f"Unexpected color: {sc.color}"

    def test_recommendations_have_priority(self):
        response = output_mapper.from_deerflow(GOLDEN_LIABILITY_REVIEW_JSON, "liability", "audit-g2")
        for rec in response.recommendations:
            assert rec.priority in ("high", "medium", "low")


class TestGoldenFixedAssetFollowup:
    def test_full_response_structure(self):
        response = output_mapper.from_deerflow(GOLDEN_FIXED_ASSET_JSON, "alerts", "audit-g3")
        assert_valid_agent_response(response, "alerts")
        assert_distinguishes_rule_vs_ai(response)

    def test_idle_asset_flagged(self):
        response = output_mapper.from_deerflow(GOLDEN_FIXED_ASSET_JSON, "alerts", "audit-g3")
        flag_titles = [f.title for f in response.risk_flags]
        assert any("闲置" in t for t in flag_titles)


class TestGoldenFenceStripping:
    def test_json_in_markdown_fence_parsed(self):
        fenced = f"```json\n{GOLDEN_ASSET_CHECKUP_JSON}\n```"
        response = output_mapper.from_deerflow(fenced, "report", "audit-g4")
        assert len(response.scorecards) == 4

    def test_json_with_preamble_parsed(self):
        with_preamble = f"以下是分析结果：\n\n{GOLDEN_ASSET_CHECKUP_JSON}\n\n请参考以上内容。"
        response = output_mapper.from_deerflow(with_preamble, "report", "audit-g5")
        assert len(response.scorecards) == 4

    def test_plain_text_fallback_uses_summary(self):
        plain = "家庭财务状况整体良好，建议关注负债结构。"
        response = output_mapper.from_deerflow(plain, "report", "audit-g6")
        assert response.summary == plain
        assert response.scorecards == []
