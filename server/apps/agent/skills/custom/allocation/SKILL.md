---
name: allocation
description: |
  资产配置偏离分析。检查家庭资产配置是否偏离目标配置，给出调整建议。

trigger_phrases:
  - 配置偏离
  - 资产配置检查
  - 配置分析
  - 偏离预警

allowed-tools: []

---

## 适用场景

检查家庭资产配置是否偏离预设目标，识别需要调整的类别。

## 输入约束

- 输入为已脱敏的家庭资产配置数据和目标配置
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析配置偏离状况，指出需要关注的类别
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
{
  "has_significant_drift": true,
  "narrative": "配置偏离分析摘要",
  "drifts": [
    {
      "category": "physical",
      "target_pct": 50,
      "current_pct": 65,
      "drift": 15,
      "exceeds_threshold": true
    }
  ]
}
-->

## 字段说明

- `has_significant_drift`: 是否存在显著偏离
- `narrative`: 分析摘要（可选）
- `drifts`: 各类别偏离详情
  - `category`: 类别名称
  - `target_pct`: 目标占比
  - `current_pct`: 当前占比
  - `drift`: 偏离幅度（百分比）
  - `exceeds_threshold`: 是否超出阈值

## 边界限制

- 严禁提供具体投资调整建议
- 使用观察性语言：「观察到」「建议关注」