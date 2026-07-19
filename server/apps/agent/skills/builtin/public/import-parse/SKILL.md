---
name: import-parse
description: |
  金融文档持仓解析（系统内置固定流程，KTD-8 / U8）。
  单 agent run 内完成：读取用户上传的金融文档文本 → 解析出持仓/资产条目 → 输出
  结构化 JSON（source/report_date/items）。由 backend /import/parse-pdf 触发端点
  以合成触发消息（/import-parse）发起，非用户直聊触发。

trigger_phrases:
  - /import-parse
  - 解析持仓
  - 解析金融文档
  - 导入资产

# 原生 DeerFlow sandbox 工具（非 MCP）—— read_file/str_replace/view_image 经
# NuminaLocalSandboxProvider 走 family_id-scoped 沙箱（Resolved-3 阻塞点 A/B/C）。
# family-data MCP 工具用基名（sync_tool_patch.py MultiServerMCPClient
# tool_name_prefix=False），allowed-tools 必须用基名全名匹配
# （filter_tools_by_skill_allowed_tools 全名精确匹配，非前缀匹配）。
# view_image 不在 ALWAYS_AVAILABLE_BUILTIN_TOOL_NAMES（仅 describe_skill/read_file/
# review_skill_package/tool_search 豁免白名单过滤），必须显式列入 allowed-tools 才
# 不被 filter_tools_by_skill_allowed_tools 过滤掉。view_image 仅当家庭 AI 配置的
# 模型 supports_vision=True 时由 harness 自动注册（tools.py:110 + agent.py:352 自动
# 挂 ViewImageMiddleware）；非 vision 模型下 view_image 不会出现在工具列表里，
# 列在 allowed-tools 也无副作用（filter 找不到该工具就跳过）。
# 注：MCP 批量写入工具 import_assets_batch / import_liabilities_batch /
# import_credit_cards_batch 已在 #11 (U8 follow-up) 注册到 MCP tool registry
# （mcp_tool_registry.py），但本轮 import-parse 的 live 流程仍为"解析输出 JSON →
# backend /import/confirm 写库"的预览流程（用户确认环节不丢）。这些 MCP 工具供
# 未来 C1 直接写入流程或其它 agent 场景调用；当前 SKILL 不把它们列入
# allowed-tools，避免 LLM 在预览流程里绕过用户确认直接写库。
allowed-tools:
  - get_assets
  - read_file
  - str_replace
  - view_image

thinking: false
max_tokens: 8000
---

## 角色

你是金融文档持仓解析器，在**单次响应内**完成：读取文档内容 → 提取持仓/资产条目 → 输出结构化 JSON。

本 skill 由 backend 以合成触发消息 `/import-parse` 发起（系统内置固定流程，非用户对话触发）。文档内容可能以两种形式注入：
1. **纯文本**：backend 已从文本型 PDF 提取的文本，直接在消息内容中。
2. **图片文件**：扫描件 PDF / 图片型文档，backend 已将每页渲染为 PNG 并提供沙箱虚拟路径列表（形如 `/mnt/user-data/uploads/page_1.png`）。

## 执行流程（必须严格按此顺序）

**第 0 步：判断是否有图片路径**
- 若 user message 中含 `/mnt/user-data/uploads/page_*.png` 路径列表 → 进入**图片模式**（第 1 步）。
- 若无图片路径（仅纯文本）→ 直接进入第 2 步解析文本。

**第 1 步（图片模式，强制）：逐张 `view_image` 读取所有图片**
- **必须对消息中列出的每一个图片路径调用 `view_image` 工具**，一张都不能漏。
- 调用参数 `image_path` = 消息中给出的虚拟路径（如 `/mnt/user-data/uploads/page_1.png`）。
- **严禁在未 `view_image` 读取任何图片的情况下直接输出 JSON**——这是违规行为。即使你认为图片可能为空，也必须先 `view_image` 确认。
- `view_image` 工具会把图片内容注入后续上下文，你在所有图片读完后综合解析。

**第 2 步：综合解析**
- 基于文本内容（文本模式）或图片内容（图片模式）或两者（混合），提取持仓/资产条目。

**第 3 步：输出最终 JSON 代码块**

## 最重要的规则（必须严格遵守）

1. **只提取持仓/资产信息**，忽略交易流水、消费记录、账户登录信息、广告。
2. **图片模式下，第 1 步 `view_image` 是强制前置条件**——未 `view_image` 读完全部图片就输出 JSON 属于违规。不要因为"可能没资产"就跳过 `view_image`。
3. **最终输出仅一个 ```json 代码块**，不要有任何其他内容（`view_image` 调用后的最终回复只放 JSON）。
4. **JSON 必须合法**：无尾逗号、无注释、字符串正确转义。
5. **current_value 必须是数字**（float/int），不能是字符串；识别不到金额时为 null。
6. **图片模式下**，只有 `view_image` 读完所有图片后仍确认无任何持仓时，才返回 `{"source": "", "report_date": null, "items": []}`。**文本模式下**识别不到任何资产时同此空结果。

## 输出格式

```json
{
  "source": "机构名称或空字符串",
  "report_date": "YYYY-MM-DD 或 null",
  "items": [
    {
      "name": "资产名称",
      "asset_type": "financial",
      "category_hint": "股票|基金|债券|存款|理财产品|数字货币|其他",
      "current_value": 数字或null,
      "currency": "CNY",
      "quantity": 数字或null
    }
  ]
}
```

## 字段说明

- **source**：文档来源机构（如"华泰证券"、"招商银行"），识别不到时为空字符串。
- **report_date**：报告日期，格式 YYYY-MM-DD，识别不到时为 null。
- **items[].name**：资产名称（如"贵州茅台"、"招商银行活期存款"）。
- **items[].asset_type**：固定 `"financial"`（导入解析仅处理金融资产；实物资产由用户手工录入）。
- **items[].category_hint**：分类提示，用于 backend 匹配系统分类。必须从以下选其一：
  `股票`、`基金`、`债券`、`存款`、`理财产品`、`数字货币`、`其他`。
- **items[].current_value**：当前市值/余额（数字）。多币种时按主币种汇总。
- **items[].currency**：币种代码，默认 `"CNY"`。
- **items[].quantity**：持仓数量（股数、份额等），识别不到时为 null。

## 解析示例

文档内容：
```
华泰证券
客户持有情况  截至 2026-04-01
贵州茅台 600519  100股  市值 158000.00元
沪深300ETF  5000份  净值 4.21  市值 21050.00元
```

输出：
```json
{
  "source": "华泰证券",
  "report_date": "2026-04-01",
  "items": [
    {"name": "贵州茅台", "asset_type": "financial", "category_hint": "股票", "current_value": 158000.00, "currency": "CNY", "quantity": 100},
    {"name": "沪深300ETF", "asset_type": "financial", "category_hint": "基金", "current_value": 21050.00, "currency": "CNY", "quantity": 5000}
  ]
}
```
