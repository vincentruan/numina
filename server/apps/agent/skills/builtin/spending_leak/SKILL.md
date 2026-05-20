---
name: spending_leak
description: |
  消费漏洞分析。识别家庭中产生隐性浪费的资产，如高闲置成本、冗余订阅、高维护费用。

trigger_phrases:
  - 消费漏洞
  - 隐性浪费
  - 闲置成本
  - 订阅冗余

allowed-tools: []

---

## 适用场景

识别家庭财务中的隐性浪费，帮助节省开支。

## 输入约束

- 输入为已脱敏的家庭资产和支出数据
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析消费漏洞状况，指出浪费来源和节省建议
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
[
  {
    "asset_name": "资产/项目名称",
    "leak_type": "high_idle_cost",
    "severity": "medium",
    "estimated_annual_waste": 1200,
    "suggestion": "取消订阅或处置资产"
  }
]
-->

## 字段说明

- `leak_type`: high_idle_cost（高闲置成本）| redundant（冗余订阅/重复）| high_maintenance（高维护费用）
- `severity`: low | medium | high
- `estimated_annual_waste`: 预估年浪费金额（可选，元）

## 边界限制

- 严禁承诺具体节省金额
- 使用观察性语言：「预估」「建议」「可能」