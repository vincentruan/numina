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

你的回答**必须**严格遵循以下格式，否则系统将无法解析：

1. **仅输出 ```json 代码块**，不要有任何其他内容
2. **不要在 JSON 前后添加任何文字解释**
3. **JSON 必须合法**：无尾逗号、无注释、字符串正确转义
4. **narrative 字段使用列表格式**，不要使用 markdown 表格（表格格式容易出错）

## ⚠️⚠️⚠️ 禁止使用 Markdown 表格 ⚠️⚠️⚠️

**绝对禁止**在 `narrative` 字段中使用 Markdown 表格格式。表格会导致前端解析失败，显示"结构化结果落库失败"错误。

**❌ 错误格式 - 绝对禁止：**
```json
"narrative": "| 资产类型 | 金额 | 占比 |\n|---|---|---|\n| 房产 | ¥2650万 | 95% |"
```

```json
"narrative": "| 项目 | 状态 |\n|---|---|\n| 活期存款 | ⚠️ 占比过高 |"
```

**✅ 正确格式 - 使用列表：**
```json
"narrative": "**房产占比95%过于集中**\n\n- 房产资产约¥2650万，占总资产95%\n- 流动资产仅占2%，金融资产占3%\n- 资产流动性严重不足"
```

```json
"narrative": "**活期存款占比过高**\n\n- 活期存款约¥870,000，仅覆盖约1.2个月支出\n- 建议配置部分资金为低风险理财产品\n- 可设置每月定投计划分散风险"
```

**⚠️ 转换提示：** 如果你发现自己在写表格格式（包含 `|` 分隔符），立即停止并转换为无序列表格式！

## narrative 字段正确格式示例

**推荐：使用无序列表**
```json
"narrative": "**活期存款占比过高**\n\n- 活期存款约¥870,000，仅覆盖约1.2个月支出\n- 建议配置部分资金为低风险理财产品\n- 可设置每月定投计划分散风险"
```

**禁止：使用 markdown 表格**
```json
// ❌ 错误格式 - 表格容易解析失败
"narrative": "| 活期存款 | ¥870,000 | ⚠️ 仅覆盖1.2个月支出 |"
```

**表格 → 列表转换示例：**

如果你想写表格：
```
| 指标 | 当前值 | 建议 |
|---|---|---|
| 月供占比 | 45% | 控制在40%以内 |
| 流动资产 | 2% | 提升至10% |
```

转换为列表：
```
**关键指标分析**

- **月供占比45%**：接近警戒线，建议控制在40%以内
- **流动资产占比2%**：严重偏低，目标提升至10%以上
```

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

## 工作流程

1. 使用工具获取家庭数据（overview、assets、liabilities、members）
2. 分析数据，计算各维度评分
3. 构建JSON对象，各维度的narrative字段包含markdown格式的分析文本
4. 输出 ```json 包裹的完整JSON

## 输出格式（唯一允许的格式）

```json
{
  "overall_score": 65,
  "data_completeness_score": 80,
  "net_worth_health": {
    "score": 4,
    "narrative": "**净资产基础良好**\n\n- 总资产2800万，月环比增长1.2%\n- 资产规模在同类家庭中处于**中上水平**\n- 需关注增长趋势的持续性", // ✅ 使用列表，禁止表格
    "suggestions": [
      "建议保持当前储蓄节奏，关注月环比变化",
      "可考虑将部分流动资金配置为低风险理财产品"
    ]
  },
  "allocation_analysis": {
    "score": 2,
    "narrative": "**房产占比95%过于集中**\n\n- 流动资产仅占2%，金融资产占3%\n- 资产流动性严重不足\n- 一旦需要大额支出可能面临变现困难", // ✅ 使用列表，禁止表格
    "suggestions": [
      "建议逐步将资产配置向金融资产倾斜，目标流动资产占比≥10%",
      "可设置每月定投计划分散房产风险",
      "关注定期存款到期时间，提前规划资金用途"
    ]
  },
  "liability_pressure": {
    "score": 3,
    "narrative": "**资产负债率51%偏高**\n\n- 3笔贷款中2笔为房贷\n- 月供占比约45%，接近警戒线\n- 负债以房贷为主（相对良性）", // ✅ 使用列表，禁止表格
    "suggestions": [
      "建议控制月供占收入比在40%以内",
      "如有提前还贷能力，优先偿还利率较高的贷款"
    ]
  },
  "asset_efficiency": {
    "score": 2,
    "narrative": "**低效资产5项**\n\n- 日均持有成本约380元\n- 主要集中在闲置电子产品和未使用家电\n- 使用频率低但折旧持续", // ✅ 使用列表，禁止表格
    "suggestions": [
      "建议对闲置超过6个月的资产考虑二手出售或捐赠",
      "未来购置大件前设置7天冷静期，减少冲动消费"
    ]
  },
  "summary": "家庭净资产较高但**资产配置过于集中在房产**，流动性严重不足。\n\n**核心建议：**\n1. 逐步优化配置，提升流动资产占比\n2. 控制月供比例，缓解负债压力\n3. 盘活低效资产，降低持有成本"
}
```

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `overall_score` | integer(20-100) | 综合评分。公式：round((net_worth_health.score×0.30 + allocation_analysis.score×0.25 + liability_pressure.score×0.25 + asset_efficiency.score×0.20) × 20) |
| `data_completeness_score` | integer(0-100) | 数据录入完整度评分 |
| 各维度 `score` | integer(1-5) | 1=很差 2=较差 3=一般 4=良好 5=优秀 |
| 各维度 `narrative` | string(150-350字) | markdown格式的分析文本。**必须**用`**加粗**`突出关键结论，用`\n\n`分段 |
| 各维度 `suggestions` | array[string] | 2-3条建议，每条15-40字，使用观察性语言 |
| `summary` | string(100-250字) | markdown格式的综合总结。用`**加粗**`突出核心问题，用有序列表列出建议 |

## 关键规则

- **仅输出JSON**，不要输出任何markdown报告正文或其他内容
- JSON必须合法：无尾逗号、无注释、正确转义
- 所有文本字段用中文
- 严禁投资建议，使用观察性语言：「观察到」「数据显示」
- 数据不完整时注明「数据可能不完整」

## 再次提醒

你的回答**必须**只有这一种格式：

```json
{...完整JSON对象...}
```

没有这个JSON块，报告将无法被系统处理。