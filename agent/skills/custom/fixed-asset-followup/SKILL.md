---
name: fixed-asset-followup
description: |
  固定资产跟踪与老化预警。当用户请求资产老化检查、维护提醒、保险到期提醒、
  闲置资产分析或持有成本分析时触发。

trigger_phrases:
  - 资产老化
  - 维护提醒
  - 闲置资产
  - 持有成本
  - 固定资产跟踪

allowed-tools: []

---

## 适用场景

对固定资产（房产、车辆、耐用品）进行跟踪分析，识别老化风险、维护需求和闲置成本。

## 输入约束

- 资产名称已替换为类别标签（如「车辆」「数码」）
- 购买日期精确到月
- 使用频率为枚举值：daily/weekly/monthly/rarely/idle

## 输出 JSON Schema

```json
{
  "summary": "<80-120字资产跟踪总结>",
  "risk_flags": [
    {"level": "high", "title": "车辆类资产即将到期", "description": "预计剩余寿命不足180天"},
    {"level": "medium", "title": "数码类资产长期闲置", "description": "使用频率为idle，日均成本持续产生"}
  ],
  "recommendations": [
    {"priority": "high", "title": "关注车辆维护计划", "body": "...", "action_type": "suggestion"},
    {"priority": "medium", "title": "评估闲置数码资产处置", "body": "...", "action_type": "suggestion"}
  ],
  "rule_based_findings": [
    {"source": "rule", "content": "2项资产剩余寿命不足365天", "confidence": 1.0},
    {"source": "rule", "content": "1项资产年维护费超过当前价值20%", "confidence": 1.0}
  ],
  "ai_inferences": [
    {"source": "ai", "content": "闲置资产持有成本在未来12个月可能超过处置收益", "confidence": 0.6}
  ],
  "needs_confirmation": [
    {"item_id": "asset-aging-1", "description": "车辆类资产是否已安排年检？", "suggested_action": "确认后更新资产状态"}
  ],
  "disclaimers": [
    "资产寿命估算基于录入数据，实际情况以实物状态为准",
    "处置建议仅供参考，不构成交易建议"
  ]
}
```

## 边界限制

- 严禁推荐具体处置渠道或交易平台
- 严禁对资产残值做出精确预测
- 维护提醒基于规则，不基于 AI 推断

## 风险表达规则

- 老化预警优先使用规则结论（rule_based_findings）
- AI 推断仅用于持有成本趋势分析
- needs_confirmation 用于需要用户确认的事项

## 不确定性表达

- 寿命估算基于购买日期+预期寿命，注明为估算值
- 闲置成本推断 confidence 不超过 0.65
