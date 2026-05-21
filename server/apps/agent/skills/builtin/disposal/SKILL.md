---
name: disposal
description: |
  闲置资产处置建议。识别低效、闲置资产，给出处置渠道建议和预估转售价值。

trigger_phrases:
  - 闲置资产
  - 处置建议
  - 出售渠道
  - 低效资产

allowed-tools: []

---

## 适用场景

识别家庭中闲置、低效使用的资产，给出处置建议。

## 输入约束

- 输入为已脱敏的家庭资产数据（资产名称、类别、当前价值、使用频率）
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析闲置资产状况，指出处置价值和建议渠道
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
[
  {
    "asset_name": "资产名称",
    "category_name": "类别",
    "inefficiency_score": 75,
    "suggested_channel": "闲鱼",
    "estimated_resale_range": "500-800元",
    "suggestion": "处置建议",
    "daily_cost": 2.0
  }
]
-->

## 字段说明

- `inefficiency_score`: 闲置效率评分（0-100，越高越建议处置）
- `suggested_channel`: 推荐处置渠道（如闲鱼、转转、二手店、捐赠）
- `estimated_resale_range`: 预估转售价格区间（可选）
- `daily_cost`: 每日持有成本（可选，元）

## 边界限制

- 严禁承诺具体转售价格
- 使用观察性语言：「预估」「建议」「可能」