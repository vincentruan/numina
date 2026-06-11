---
# Capability Registry frontmatter (for /api/v1/ai/capabilities discovery)
capability: report_structured
name: 报告结构化转换
description: 将markdown报告转换为结构化JSON格式（Phase 2）
category: report
icon: file-markdown
color: "#1890ff"
route: /ai/report
input_mode: trigger
allowed_roles: [member, owner]

# DeerFlow skill frontmatter (for skill dispatch)
skill_name: report_structured
skill_description: 家庭资产报告结构化转换（Phase 2）。读取markdown报告文件，转换为结构化JSON格式。
trigger_phrases:
  - 结构化报告
  - 转换报告格式
allowed-tools:
  - numina-files_read_file
thinking: false
max_tokens: 2000
---

## 最重要的规则（必须遵守）

1. **仅输出 JSON 格式**，不要有任何 markdown 或其他内容
2. **JSON 必须合法**：无尾逗号、无注释、字符串正确转义
3. **仅使用 ```json 代码块包裹**
4. **narrative 字段禁止使用 markdown 表格**，必须使用列表格式

## 适用场景

将已生成的 markdown 格式家庭资产报告转换为结构化 JSON，供前端展示使用。

## 输入来源

系统会提供 markdown 报告文件路径，使用 `read_file` 工具读取内容。

## 工作流程

1. 使用 `read_file` 工具读取 markdown 报告
2. 解析报告内容，提取各维度分析
3. 构建 JSON 结构（见下方 schema）
4. 输出 ```json 包裹的完整 JSON

## JSON 输出格式

```json
{
  "overall_score": 65,
  "data_completeness_score": 80,
  "summary": "家庭净资产较高但**资产配置过于集中在房产**，流动性严重不足。\n\n**核心建议**:\n1. 逐步优化配置，提升流动资产占比\n2. 控制月供比例，缓解负债压力\n3. 盘活低效资产，降低持有成本",
  "indicators": [
    {
      "key": "net_worth_health",
      "label": "净资产健康度",
      "score": 4,
      "narrative": "**分析结论**\n\n- 总资产2800万，月环比增长1.2%\n- 资产规模在同类家庭中处于**中上水平**\n- 净资产基础良好，需关注增长趋势的持续性",
      "suggestions": [
        "保持当前储蓄节奏，关注月环比变化",
        "可考虑将部分流动资金配置为低风险理财产品"
      ],
      "data": {
        "net_worth": 28000000,
        "mom_change_pct": 1.2
      }
    },
    {
      "key": "allocation_analysis",
      "label": "资产配置分析",
      "score": 2,
      "narrative": "**分析结论**\n\n- 房产占比95%过于集中\n- 流动资产仅占2%，金融资产占3%\n- 资产流动性严重不足",
      "suggestions": [
        "逐步将资产配置向金融资产倾斜，目标流动资产占比≥10%",
        "可设置每月定投计划分散房产风险"
      ],
      "data": {
        "items": [
          {"category_name": "房产", "percentage": 95},
          {"category_name": "流动资产", "percentage": 2},
          {"category_name": "金融资产", "percentage": 3}
        ]
      }
    },
    {
      "key": "liability_pressure",
      "label": "负债压力评估",
      "score": 3,
      "narrative": "**分析结论**\n\n- 资产负债率51%偏高\n- 3笔贷款中2笔为房贷\n- 月供占比约45%，接近警戒线",
      "suggestions": [
        "控制月供占收入比在40%以内",
        "如有提前还贷能力，优先偿还利率较高的贷款"
      ],
      "data": {
        "liability_ratio": 51,
        "monthly_payment_ratio": 45
      }
    }
  ]
}
```

## 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `overall_score` | integer(1-100) | 综合评分 |
| `data_completeness_score` | integer(0-100) | 数据录入完整度评分 |
| `summary` | string | markdown格式的综合总结 |
| `indicators` | array | 弹性指标数组（3-8个） |
| `indicators[].key` | string | 指标唯一标识（snake_case） |
| `indicators[].label` | string | 指标显示名称 |
| `indicators[].score` | integer(1-5) | 指标评分（1=很差 5=优秀） |
| `indicators[].narrative` | string | markdown格式的分析文本（禁止表格） |
| `indicators[].suggestions` | array[string] | 2-3条改善建议 |
| `indicators[].data` | object | 可选的数据可视化字段 |

## narrative 字段正确格式

**推荐：使用无序列表**
```json
"narrative": "**分析结论**\n\n- 观察点1\n- 观察点2\n- 观察点3"
```

**禁止：使用 markdown 表格**
```json
// ❌ 错误格式 - 表格会导致解析失败
"narrative": "| 项目 | 金额 |\n|---|---|\n| 房产 | 2650万 |"
```

## 指标 key 映射建议

| 常见指标 | 建议 key |
|---------|---------|
| 净资产健康度 | `net_worth_health` |
| 资产配置分析 | `allocation_analysis` |
| 负债压力评估 | `liability_pressure` |
| 资产效率分析 | `asset_efficiency` |
| 流动性分析 | `liquidity_analysis` |
| 风险评估 | `risk_assessment` |
| 增长潜力 | `growth_potential` |

## 关键规则

- 仅输出 JSON，不要有任何其他内容
- JSON 必须合法：无尾逗号、无注释
- `indicators` 数组弹性输出（根据报告内容，3-8个）
- 所有文本字段用中文
- narrative 禁止表格，使用列表格式
- 数据不完整时在 summary 中注明

## 再次提醒

你的回答**必须**只有这一种格式：

```json
{...完整JSON对象...}
```

没有这个 JSON 块，前端将无法正确展示报告。