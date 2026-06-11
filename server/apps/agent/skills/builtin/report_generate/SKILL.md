---
# Capability Registry frontmatter (for /api/v1/ai/capabilities discovery)
capability: report_generate
name: 资产报告生成
description: 生成家庭资产健康报告markdown文件（Phase 1）
category: report
icon: file-text
color: "#52c41a"
route: /ai/report
input_mode: trigger
allowed_roles: [member, owner]

# DeerFlow skill frontmatter (for skill dispatch)
skill_name: report_generate
skill_description: 家庭资产健康报告生成（Phase 1）。调用MCP工具获取家庭数据，生成完整的markdown报告文件。
trigger_phrases:
  - 生成资产报告
  - 生成健康报告
  - 生成财务体检
allowed-tools:
  - numina-family-data_get_family_overview
  - numina-family-data_get_assets
  - numina-family-data_get_liabilities
  - numina-family-data_get_members
  - numina-family-data_get_recent_alerts
  - numina-files_write_file
thinking: false
max_tokens: 4000
---

---

## 最重要的规则（必须遵守）

1. **仅输出 markdown 格式的报告**，不要输出任何 JSON 或其他格式
2. **必须使用 write_file 工具保存报告文件**
3. **文件名格式**: `report_{YYYYMMDD_HHMMSS}.md`（例如：`report_20260611_100530.md`）
4. **保存路径**: 使用系统提供的 tenant reports 目录

## 适用场景

生成家庭资产健康状况综合报告，以 markdown 格式输出并保存到文件系统。

## 工作流程

1. 使用 MCP 工具获取家庭数据：
   - `get_family_overview` - 获取家庭总览（净资产、资产总计、负债总计）
   - `get_assets` - 获取资产列表和详情
   - `get_liabilities` - 获取负债列表和详情
   - `get_members` - 获取家庭成员信息
   - `get_recent_alerts` - 获取最近 alerts

2. 分析数据，构建多维度评估：
   - 净资产健康度（资产增长、净资产规模）
   - 资产配置分析（各类资产占比、流动性）
   - 负债压力评估（负债率、月供占比）
   - 资产效率分析（低效资产、持有成本）
   - 其他有价值的分析维度（弹性输出）

3. 生成 markdown 报告，包含：
   - 标题和生成时间
   - 综合评分（1-100）
   - 各维度详细分析（评分、叙述、建议）
   - 总结和核心建议

4. 使用 `write_file` 工具保存报告：
   ```
   write_file(path: "report_{timestamp}.md", content: "<markdown内容>")
   ```

## Markdown 报告格式模板

```markdown
# 家庭资产健康报告

**生成时间**: 2026-06-11 10:05:30
**数据完整度**: 80%

---

## 📊 综合评分

**总体评分**: 65/100

---

## 净资产健康度

**评分**: ★★★★☆ (4/5)

### 分析结论

- 总资产2800万，月环比增长1.2%
- 资产规模在同类家庭中处于**中上水平**
- 净资产基础良好，需关注增长趋势的持续性

### 改善建议

1. 保持当前储蓄节奏，关注月环比变化
2. 可考虑将部分流动资金配置为低风险理财产品

---

## 资产配置分析

**评分**: ★★☆☆☆ (2/5)

### 分析结论

- 房产占比95%过于集中
- 流动资产仅占2%，金融资产占3%
- 资产流动性严重不足

### 改善建议

1. 逐步将资产配置向金融资产倾斜，目标流动资产占比≥10%
2. 可设置每月定投计划分散房产风险

---

## 负债压力评估

**评分**: ★★★☆☆ (3/5)

### 分析结论

- 资产负债率51%偏高
- 3笔贷款中2笔为房贷
- 月供占比约45%，接近警戒线

### 改善建议

1. 控制月供占收入比在40%以内
2. 如有提前还贷能力，优先偿还利率较高的贷款

---

## 总结

家庭净资产较高但**资产配置过于集中在房产**，流动性严重不足。

**核心建议**:
1. 逐步优化配置，提升流动资产占比
2. 控制月供比例，缓解负债压力
3. 盘活低效资产，降低持有成本
```

## 关键规则

- 仅输出 markdown 格式报告
- 必须调用 write_file 工具保存文件
- 文件名使用 `report_{timestamp}.md` 格式
- 所有分析用中文，使用观察性语言
- 评分范围：各维度 1-5 星，综合 1-100 分
- 数据不完整时注明「数据可能不完整」

## 输出确认

完成报告生成后，在最后输出：

```
✅ 报告已生成并保存: report_20260611_100530.md
```