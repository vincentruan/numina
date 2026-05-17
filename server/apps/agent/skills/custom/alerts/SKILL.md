---
name: alerts
description: |
  资产老化预警分析。扫描家庭资产，识别即将到期、老化、高维护成本或闲置产生费用的资产，
  并给出处置建议。

trigger_phrases:
  - 老化预警
  - 资产到期
  - 维护成本过高
  - 闲置资产费用

allowed-tools: []

---

## 适用场景

家庭资产老化预警分析，识别需要关注或处置的资产。

## 输入约束

- 输入为已脱敏的家庭资产数据（资产名称、类别、购买日期、预期寿命、维护成本、使用频率）
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析资产状况，指出老化、高维护、闲置成本等问题
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
[
  {
    "asset_name": "资产名称",
    "alert_type": "aging",
    "severity": "high",
    "suggestion": "处置建议",
    "remaining_life_days": 30,
    "daily_cost": 1.5
  }
]
-->

## 字段说明

- `alert_type`: aging（老化）| high_maintenance（高维护）| idle_cost（闲置费用）
- `severity`: low | medium | high
- `remaining_life_days`: 预估剩余寿命天数（可选）
- `daily_cost`: 每日持有成本（可选，元）

## 边界限制

- 严禁提供投资建议
- 使用观察性语言：「观察到」「建议关注」「数据显示」
- 禁止使用确定性语言：「必须」「一定会」