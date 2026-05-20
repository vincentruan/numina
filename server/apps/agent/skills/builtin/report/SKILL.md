---
name: report
description: |
  家庭资产健康报告。综合分析家庭财务状况，输出评分、风险标记和建议。

trigger_phrases:
  - 资产报告
  - 健康报告
  - 财务体检
  - 资产分析

allowed-tools: []

---

## 适用场景

生成家庭资产健康状况综合报告。

## 输入约束

- 输入为已脱敏的家庭资产、负债、现金流数据
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求

1. 首先用自然语言分析家庭财务状况，指出健康程度和风险点
2. 然后在分析末尾输出结构化数据块，格式如下：

<!-- STRUCTURED_DATA
{
  "overall_score": 75,
  "data_completeness_score": 85,
  "narrative": "综合分析摘要",
  "sections": {
    "health": {"score": 4, "label": "良好"},
    "allocation": {"score": 3, "label": "一般"},
    "risk": {"score": 4, "label": "良好"}
  }
}
-->

## 字段说明

- `overall_score`: 整体健康评分（0-100）
- `data_completeness_score`: 数据完整度评分（0-100）
- `narrative`: 综合分析摘要（可选）
- `sections`: 各维度评分详情（可选）

## 边界限制

- 严禁提供投资建议
- 使用观察性语言：「观察到」「数据显示」
- 数据不完整时注明「数据可能不完整」