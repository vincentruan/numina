---
name: multi-provider-model-selection
description: 多供应商智能模型选择系统 — 支持配置多个 AI 供应商（每个供应商最多 3 个模型），agent 根据任务特征自动选择最优模型，供应商级熔断降级
type: project
---

# Multi-Provider Model Selection System

**Created:** 2026-05-16
**Status:** Requirements captured, awaiting planning

## Problem Statement

当前家庭管理员只能配置**单个 AI 供应商**（一条激活的 `AIProviderConfig` 记录），包含一个主模型和一个视觉模型。高频使用家庭有多个供应商（Anthropic、OpenAI、DeepSeek、GLM 等）和多种模型（文本生成、深度思考、视觉理解），希望根据任务特征自动选择最佳模型组合。

现有系统的局限：

1. **单供应商约束**：`AIProviderConfig.is_active=True` 只能有一条，无法配置备用供应商
2. **模型能力标识分散**：主模型和视觉模型分开存储，无法标识"某个模型同时支持文本+思考+视觉"
3. **无熔断降级**：某供应商持续 429/401 时系统直接失败，无法切换到备用供应商
4. **无优先级调整**：用户无法拖拽调整供应商顺序，无法表达"优先用 DeepSeek，失败时切换 OpenAI"

## Proposed Solution

**多供应商智能模型选择系统**：让家庭管理员配置多个供应商（每个供应商最多 3 个模型），手动标注每个模型的能力（文本生成/深度思考/视觉理解），agent 根据任务特征自动选择最优供应商+模型组合，遇到供应商连续失败时自动熔断并切换到下一供应商，恢复后优先使用高优先级供应商。

### Core Components

1. **数据层**：扩展 `AIProviderConfig` 表（加 `provider_name`、`display_order`、`model_2_id`、`model_3_id`、`model_1/2/3_capabilities`、熔断状态字段）
2. **Agent 层**：新增模型选择策略层（`orchestrator._select_model()`），根据任务特征选最优 `(provider, model_id)`
3. **熔断机制**：供应商级熔断（连续 N 次 429/401/5xx 后切换下一供应商），定时自动恢复 + 手动重置
4. **前端 UI**：供应商卡片列表（拖拽排序），每张卡片展开编辑模型配置和能力标识

## Key Decisions

### Model Configuration (Confirmed)

**决策**：每个供应商最多 3 个模型槽位，用户自由填写 `model_id`，手动勾选能力标志。

**能力标志**（JSON 数组存储）：
- `text_generation`（📝文本生成）
- `deep_thinking`（🧠深度思考）
- `vision_understanding`（🖼️视觉理解）

**理由**：
- 产品约束明确（最多 3 个），不需要无限扩展
- 用户可以根据模型实际能力灵活标注（Claude 3.5 Sonnet 支持 text+thinking+vision，GLM-4V 支持 text+vision）
- Agent 选择逻辑简单：按任务特征匹配能力标志

### Circuit Breaker Granularity (Confirmed)

**决策**：供应商级熔断，不是模型级。

**行为**：
- 某供应商连续 N 次 429/401/5xx 后，整个供应商暂停（所有模型槽位都不可用）
- 切换到下一优先级供应商（按 `display_order` 排序）
- 不做单个 `model_id` 的独立熔断计数

**理由**：
- API Key 是供应商级别的，一个 Key 失效意味着整个供应商失效
- 同供应商内不同模型通常共享配额（Anthropic、OpenAI 都是这样）
- 模型级熔断增加复杂度，但对用户价值有限

### Circuit Breaker Trigger (Confirmed)

**决策**：自动感知，不需要用户配置限额。

**触发条件**：
- 连续 N 次（建议 N=5）以下错误：
  - 429 Too Many Requests
  - 401 Unauthorized
  - 5xx Server Error（500、502、503）

**熔断状态字段**：
- `circuit_open` (bool)：熔断是否开启
- `circuit_open_until` (datetime)：熔断恢复时间（默认 1 小时后）
- `failure_count` (int)：连续失败计数
- `last_failure_at` (datetime)：最近一次失败时间

**理由**：
- 用户不需要手动估算每日调用量（对家庭用户不友好）
- 系统根据实际 API 响应自动触发，更准确
- 简化前端 UI（不需要限额输入字段）

### Recovery Mechanism (Confirmed)

**决策**：定时自动恢复 + 手动重置。

**自动恢复**：
- 熔断后等待固定时间（默认 1 小时）
- 下一次请求尝试使用该供应商（half-open 状态）
- 成功则清除熔断状态，恢复使用
- 失败则继续熔断，延长等待时间

**手动重置**：
- 用户可在前端配置页点击"重置熔断状态"按钮
- 立即清除 `circuit_open`、`failure_count`，恢复使用

**理由**：
- 自动恢复避免永久失效（供应商临时故障恢复后自动切回）
- 手动重置提供用户控制权（明确知道供应商已恢复时可主动切回）

### Data Layer (Confirmed)

**决策**：在现有 `AIProviderConfig` 表上加字段，不拆子表。

**新增字段**：
```python
provider_name: str          # 供应商名称（用户自定义，如"DeepSeek 官方"、"OpenAI 备用"）
display_order: int          # 排序权重（用于拖拽调整优先级）

# 第 2、3 个模型槽位（第 1 个沿用现有 model_id/vision_model_id）
model_2_id: str | None
model_3_id: str | None

# 每个模型的能力标志（JSON 数组）
model_1_capabilities: list[str]  # ["text_generation", "deep_thinking"]
model_2_capabilities: list[str]  # ["text_generation", "vision_understanding"]
model_3_capabilities: list[str]  # ["vision_understanding"]

# 熔断状态
circuit_open: bool = False
circuit_open_until: datetime | None
failure_count: int = 0
last_failure_at: datetime | None
```

**迁移策略**：
- 一次 Alembic migration
- 现有数据兼容：
  - `provider_name` 默认为 `provider` 值（如"anthropic" → "Anthropic"）
  - `display_order` 默认按 `created_at` 排序（老记录靠前）
  - `model_1_capabilities` 根据 `thinking_supported` 推断：`True` → `["text_generation", "deep_thinking"]`，`False` → `["text_generation"]`
  - `model_2_capabilities` 默认 `["vision_understanding"]`（如果有 `vision_model_id`）
  - `model_3` 默认为空

**理由**：
- 结构简单，无外键，无数据丢失风险
- Agent 侧读取一条记录就能拿到所有信息（不需要嵌套查询）
- 前端 API 不需要嵌套结构（`AIConfigResponse` 直接平铺字段）

## Scope Boundaries

### In Scope

- 数据层：`AIProviderConfig` 表扩展（加字段）
- 后端：`/api/v1/ai/config` CRUD API 扩展（支持多供应商排序、能力标志）
- 后端：`/internal/ai/config` 返回有序供应商列表（含熔断状态过滤）
- Agent：`orchestrator._select_model()` 模型选择策略层
- Agent：`family_adapter_cache` 扩展为支持多供应商轮询
- Agent：熔断状态写入和恢复逻辑（每次 API 调用失败写 DB）
- 前端：`AIConfigPage.vue` 重构为供应商卡片列表
- 前端：拖拽排序（Vant 拖拽或 `@vueuse/core` useSortable）
- 前端：能力标识 UI（彩色 emoji 表示支持，黑白禁用标识表示不支持）
- 前端：熔断状态显示和手动重置按钮

### Deferred for Later

- 模型级熔断（不做单个 `model_id` 的独立熔断计数）
- 超过 3 个模型的扩展（产品约束明确，未来需要再加列）
- 熔断计数持久化到 Redis（当前 DB 写入足够，未来高并发场景再迁移）
- 模型成本/延迟监控（不在本次需求范围）

### Outside This Product's Identity

- 用户手动配置每日限额（由系统自动感知 429/401 触发）
- MCP 工具或 skill 配置的变更（现有机制足够）
- 模型自动发现（用户手动填写 model_id，不扫描供应商模型列表）

## Dependencies and Assumptions

### Dependencies

- **现有机制可复用**：
  - `AIProviderTestResult` 表继续存储测试结果（按 `config_id` + `test_type`）
  - `family_adapter_cache.py` 的 LRU 缓存机制扩展为多供应商轮询
  - `orchestrator.py` 的 `ai_config` dict 只需扩展字段
  - `DeerFlowAdapter` 执行层不变（只传 `(provider, model_id)` 参数）

- **前端依赖**：
  - Vant 4 的拖拽组件或 `@vueuse/core` 的 `useSortable`
  - 现有 `api/ai.ts` 和 `stores/ai.ts` 扩展字段

### Assumptions

- **家庭级使用频率**：每日调用次数 < 1000，熔断状态写入 DB 不会造成性能问题
- **API Key 失效范围**：一个 API Key 失效意味着整个供应商失效（Anthropic、OpenAI、DeepSeek 都是这样）
- **模型能力稳定性**：模型能力标志由用户标注，不会动态变化（Claude 3.5 Sonnet 永远支持 text+thinking+vision）
- **熔断恢复时间**：默认 1 小时足够供应商临时故障恢复（如果是永久失效，用户可手动禁用或删除该供应商）

## Success Criteria

### Functional Success

1. **多供应商配置**：家庭管理员可配置 ≥ 2 个供应商，每个供应商可配置 1-3 个模型
2. **能力标识**：用户可为每个模型勾选 0-3 个能力标志（文本/思考/视觉）
3. **拖拽排序**：移动端拖拽调整供应商优先级，缩略卡片可操作
4. **自动模型选择**：
   - 普通文本问答 → 选择优先支持 `text_generation` 的供应商+模型
   - 深度思考任务 → 选择支持 `deep_thinking` 的供应商+模型
   - 视觉理解任务（图片/PDF）→ 选择支持 `vision_understanding` 的供应商+模型
5. **熔断降级**：某供应商连续 5 次 429/401 后自动切换下一供应商
6. **自动恢复**：熔断供应商 1 小时后自动尝试恢复，成功则重新使用
7. **手动重置**：用户可在前端点击"重置熔断状态"按钮

### Quality Success

1. **迁移无数据丢失**：现有单供应商配置平滑迁移到多供应商结构
2. **前端可用性**：移动端拖拽排序操作流畅（缩略卡片 < 50px 高度）
3. **Agent 性能**：模型选择函数耗时 < 5ms（纯内存逻辑，不阻塞 DeerFlow 调用）
4. **熔断写入频率**：家庭级使用场景，每日写入 < 100 行（完全可控）

## Implementation Notes

### Agent Model Selection Strategy

`orchestrator._select_model()` 伪代码：

```python
def _select_model(ai_configs: list[dict], task_type: str) -> tuple[str, str]:
    """
    Args:
        ai_configs: 有序供应商列表（按 display_order，已过滤熔断状态）
        task_type: "text" | "thinking" | "vision"

    Returns:
        (provider, model_id)
    """
    required_capability = {
        "text": "text_generation",
        "thinking": "deep_thinking",
        "vision": "vision_understanding",
    }[task_type]

    for config in ai_configs:
        # 检查模型槽位 1-3，找到第一个支持所需能力的模型
        for slot in [1, 2, 3]:
            model_id = config.get(f"model_{slot}_id")
            capabilities = config.get(f"model_{slot}_capabilities", [])
            if model_id and required_capability in capabilities:
                return config["provider"], model_id

    # Fallback: 使用第一个供应商的第一个模型（即使能力不匹配）
    return ai_configs[0]["provider"], ai_configs[0]["model_1_id"]
```

### Frontend UI Structure

供应商卡片列表（展开状态）：

```
┌─────────────────────────────────────────────┐
│ 💬 Anthropic 官方          [拖拽手柄] [删除] │
├─────────────────────────────────────────────┤
│ API Key: sk-ant-...****  [👁️ 显示]           │
│ Base URL: https://api.anthropic.com          │
│                                             │
│ 模型 1: claude-3-5-sonnet-20241022           │
│         📝文本 🧠思考 🖼️视觉                 │
│                                             │
│ 模型 2: claude-3-5-haiku-20241022            │
│         📝文本                               │
│                                             │
│ 模型 3: （空槽位，点击添加）                  │
│                                             │
│ 状态: ✅ 正常  [测试连接]                     │
└─────────────────────────────────────────────┘
```

拖拽时缩略卡片：

```
┌──────────────────┐
│ 💬 Anthropic 官方 │
└──────────────────┘
```

能力标识样式：
- 支持：彩色 emoji（📝🧠🖼️）
- 不支持：黑白 emoji + 禁用标识（📝️🧠️🖼️️）

## Open Questions

(All resolved during brainstorming — no open questions remain)

## Next Steps

1. `/ce-plan` 生成详细实现计划
2. 后端：Alembic migration 加字段
3. 后端：扩展 `/api/v1/ai/config` CRUD API
4. Agent：实现 `_select_model()` 模型选择策略
5. Agent：实现熔断状态写入和恢复逻辑
6. 前端：重构 `AIConfigPage.vue` 为供应商卡片列表
7. 前端：实现拖拽排序和能力标识 UI
8. 测试：迁移兼容性、模型选择逻辑、熔断降级流程