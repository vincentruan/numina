---
name: liability
description: |
  家庭负债分析和还款策略建议。分析家庭负债状况，给出还款优先级和策略建议。

trigger_phrases:
  - 负债分析
  - 还款策略
  - 负债建议
  - 债务规划

allowed-tools: []

---

## 适用场景

分析家庭负债状况，给出还款优先级和策略建议（雪崩法、滚雪球法）。

## 输入约束

- 输入为已脱敏的家庭负债数据（负债类别、剩余金额、月供、利率）
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析负债状况，指出还款策略建议
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
{
  "has_liabilities": true,
  "total_remaining": 150000,
  "total_monthly_payment": 5000,
  "liability_count": 3,
  "narrative": "负债分析摘要",
  "recommended_strategy": "avalanche",
  "strategies": [
    {
      "strategy": "avalanche",
      "strategy_name": "雪崩法（先还高利率）",
      "estimated_interest_saved": 2000,
      "priority_debt": "信用卡A",
      "order": [
        {"id": "1", "category": "信用卡", "rate": 18}
      ]
    }
  ]
}
-->

## 字段说明

- `has_liabilities`: 是否存在负债
- `total_remaining`: 总剩余金额（可选，元）
- `total_monthly_payment`: 总月供（可选，元）
- `liability_count`: 负债数量（可选）
- `narrative`: 分析摘要（可选）
- `recommended_strategy`: 推荐策略（avalanche | snowball | hybrid）
- `strategies`: 各策略详情（可选）

## 边界限制

- 严禁提供贷款建议或推荐借贷产品
- 使用观察性语言：「建议」「预估」
- 利息节省为预估，不承诺实际结果