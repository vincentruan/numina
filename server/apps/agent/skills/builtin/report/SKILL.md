---
name: report
description: |
  家庭资产健康报告。综合分析家庭财务状况，输出评分、风险标记和建议。

trigger_phrases:
  - 资产报告
  - 健康报告
  - 财务体检
  - 资产分析
  - 资产体检
  - 体检报告
  - 生成报告
  - 生成家庭资产体检报告

allowed-tools:
  - numina-family-data_get_family_overview
  - numina-family-data_get_assets
  - numina-family-data_get_liabilities
  - numina-family-data_get_members
  - numina-family-data_get_recent_alerts

---

## 适用场景

生成家庭资产健康状况综合报告。

## 工作流程

1. 使用工具获取家庭数据（overview、assets、liabilities、members）
2. 分析数据，计算各维度评分
3. 生成自然语言分析报告
4. **必须**在输出末尾附加结构化数据块

## 输入约束

- 输入为已脱敏的家庭资产、负债、现金流数据
- 不包含真实金额（已脱敏为区间或比例）

## 输出格式要求（必须严格遵守）

先用自然语言分析家庭财务状况。分析完成后，**必须**在回答的最末尾输出如下结构化数据块：

```
<!-- STRUCTURED_DATA
{
  "overall_score": <20-100整数>,
  "data_completeness_score": <0-100数值>,
  "net_worth_health": {
    "score": <1-5整数>,
    "narrative": "<50-100字的净资产健康状况分析>"
  },
  "allocation_analysis": {
    "score": <1-5整数>,
    "narrative": "<50-100字的资产配置分析>"
  },
  "liability_pressure": {
    "score": <1-5整数>,
    "narrative": "<50-100字的负债压力分析，无负债时score给5>"
  },
  "asset_efficiency": {
    "score": <1-5整数>,
    "narrative": "<50-100字的资产效率分析>"
  },
  "summary": "<100-150字的综合总结和核心建议>"
}
-->
```

## 评分规则

- 各维度评分：1=很差，2=较差，3=一般，4=良好，5=优秀
- overall_score 计算公式：round((net_worth_health.score * 0.30 + allocation_analysis.score * 0.25 + liability_pressure.score * 0.25 + asset_efficiency.score * 0.20) * 20)
- overall_score 范围：20（全1分）到 100（全5分）

## 关键规则

- **绝对不可省略** `<!-- STRUCTURED_DATA ... -->` 块，即使分析文本很长
- 结构化数据块必须是输出的最后一部分内容
- JSON 必须是合法的，不能有尾逗号或注释
- narrative 字段用中文

## 边界限制

- 严禁提供投资建议
- 使用观察性语言：「观察到」「数据显示」
- 数据不完整时注明「数据可能不完整」
