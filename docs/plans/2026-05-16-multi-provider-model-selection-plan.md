---
name: multi-provider-model-selection
status: active
created: 2026-05-16
origin: docs/brainstorms/2026-05-16-multi-provider-model-selection-requirements.md
---

# 多供应商智能模型选择系统 — 实施计划

## 问题框架

当前 `AIProviderConfig` 表每个家庭只有一条激活记录（`is_active=True`），包含一个主模型和一个视觉模型。本计划将其升级为多供应商多模型结构，支持供应商级熔断降级和基于任务特征的智能模型选择。

(see origin: docs/brainstorms/2026-05-16-multi-provider-model-selection-requirements.md)

---

## 关键决策与理由

### D1: 保留现有字段名，不重命名 `model_id`

现有 `model_id` 和 `vision_model_id` 字段**保留原名**，新增 `model_2_id`/`model_3_id` 作为额外槽位。理由：重命名需要更新所有读取 `ai_model_id` 的 agent 代码（orchestrator、family_adapter_cache、session journal），风险高于收益。迁移时 `model_1_capabilities` 对应 `model_id`，`model_2_capabilities` 对应 `vision_model_id`。

### D2: 废弃 `thinking_supported` 列，改用 `model_1_capabilities`

`thinking_supported` 列已存在但内部端点不读它（从 `AIProviderTestResult` 推断）。新增 `model_1_capabilities` JSON 列后，`thinking_supported` 保留但不再写入新值，内部端点改为从 `model_1_capabilities` 读取。

### D3: 扩展 provider 验证器支持 `openai_compatible`

`AIConfigCreate`/`AIConfigUpdate` 的 `validate_provider` 目前只允许 `anthropic`/`openai`，但 `family_adapter_cache.py` 已支持 `openai_compatible`。本次扩展验证器，同时在前端 provider 选项中增加 `openai_compatible`。

### D4: 熔断状态写入由 agent 侧触发，通过新 backend endpoint 持久化

agent 捕获 DeerFlow 返回的 429/401/5xx 后，调用 `POST /internal/ai/config/{config_id}/circuit-event` 通知 backend 更新熔断计数。backend 侧判断是否触发熔断（`failure_count >= 5`）。手动重置通过 `POST /api/v1/ai/config/{config_id}/reset-circuit` 实现（owner only）。

### D5: 缓存键从 `family_id` 改为 `(family_id, config_id)`

`family_adapter_cache.py` 当前以 `family_id` 为键，多供应商场景下同一家庭可能使用不同供应商，缓存键必须包含 `config_id`（即 `AIProviderConfig.id`）以避免跨供应商缓存污染。

### D6: 拖拽库选用 `vuedraggable@next`（基于 SortableJS）

项目无现有拖拽库。`vuedraggable@next`（Vue 3 版本）是 Vue 生态最成熟的选择，体积小（~10KB gzip），移动端触摸支持好，与 Vant 4 无冲突。

### D7: 内部端点返回有序供应商列表，agent 侧适配消费方式

`GET /internal/ai/config` 从返回单条 dict 改为返回 `{"providers": [...], "ai_enabled": bool}`，列表按 `display_order` 升序，已熔断（`circuit_open=True` 且 `circuit_open_until` 未过期）的供应商过滤掉。agent orchestrator 从读取单条 `ai_config` 改为读取 `ai_configs` 列表，传入新增的 `_select_model()` 函数。

---

## 实施单元

### IU-1: Alembic Migration — AIProviderConfig 表扩展

**文件:**
- `server/apps/backend/alembic/versions/{id}_add_multi_provider_fields.py` (新建)
- `server/apps/backend/app/models/ai_provider_config.py` (修改)

**变更内容:**

`AIProviderConfig` 新增列：

| 列名 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `provider_name` | String(100) | `provider` 值首字母大写 | 用户自定义供应商名称 |
| `display_order` | Integer | 按 `created_at` 排序的序号 | 拖拽排序权重 |
| `model_2_id` | String(100) nullable | NULL | 第2个模型槽位 |
| `model_3_id` | String(100) nullable | NULL | 第3个模型槽位 |
| `model_1_capabilities` | Text nullable | 从 `thinking_supported` 推断 | JSON 数组，如 `["text_generation","deep_thinking"]` |
| `model_2_capabilities` | Text nullable | `["vision_understanding"]` 若有 `vision_model_id` | JSON 数组 |
| `model_3_capabilities` | Text nullable | NULL | JSON 数组 |
| `circuit_open` | Boolean | False | 熔断是否开启 |
| `circuit_open_until` | DateTime nullable | NULL | 熔断恢复时间 |
| `failure_count` | Integer | 0 | 连续失败计数 |
| `last_failure_at` | DateTime nullable | NULL | 最近失败时间 |

**迁移数据逻辑（在 `upgrade()` 中用 `op.execute` 执行）：**
- `provider_name` = `INITCAP(provider)`（SQLite 用 `UPPER(SUBSTR(provider,1,1)) || SUBSTR(provider,2)`）
- `display_order` = 按 `family_id`, `created_at` 分组的行号
- `model_1_capabilities` = `'["text_generation","deep_thinking"]'` 若 `thinking_supported=1`，否则 `'["text_generation"]'`
- `model_2_capabilities` = `'["vision_understanding"]'` 若 `vision_model_id IS NOT NULL`，否则 NULL

**命名约定:** 参考现有迁移文件，ID 格式为 8 位字母数字（如 `p6935q19rjk5`）。

**测试场景:**
- 迁移后现有记录 `model_1_capabilities` 非空
- `thinking_supported=True` 的记录迁移后 `model_1_capabilities` 包含 `deep_thinking`
- `vision_model_id` 非空的记录迁移后 `model_2_capabilities` 包含 `vision_understanding`
- `display_order` 在同一 `family_id` 内唯一且从 0 开始
- `downgrade()` 能无损回滚（新增列直接 drop）

---

### IU-2: Backend Schema 扩展

**文件:**
- `server/apps/backend/app/schemas/ai_config.py` (修改)

**变更内容:**

`AIConfigResponse` 新增字段：
```
provider_name: str
display_order: int
model_2_id: str | None
model_3_id: str | None
model_1_capabilities: list[str]
model_2_capabilities: list[str]
model_3_capabilities: list[str]
circuit_open: bool
circuit_open_until: datetime | None
failure_count: int
```

`AIConfigCreate` / `AIConfigUpdate` 新增字段：
```
provider_name: str | None
display_order: int | None
model_2_id: str | None
model_3_id: str | None
model_1_capabilities: list[str] | None
model_2_capabilities: list[str] | None
model_3_capabilities: list[str] | None
```

`validate_provider` 扩展为允许 `anthropic` / `openai` / `openai_compatible`。

新增 `AICircuitResetResponse(BaseModel)`: `{ "ok": bool }`

**测试场景:**
- `provider="openai_compatible"` 通过验证
- `provider="unknown"` 仍然被拒绝
- `AIConfigResponse` 序列化包含所有新字段
- `model_1_capabilities` 为空列表时序列化为 `[]` 而非 `null`

---

### IU-3: Backend CRUD API 扩展

**文件:**
- `server/apps/backend/app/routers/ai_config.py` (修改)

**变更内容:**

1. `_cfg_to_response()` 辅助函数：从 `cfg` 读取新字段，`model_X_capabilities` 从 JSON 字符串反序列化为 `list[str]`（空/NULL 返回 `[]`）。

2. `create_ai_config` / `update_ai_config`：写入新字段，`model_X_capabilities` 序列化为 JSON 字符串存储。

3. 新增端点 `POST /config/{config_id}/reset-circuit`（owner only）：
   - 清除 `circuit_open=False`、`failure_count=0`、`circuit_open_until=None`
   - 返回 `AICircuitResetResponse`

4. 新增端点 `PUT /config/reorder`（owner only）：
   - 接收 `{ "order": [config_id_1, config_id_2, ...] }` 
   - 按列表顺序更新各记录的 `display_order`
   - 返回 `{ "ok": true }`

**测试场景:**
- `POST /config` 创建时 `display_order` 自动设为当前家庭最大值+1
- `PUT /config/{id}` 更新 `model_2_id` 不影响其他字段
- `POST /config/{id}/reset-circuit` 清除熔断状态
- `PUT /config/reorder` 正确更新所有记录的 `display_order`
- 非 owner 调用 `reset-circuit` 返回 403

---

### IU-4: Backend 内部端点改造

**文件:**
- `server/apps/backend/app/routers/ai_internal.py` (修改)

**变更内容:**

1. `GET /internal/ai/config` 返回结构从单条 dict 改为：
```python
{
    "ai_enabled": bool,          # 是否有任何可用供应商
    "providers": [               # 按 display_order 升序，已过滤熔断中的供应商
        {
            "config_id": str,    # AIProviderConfig.id（字符串，Snowflake）
            "ai_provider": str,
            "api_key": str,      # 明文，内部网络
            "ai_base_url": str | None,
            "ai_model_id": str | None,        # model_id（槽位1）
            "ai_vision_model_id": str | None, # vision_model_id（槽位1视觉）
            "model_2_id": str | None,
            "model_3_id": str | None,
            "model_1_capabilities": list[str],
            "model_2_capabilities": list[str],
            "model_3_capabilities": list[str],
            "timeout_seconds": int,
        }
    ]
}
```

熔断过滤逻辑：`circuit_open=True AND circuit_open_until > now()` 的记录排除。若 `circuit_open=True` 但 `circuit_open_until <= now()`，视为 half-open，**包含**在列表中并清除熔断状态（顺带写入 DB）。

2. 新增 `POST /internal/ai/config/{config_id}/circuit-event`（agent token 认证）：
```python
# 请求体
{ "error_code": int }   # 429 / 401 / 500 / 502 / 503

# 逻辑
failure_count += 1
last_failure_at = now()
if failure_count >= 5:
    circuit_open = True
    circuit_open_until = now() + 1 hour
```
返回 `{ "circuit_open": bool, "failure_count": int }`

**测试场景:**
- 无可用供应商时返回 `{"ai_enabled": false, "providers": []}`
- 熔断中的供应商不出现在列表中
- half-open 供应商（`circuit_open_until` 已过期）出现在列表中，且 DB 中熔断状态被清除
- `circuit-event` 第5次调用后 `circuit_open=True`
- `circuit-event` 成功调用后 `failure_count` 重置为 0（需在 orchestrator 侧成功时调用重置）

---

### IU-5: Agent — 模型选择策略层

**文件:**
- `server/apps/agent/services/orchestrator.py` (修改)
- `server/apps/agent/core/backend_client.py` (修改，新增 `report_circuit_event` 和 `reset_circuit_success` 方法)

**变更内容:**

`orchestrator.py` 新增 `_select_model(providers: list[dict], task_type: str) -> tuple[dict, str]`：

- `task_type` 由 capability 和请求参数推断：
  - `enable_thinking=True` → `"thinking"`
  - capability 为 `import_parse` 或请求含图片附件 → `"vision"`
  - 其他 → `"text"`
- 遍历 `providers`（已按优先级排序、已过滤熔断），对每个 provider 检查 3 个槽位，返回第一个匹配 `required_capability` 的 `(provider_dict, model_id)`
- Fallback：若无匹配，返回第一个 provider 的 `ai_model_id`（槽位1）
- 返回值包含完整 provider dict（含 `config_id`），供后续熔断上报使用

`stream_dispatch` 和 `stream_dispatch_events` 改造：
- `ai_config` 改为 `ai_configs = await client.get_family_ai_configs()`（返回 providers 列表）
- 调用 `_select_model()` 得到 `(selected_provider, model_id)`
- `_create_family_adapter` 传入 `selected_provider`（单条 dict）
- 成功完成后调用 `client.reset_circuit_success(config_id)` 重置失败计数
- DeerFlow 抛出 429/401/5xx 相关错误时调用 `client.report_circuit_event(config_id, error_code)`
- `model_name` 记录实际使用的 `model_id`（而非配置的默认值）

`_generate_title()` 适配：从 `selected_provider` dict 读取字段，而非从顶层 `ai_config`。

**测试场景:**
- `_select_model` 在 `task_type="thinking"` 时跳过无 `deep_thinking` 能力的 provider
- `_select_model` 在所有 provider 都无匹配能力时返回 fallback（第一个 provider 槽位1）
- `_select_model` 跳过空 providers 列表时抛出明确错误
- DeerFlow 429 错误触发 `report_circuit_event` 调用
- 成功响应触发 `reset_circuit_success` 调用（failure_count 归零）
- `model_name` 在 session journal 中记录实际使用的模型 ID

---

### IU-6: Agent — 适配器缓存键扩展

**文件:**
- `server/apps/agent/services/deerflow_adapter/family_adapter_cache.py` (修改)

**变更内容:**

缓存键从 `family_id: str` 改为 `(family_id, config_id): tuple[str, str]`。

`get_family_adapter(family_id, ai_config, ...)` 签名不变，但内部用 `(family_id, ai_config["config_id"])` 作为 `_adapter_cache` 的键。

`_generate_temp_config` 读取字段适配：
- `api_key` → `ai_config["api_key"]`（不变）
- `ai_model_id` → `ai_config["ai_model_id"]`（不变，槽位1）
- `ai_provider` → `ai_config["ai_provider"]`（不变）
- `ai_base_url` → `ai_config["ai_base_url"]`（不变）
- `thinking_supported` → `"deep_thinking" in ai_config.get("model_1_capabilities", [])`

`invalidate_family_adapter_cache` 扩展为支持按 `family_id` 批量清除（清除所有 `(family_id, *)` 键）。

**测试场景:**
- 同一家庭两个不同 `config_id` 各自有独立缓存条目
- `config_id` 变更后旧缓存不被复用
- `thinking_supported` 从 `model_1_capabilities` 正确推断
- 批量 invalidate 清除该家庭所有缓存条目

---

### IU-7: 前端 — 依赖与 API 层

**文件:**
- `frontend/apps/main/package.json` (修改，添加 `vuedraggable`)
- `frontend/apps/main/src/api/ai.ts` (修改)
- `frontend/apps/main/src/stores/ai.ts` (修改)
- `frontend/apps/main/src/types/` (新增或修改 AI config 类型定义)

**变更内容:**

新增依赖：`vuedraggable@next`（Vue 3 兼容版本，基于 SortableJS）。

`api/ai.ts` 类型和函数更新：
- `AIConfig` 接口扩展新字段（`provider_name`、`display_order`、`model_2_id`、`model_3_id`、`model_1/2/3_capabilities`、`circuit_open`、`circuit_open_until`、`failure_count`）
- `getAIConfigs()` 替换 `getAIConfig()`，返回 `AIConfig[]`（按 `display_order` 排序）
- `createAIConfig(payload)` / `updateAIConfig(id, payload)` 支持新字段
- 新增 `reorderAIConfigs(order: string[])` → `PUT /ai/config/reorder`
- 新增 `resetCircuitBreaker(id: string)` → `POST /ai/config/{id}/reset-circuit`
- 移除 `_cachedConfigId` 模块变量（单配置假设的遗留物）

`stores/ai.ts` 更新：
- `config: AIConfig | null` 改为 `configs: AIConfig[]`
- 新增 `activeConfigs` computed（过滤熔断中的供应商）
- 新增 `reorderConfigs(order: string[])` action
- 新增 `resetCircuit(id: string)` action

**测试场景:**
- `getAIConfigs()` 返回按 `display_order` 排序的数组
- `reorderAIConfigs` 调用正确的 PUT endpoint
- store `configs` 在 `fetchConfigs()` 后包含所有供应商
- `activeConfigs` 过滤掉 `circuit_open=true` 的供应商

---

### IU-8: 前端 — AIConfigPage.vue 重构

**文件:**
- `frontend/apps/main/src/pages/AIConfigPage.vue` (重构)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` (修改，新增 key)
- `frontend/apps/main/src/i18n/locales/en-US.ts` (修改，新增 key)

**UI 结构:**

```
AIConfigPage
├── AI 开关（全局，owner only）
├── 供应商列表（vuedraggable，拖拽排序）
│   └── ProviderCard（每个 AIConfig 一张）
│       ├── 展开态：供应商名称、provider 类型、API Key、Base URL
│       │   ├── 模型槽位 1（model_id）+ 能力标识行
│       │   ├── 模型槽位 2（model_2_id）+ 能力标识行（可选）
│       │   ├── 模型槽位 3（model_3_id）+ 能力标识行（可选）
│       │   ├── 超时配置
│       │   ├── 熔断状态（若 circuit_open=true 显示警告 + 重置按钮）
│       │   └── 测试连接按钮
│       └── 折叠/拖拽态：仅显示供应商名称 + provider 类型图标
├── 添加供应商按钮
└── 保存顺序按钮（拖拽后出现）
```

**能力标识组件（内联）：**
- 支持：彩色 emoji（📝🧠🖼️）+ 彩色文字
- 不支持：灰色 emoji + `opacity: 0.3` + 删除线或禁用样式
- 点击能力标识切换勾选状态（owner only）

**拖拽行为：**
- 拖拽时卡片折叠为缩略态（仅显示供应商名称 + 图标）
- 拖拽结束后显示"保存顺序"按钮，点击调用 `reorderAIConfigs`
- 移动端触摸拖拽需测试（vuedraggable 默认支持）

**新增 i18n key（zh-CN.ts `aiConfig` 命名空间下）：**
```
providerOpenAICompatible: 'OpenAI 兼容'
providerName: '供应商名称'
addProvider: '添加供应商'
saveOrder: '保存排序'
modelSlot: '模型 {n}'
capabilityText: '文本生成'
capabilityThinking: '深度思考'
capabilityVision: '视觉理解'
circuitOpen: '⚠️ 供应商已熔断'
circuitOpenUntil: '预计 {time} 后自动恢复'
resetCircuit: '手动重置熔断'
circuitResetSuccess: '✅ 熔断状态已重置'
```

**测试场景:**
- 多个供应商卡片正确渲染，按 `display_order` 排序
- 能力标识彩色/灰白状态与 `capabilities` 数组一致
- 拖拽后"保存顺序"按钮出现，点击后消失
- 熔断中的供应商显示警告横幅和重置按钮
- 重置按钮调用 `resetCircuit` action 并显示成功 toast
- 非 owner 用户看到只读视图（无编辑/拖拽/重置）
- 添加第4个供应商时无上限限制（每个供应商最多3个模型槽位，供应商数量不限）

---

## 依赖与顺序

```
IU-1 (migration)
  └─→ IU-2 (schema)
        └─→ IU-3 (CRUD API)
              └─→ IU-4 (internal endpoint)
                    ├─→ IU-5 (orchestrator)
                    │     └─→ IU-6 (adapter cache)
                    └─→ IU-7 (frontend API/store)
                          └─→ IU-8 (frontend UI)
```

IU-5 和 IU-7 可并行（都依赖 IU-4 完成）。

---

## 风险与注意事项

### R1: `thinking_supported` 列废弃但不删除

`thinking_supported` 列继续存在（不 drop），但新代码不再写入它。内部端点改为从 `model_1_capabilities` 读取。这避免了需要同时更新所有读取该列的代码。

### R2: 内部端点返回结构变化是破坏性变更

`GET /internal/ai/config` 从返回单条 dict 改为返回 `{"ai_enabled": bool, "providers": [...]}` 是破坏性变更。IU-4 和 IU-5 必须同步部署，不能分开上线。

### R3: 熔断写入频率

每次 DeerFlow 调用失败都写一次 DB。家庭级低频使用（< 1000 次/天）完全可控，但需确保 `circuit-event` endpoint 是异步 fire-and-forget（不阻塞主响应路径）。

### R4: 拖拽库新增依赖

`vuedraggable@next` 需要 `pnpm add vuedraggable@next` 并在 `package.json` 中锁定版本。需验证与 Vant 4 / Vue 3.5 的兼容性。

### R5: SQLite 兼容性（测试环境）

测试使用 in-memory SQLite。`model_X_capabilities` 存为 Text（JSON 字符串），SQLite 兼容。`circuit_open_until` 为 DateTime，SQLite 兼容。无需特殊处理。

---

## 验证标准（对应需求文档 Success Criteria）

| 需求 | 验证方式 |
|------|---------|
| 可配置 ≥2 个供应商，每个最多3个模型 | 后端 CRUD 测试 + 前端 E2E |
| 能力标识彩色/灰白正确显示 | 前端组件测试 |
| 移动端拖拽排序可操作 | 浏览器手动测试（375px viewport） |
| 普通文本 → 选 text_generation 模型 | `_select_model` 单元测试 |
| 深度思考 → 选 deep_thinking 模型 | `_select_model` 单元测试 |
| 视觉任务 → 选 vision_understanding 模型 | `_select_model` 单元测试 |
| 连续5次429/401后熔断，切换下一供应商 | `circuit-event` endpoint 集成测试 |
| 1小时后自动尝试恢复 | half-open 逻辑单元测试 |
| 手动重置熔断 | `reset-circuit` endpoint 测试 + 前端测试 |
| 迁移无数据丢失 | migration upgrade/downgrade 测试 |
