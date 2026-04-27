# Phase 5：金融文档智能导入设计文档

**日期：** 2026-04-27  
**状态：** 已批准  
**范围：** PDF 金融账单智能解析，提取持仓快照，更新 Numina 资产数据

---

## 1. 背景与目标

### 用户场景

- **定期对账**：用户每月收到券商日结单/银行账单，希望快速同步最新持仓到 Numina，减少手动录入
- **历史数据迁移**：首次使用 Numina 时，批量导入过去账单建立历史基线

### 设计约束

- 仅处理**资产/负债**概念，不引入交易流水、信用卡消费记录等新概念
- 聚焦**持仓快照**：从 PDF 提取当前持仓（名称、数量、市值），映射到现有金融资产模型
- 当识别出的资产在 Numina 中已存在时，**自动更新**（用新市值覆盖旧数据）
- 支持**通用金融文档**，不限机构，LLM 尽力解析，识别失败给明确提示

---

## 2. 架构设计

### 数据流

```
用户上传 PDF
    → Frontend (Vant 文件上传组件)
    → POST /api/v1/import/parse        (Backend)
    → Backend 提取 PDF 文本 (pdfplumber)
    → POST /agent/import/parse         (Agent 微服务，内部调用)
    → Agent 调用 LLM，返回结构化 JSON
    → Backend 返回 ImportPreview 给前端
    → 用户在预览页检查/编辑后确认
    → POST /api/v1/import/confirm      (Backend)
    → Backend 执行资产匹配 + 更新/创建
```

### 技术选型

| 组件 | 技术 | 说明 |
|------|------|------|
| PDF 文本提取 | `pdfplumber` | Backend 侧，处理原生 PDF；扫描件返回错误 |
| LLM 解析 | Agent 微服务现有 LLM 基础设施 | 结构化提取持仓数据 |
| 资产匹配 | 精确匹配 > 模糊匹配 | 按名称匹配现有资产，决定 update/create |
| 前端预览 | Vue 3 + Vant Table | 可编辑表格，支持逐行确认 |

---

## 3. 接口设计

### 3.1 Backend 新增路由

**文件：** `backend/app/routers/import_report.py`  
**前缀：** `/import`

#### `POST /import/parse`

接收 PDF 文件，提取文本，调用 Agent 解析，返回预览数据。

**请求：** `multipart/form-data`，字段 `file`（PDF）

**响应：**
```json
{
  "source": "华泰证券",
  "report_date": "2026-04-01",
  "items": [
    {
      "temp_id": "tmp_001",
      "name": "贵州茅台",
      "asset_type": "financial",
      "category_hint": "股票",
      "current_value": 158000.00,
      "currency": "CNY",
      "quantity": 100,
      "notes": "",
      "matched_asset_id": "uuid-or-null",
      "matched_asset_name": "贵州茅台 600519",
      "action": "update",
      "warning": null
    }
  ]
}
```

**错误响应：**
- `400` — PDF 无法提取文本（扫描件）
- `422` — LLM 未能识别出资产信息
- `504` — Agent 调用超时（30s）

#### `POST /import/confirm`

接收用户确认后的数据，执行写入。

**请求：**
```json
{
  "items": [
    {
      "temp_id": "tmp_001",
      "name": "贵州茅台",
      "asset_type": "financial",
      "category_hint": "股票",
      "current_value": 158000.00,
      "currency": "CNY",
      "matched_asset_id": "uuid-or-null",
      "action": "update"
    }
  ]
}
```

**响应：**
```json
{
  "updated": 2,
  "created": 1,
  "skipped": 0
}
```

### 3.2 Agent 新增路由

**文件：** `agent/app/routers/import_parse.py`  
**前缀：** `/import`（Agent 内部接口，不对外暴露）

#### `POST /import/parse`

**请求：**
```json
{
  "text": "...PDF 提取的原始文本..."
}
```

**响应：**
```json
{
  "source": "华泰证券",
  "report_date": "2026-04-01",
  "items": [
    {
      "name": "贵州茅台",
      "asset_type": "financial",
      "category_hint": "股票",
      "current_value": 158000.00,
      "currency": "CNY",
      "quantity": 100
    }
  ]
}
```

**LLM Prompt 要点：**
- 要求输出严格 JSON，不输出解释文字
- 明确告知只提取持仓/资产信息，忽略交易流水
- 识别不到时返回 `{"items": []}`，不抛异常

---

## 4. 数据模型

### ImportPreviewItem（前端预览用，不持久化）

| 字段 | 类型 | 说明 |
|------|------|------|
| temp_id | str | 前端临时 ID，用于追踪编辑 |
| name | str | 资产名称 |
| asset_type | str | `financial` / `physical` |
| category_hint | str | LLM 推断的分类名（如"股票"） |
| current_value | Decimal | 当前市值 |
| currency | str | 货币代码，默认 CNY |
| quantity | float \| None | 持仓数量（股票/基金适用） |
| notes | str \| None | 备注 |
| matched_asset_id | UUID \| None | 匹配到的现有资产 ID |
| matched_asset_name | str \| None | 匹配到的现有资产名称 |
| action | str | `update` / `create` |
| warning | str \| None | 字段缺失等警告信息 |

### 资产匹配逻辑

1. **精确匹配**：`Asset.name == item.name`（同一家庭内）
2. **模糊匹配**：名称包含关系（`item.name in Asset.name` 或反向）
3. **无匹配**：`action = "create"`，`matched_asset_id = null`

---

## 5. 前端设计

### 页面：`ImportReportPage.vue`

**入口：** 设置页 → 数据管理 → 导入账单

**流程：**

```
[上传区域]
  Vant Uploader，限 PDF，单文件，最大 10MB
  上传后显示加载状态（"正在解析中..."）

[解析结果预览]
  表格展示 items，列：资产名称 | 类型 | 当前市值 | 操作（更新/新建）| 匹配资产
  警告行高亮显示，支持内联编辑名称和金额
  底部显示汇总：将更新 X 条，新建 Y 条

[确认按钮]
  "确认导入" → 调用 /import/confirm → 显示结果 Toast
```

### 错误提示（中文）

| 场景 | 提示文字 |
|------|---------|
| 扫描件 PDF | 无法读取此 PDF，请确认文件非扫描件 |
| LLM 未识别 | 未能从文档中识别出资产信息，请检查文件是否为金融账单 |
| 超时 | 解析超时，请稍后重试 |
| 部分字段缺失 | 该条目信息不完整，请手动补充后确认 |

---

## 6. 错误处理

**三类失败场景：**

1. **PDF 无法提取文本**（扫描件/图片 PDF）
   - Backend 检测到 `pdfplumber` 提取文本为空
   - 返回 `400`，不调用 Agent

2. **LLM 识别失败**（格式不认识/内容不相关）
   - Agent 返回 `items: []`
   - Backend 返回 `422`，前端展示明确提示

3. **部分字段缺失**（识别出资产名但没有金额）
   - 预览中该行标记 `warning` 字段
   - 前端高亮显示，用户可手动补填后确认
   - 不阻止其他行的导入

**失败时不写入任何数据。**

---

## 7. 测试策略

### Agent 解析测试（`agent/tests/test_import_parse.py`）

- mock LLM 响应，验证结构化输出格式正确
- 验证 LLM 返回空 items 时的处理
- 验证 prompt 构造逻辑

### Backend 路由测试（`backend/tests/test_import_report.py`）

- mock Agent 调用，验证 `/import/parse` 正常流程
- 验证 PDF 文本为空时返回 400
- 验证 Agent 返回空 items 时返回 422
- 验证 `/import/confirm` 的 update 路径（已有资产）
- 验证 `/import/confirm` 的 create 路径（新资产）

### 资产匹配逻辑测试

- 精确匹配命中
- 模糊匹配命中
- 无匹配 → create
- 同名资产属于不同家庭时不跨家庭匹配

---

## 8. 不在范围内

- 交易流水导入（消费记录、转账记录）
- 信用卡账单解析（账单金额、还款日等）
- 扫描件 OCR（需要额外 OCR 服务）
- 异步任务队列（同步调用 + 30s 超时已足够）
- 机构模板维护（全 LLM，无规则引擎）
- 自动定时同步（手动上传触发）
