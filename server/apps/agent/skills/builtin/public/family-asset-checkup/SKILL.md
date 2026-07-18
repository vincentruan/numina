---
name: family-asset-checkup
description: |
  家庭资产体检分析。当用户请求资产健康评估、净资产分析、资产配置检查、
  负债压力评估或综合财务体检时触发。

trigger_phrases:
  - 资产体检
  - 家庭财务体检
  - 净资产分析
  - 资产健康
  - 财务状况评估

allowed-tools: []

---

## 适用场景

对家庭整体资产状况进行结构化分析，输出评分卡、风险标记和建议。

## 输入约束

- 输入为已脱敏的家庭财务数据（资产类别、金额区间、负债区间、成员标签）
- 不包含真实姓名、精确金额、账户信息
- 数据来源为用户自行录入，可能不完整

## 输出 JSON Schema

```json
{
  "summary": "<100-150字综合总结>",
  "scorecards": [
    {"name": "净资产健康", "score": 4.0, "max_score": 5.0, "label": "良好", "color": "green"},
    {"name": "资产配置", "score": 3.0, "max_score": 5.0, "label": "一般", "color": "yellow"},
    {"name": "负债压力", "score": 4.0, "max_score": 5.0, "label": "良好", "color": "green"},
    {"name": "资产效率", "score": 3.0, "max_score": 5.0, "label": "一般", "color": "yellow"}
  ],
  "risk_flags": [
    {"level": "medium", "title": "资产集中度偏高", "description": "单一类别占比超过60%"}
  ],
  "recommendations": [
    {"priority": "medium", "title": "建议关注资产多元化", "body": "...", "action_type": "suggestion"}
  ],
  "rule_based_findings": [
    {"source": "rule", "content": "负债月供占收入比超过40%", "confidence": 1.0}
  ],
  "ai_inferences": [
    {"source": "ai", "content": "基于资产结构观察，流动性可能偏低", "confidence": 0.7}
  ],
  "disclaimers": [
    "本分析基于用户录入的脱敏数据，不构成投资建议",
    "实际财务状况可能与分析结果存在差异"
  ]
}
```

## 边界限制

- 严禁提供投资建议、股票/基金推荐、贷款建议
- 严禁对未来收益做出预测或承诺
- 严禁基于不完整数据做出确定性结论

## 风险表达规则

- 使用观察性语言：「观察到」「建议关注」「数据显示」
- 禁止使用确定性语言：「确定」「必须」「一定会」
- 风险等级：high（需立即关注）/ medium（建议关注）/ low（参考信息）

## 不确定性表达

- AI 推断必须包含 confidence 字段（0.0-1.0）
- 数据不完整时在 summary 中注明「数据可能不完整，分析仅供参考」
- 区分规则结论（rule_based_findings）和 AI 推断（ai_inferences）
