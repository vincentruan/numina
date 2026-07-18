---
name: family-finance-insight-planner
description: |
  家庭财务深度研究规划器。当用户提出复杂财务问题需要多步骤分析时触发，
  如资产配置风险深度分析、债务结构优化、长期财务健康规划、持有成本综合分析。
  此 skill 启用 DeerFlow 规划模式，将复杂问题分解为子任务。

trigger_phrases:
  - 深度分析
  - 综合规划
  - 长期财务
  - 资产配置优化
  - 债务结构优化

allowed-tools: []

planning:
  enabled: true
  max_steps: 5

---

## 适用场景

处理需要多步骤推理的复杂财务问题：
1. 资产配置风险深度分析（跨多个资产类别）
2. 债务结构优化分析（综合利率、期限、压力）
3. 持有成本综合分析（固定资产 + 负债成本）
4. 家庭财务长期健康趋势分析

## 输入约束

- 所有数据已脱敏（类别标签、金额区间、成员标签）
- 用户问题已通过 PIIRedactor 处理
- 分析范围限于用户录入的数据，不引入外部市场数据

## 规划步骤模板

对于复杂问题，按以下步骤分解：
1. 理解问题范围，确认可用数据
2. 识别关键风险维度
3. 逐维度分析（每步聚焦一个维度）
4. 综合各维度结论
5. 生成结构化输出

## 输出 JSON Schema

```json
{
  "summary": "<150-200字深度分析总结>",
  "scorecards": [
    {"name": "综合财务健康", "score": 3.5, "max_score": 5.0, "label": "较好", "color": "green"}
  ],
  "risk_flags": [
    {"level": "medium", "title": "资产流动性不足", "description": "流动资产占比低于20%"}
  ],
  "recommendations": [
    {"priority": "high", "title": "优化资产流动性", "body": "...", "action_type": "suggestion"},
    {"priority": "medium", "title": "关注债务集中到期风险", "body": "...", "action_type": "suggestion"}
  ],
  "rule_based_findings": [
    {"source": "rule", "content": "流动资产占总资产比例低于建议水平", "confidence": 1.0}
  ],
  "ai_inferences": [
    {"source": "ai", "content": "综合资产结构和负债压力，整体财务弹性偏低", "confidence": 0.65}
  ],
  "needs_confirmation": [
    {"item_id": "confirm-income", "description": "月收入数据未录入，分析基于估算", "suggested_action": "录入月收入以提高分析准确性"}
  ],
  "disclaimers": [
    "本分析为综合性参考，不构成投资建议或财务规划建议",
    "分析基于用户录入的脱敏数据，实际情况可能存在差异",
    "建议结合专业财务顾问意见做出决策"
  ]
}
```

## 边界限制

- 严禁提供投资建议、资产配置比例建议（如「应将30%配置在X」）
- 严禁对市场走势、利率走势做出预测
- 严禁基于不完整数据做出确定性结论
- 规划步骤不超过5步，避免过度分析

## 风险表达规则

- 深度分析结论必须区分规则结论和 AI 推断
- 所有 AI 推断 confidence 不超过 0.75
- 结论中包含明确的数据局限性说明

## 不确定性表达

- 每个主要结论后注明置信度
- 数据缺失时在 needs_confirmation 中列出
- summary 末尾包含「以上分析仅供参考」声明
