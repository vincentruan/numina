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

## 最重要的规则（必须遵守）

你的回答**必须**以 `<!-- STRUCTURED_DATA ... -->` 结尾。无论报告内容多长，最后一行必须是结构化数据块。如果你没有输出这个块，系统将无法解析你的报告，生成将被视为失败。

## 适用场景

生成家庭资产健康状况综合报告。

## 工具使用规则

**只使用这些工具获取数据：**
- `numina-family-data_get_family_overview`
- `numina-family-data_get_assets`
- `numina-family-data_get_liabilities`
- `numina-family-data_get_members`
- `numina-family-data_get_recent_alerts`

**严禁使用 write_file、bash、code_execution 等其他工具。**
报告直接输出为文本，不要尝试保存文件。

## 工作流程

1. 使用工具获取家庭数据（overview、assets、liabilities、members）
2. 分析数据，计算各维度评分
3. 用中文生成自然语言分析报告
4. **最后一步：必须在回答的最末尾输出 `<!-- STRUCTURED_DATA ... -->` 块**

## 输出格式

先用中文分析家庭财务状况（800-2000字），然后**必须**输出结构化数据块。

### 报告正文示例结构

```
# 家庭资产体检报告

## 一、家庭概况
...（总资产、总负债、净资产、资产负债率）

## 二、资产结构分析
...

## 三、负债分析
...

## 四、风险提示
...

## 五、建议
...
```

### 结构化数据块（必须放在最末尾）

报告正文结束后，你**必须**紧跟输出如下格式的数据块：

<!-- STRUCTURED_DATA
{"overall_score": 65, "data_completeness_score": 80, "net_worth_health": {"score": 4, "narrative": "净资产2800万，基础良好"}, "allocation_analysis": {"score": 2, "narrative": "房产占比95%过于集中"}, "liability_pressure": {"score": 3, "narrative": "资产负债率51%偏高"}, "asset_efficiency": {"score": 2, "narrative": "流动资产仅占2%"}, "summary": "家庭净资产较高但资产配置过于集中在房产，流动性严重不足，建议逐步优化配置"}
-->

**字段说明：**
- `overall_score`: 20-100 整数。公式：round((net_worth_health.score * 0.30 + allocation_analysis.score * 0.25 + liability_pressure.score * 0.25 + asset_efficiency.score * 0.20) * 20)
- `data_completeness_score`: 0-100，数据录入完整度
- 四个维度 score: 1-5 整数（1=很差 2=较差 3=一般 4=良好 5=优秀）
- `narrative`: 每个维度 30-80 字中文说明
- `summary`: 80-150 字综合总结

## 关键规则

- **绝对不可省略** `<!-- STRUCTURED_DATA ... -->` 块
- 结构化数据块必须是输出的最后一部分
- JSON 必须合法，不能有尾逗号或注释
- 所有 narrative 和 summary 用中文
- 严禁提供投资建议，使用观察性语言：「观察到」「数据显示」
- 数据不完整时注明「数据可能不完整」

## 再次提醒

你的回答的最后几行必须是：
```
<!-- STRUCTURED_DATA
{...完整JSON...}
-->
```
没有这个块，报告将无法被系统处理。
