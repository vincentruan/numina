---
name: family-liability-review
description: |
  家庭负债结构分析。当用户请求负债健康评估、还款压力分析、利率结构检查、
  债务风险评估或负债优化建议时触发。

trigger_phrases:
  - 负债分析
  - 还款压力
  - 债务健康
  - 利率分析
  - 负债结构

allowed-tools: []

---

## 适用场景

对家庭负债结构进行分析，评估还款压力、利率风险和期限结构。

## 输入约束

- 负债金额为区间值（非精确值），如「5万-10万」
- 利率为实际值（非敏感信息）
- 到期日精确到年月（非具体日期）

## 输出 JSON Schema

```json
{
  "summary": "<100-150字负债状况总结>",
  "scorecards": [
    {"name": "还款压力", "score": 3.0, "max_score": 5.0, "label": "一般", "color": "yellow"},
    {"name": "利率水平", "score": 4.0, "max_score": 5.0, "label": "良好", "color": "green"},
    {"name": "期限结构", "score": 3.5, "max_score": 5.0, "label": "较好", "color": "green"}
  ],
  "risk_flags": [
    {"level": "high", "title": "短期负债集中到期", "description": "3个月内有多笔负债到期"}
  ],
  "recommendations": [
    {"priority": "high", "title": "关注短期流动性", "body": "...", "action_type": "suggestion"}
  ],
  "rule_based_findings": [
    {"source": "rule", "content": "月供总额超过估算月收入的35%", "confidence": 1.0}
  ],
  "ai_inferences": [
    {"source": "ai", "content": "利率结构偏向浮动利率，存在利率上升风险", "confidence": 0.65}
  ],
  "disclaimers": [
    "负债金额为区间估算，实际数值以合同为准",
    "本分析不构成贷款建议或债务重组建议"
  ]
}
```

## 边界限制

- 严禁建议具体贷款产品或金融机构
- 严禁提供债务重组或破产相关建议
- 严禁对利率走势做出预测

## 风险表达规则

- 还款压力评估使用「月供占比」等客观指标
- 风险标记需说明具体触发条件
- 高风险标记需在 recommendations 中有对应建议

## 不确定性表达

- 月收入为估算值时，在 summary 中注明
- 利率风险推断 confidence 不超过 0.7
- 区分已知事实（rule）和推断（ai）
