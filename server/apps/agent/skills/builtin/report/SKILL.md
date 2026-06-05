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
{"overall_score": 65, "data_completeness_score": 80, "net_worth_health": {"score": 4, "narrative": "**净资产基础良好**，总资产2800万，月环比增长1.2%。\n\n资产规模在同类家庭中处于**中上水平**，但需关注增长趋势的持续性。", "suggestions": ["建议保持当前储蓄节奏，关注月环比变化", "可考虑将部分流动资金配置为低风险理财产品"]}, "allocation_analysis": {"score": 2, "narrative": "**房产占比95%过于集中**，流动资产仅占2%，金融资产占3%。\n\n资产流动性严重不足，一旦需要大额支出可能面临变现困难。", "suggestions": ["建议逐步将资产配置向金融资产倾斜，目标流动资产占比≥10%", "可设置每月定投计划分散房产风险", "关注定期存款到期时间，提前规划资金用途"]}, "liability_pressure": {"score": 3, "narrative": "**资产负债率51%偏高**，3笔贷款中2笔为房贷，月供占比约45%。\n\n虽然负债以房贷为主（相对良性），但月供占收入比例接近警戒线。", "suggestions": ["建议控制月供占收入比在40%以内", "如有提前还贷能力，优先偿还利率较高的贷款"]}, "asset_efficiency": {"score": 2, "narrative": "**低效资产5项**，日均持有成本约380元，主要集中在闲置电子产品和未使用家电。\n\n这些资产的使用频率低但折旧持续，拉低了整体资产效率。", "suggestions": ["建议对闲置超过6个月的资产考虑二手出售或捐赠", "未来购置大件前设置7天冷静期，减少冲动消费"]}, "summary": "家庭净资产较高但**资产配置过于集中在房产**，流动性严重不足。\n\n**核心建议：**\n1. 逐步优化配置，提升流动资产占比\n2. 控制月供比例，缓解负债压力\n3. 盘活低效资产，降低持有成本"}
-->

**字段说明：**
- `overall_score`: 20-100 整数。公式：round((net_worth_health.score * 0.30 + allocation_analysis.score * 0.25 + liability_pressure.score * 0.25 + asset_efficiency.score * 0.20) * 20)
- `data_completeness_score`: 0-100，数据录入完整度
- 四个维度 score: 1-5 整数（1=很差 2=较差 3=一般 4=良好 5=优秀）
- `narrative`: 每个维度 150-350 字中文说明，**必须使用 markdown 格式**：
  - 用 `**加粗**` 突出关键结论
  - 用 `\n\n` 分段（结论段 + 展开段）
  - 可使用有序/无序列表展开细节
  - 禁止使用标题（#），禁止使用表格
- `suggestions`: 每个维度 2-3 条具体建议，每条 15-40 字，使用观察性语言
- `summary`: 100-250 字综合总结，**必须使用 markdown 格式**：
  - 用 `**加粗**` 突出核心问题
  - 用有序列表列出核心建议（2-4条）
  - 禁止使用标题（#），禁止使用表格

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
