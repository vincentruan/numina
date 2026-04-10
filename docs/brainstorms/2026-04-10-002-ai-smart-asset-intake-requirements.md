---
date: 2026-04-10
topic: ai-smart-asset-intake
---

# 智能资产录入助手

## Problem Frame

`AssetCreate` 有 17 个字段，其中 `expected_lifespan_days`、`annual_maintenance_cost`、`usage_frequency` 是影响下游功能（固定资产老化预警、低效资产处置建议、日均成本计算）的关键字段，但用户普遍跳过这些可选字段——因为他们不知道"一台 MacBook 的预期寿命是多少天"。

字段填写率低导致一个恶性循环：数据稀疏 → 下游 AI 功能覆盖面窄 → 功能价值低 → 用户不感知价值 → 继续跳过字段。

智能补全通过在用户输入资产名称后自动建议这些字段的合理默认值，以最小摩擦提升数据质量，启动数据质量飞轮。

**首版范围：字段智能补全**（对话式录入作为 Phase 2）。

```
用户在资产表单输入名称
         │
         ▼
    名称字段失焦
         │
         ▼
  名称长度 ≥ 2 字符？ ──否──▶ 跳过，不触发
         │
         是
         ▼
  调用 POST /api/v1/ai/asset-suggest
         │
         ▼
  字段显示加载状态（skeleton）
         │
         ▼
  AI 返回建议值
         │
         ▼
  填入空白字段（已有值的字段不覆盖）
  字段显示浅蓝色背景标识"AI 填入"
         │
         ▼
  用户可直接修改 / 清空任意字段
         │
         ▼
  用户提交表单（AI 建议值与手填值无差异）
```

---

## Requirements

**AI 基础设施前提（依赖 Phase 0，与体检报告共享）**

- R0. 依赖 `docs/brainstorms/2026-04-10-001-ai-health-report-requirements.md` 中 R0-R6 的基础设施（`agent/` 模块、脱敏管道、管理员开关、限速）。
- R1. 当家庭 `ai_enabled == False` 时，`POST /api/v1/ai/asset-suggest` 返回 `403 {"code": "ai_disabled"}`；前端静默降级——表单正常显示，仅不触发 AI 补全，不展示任何错误提示。

**后端：建议接口**

- R2. `POST /api/v1/ai/asset-suggest` 接收 `{"name": str, "asset_type": str | None, "category_id": str | None}`，返回建议字段值。
- R3. 接口返回结构：
  ```json
  {
    "category_id": "str | null",
    "usage_frequency": "daily|weekly|monthly|rarely|idle|null",
    "expected_lifespan_days": "int | null",
    "annual_maintenance_cost": "float | null",
    "tag_names": ["str"],  // 建议的标签名称列表（字符串，非 ID）；无建议时为空数组 []
    "confidence": "high|medium|low"
  }
  ```
- R4. 脱敏要求：发送给 LLM 的 prompt 只包含资产名称、资产类型和系统类别列表（21个类别的中文名），不包含任何家庭数据、金额或成员信息。
- R5. 接口响应时间目标 < 3 秒（P90）；超时时返回空建议（所有字段为 null），前端静默降级。
- R6. per-family 限速：每分钟最多 20 次建议请求（用户快速添加多项资产的场景）。
- R7. LLM prompt 包含资产类别的枚举约束和 `usage_frequency` 的合法值列表，确保返回值在合法范围内；后端对返回值做二次校验，非法值替换为 null；`confidence` 非法值替换为 `"low"`（保守降级）。

**前端：表单集成**

- R8. `AssetForm.vue` 在名称字段（`name`）失焦时触发补全，条件：名称长度 ≥ 2 字符 且 `ai_enabled == true`。
- R9. 触发后，以下字段若当前为空（null/''）则显示 skeleton 加载状态：`category_id`、`usage_frequency`、`expectedLifeYears`（年数 ref）、`annual_maintenance_cost`、`tag_ids`。
- R9a. `usage_frequency` 字段初始值改为 `null`（去掉 `'daily'` 默认值），要求用户显式选择或由 AI 填入；表单校验不强制要求该字段。
- R10. AI 建议返回后，**仅填入当前为空（null/''）的字段**；用户已手动填写的字段不被覆盖。`expected_lifespan_days`（天）由前端除以 365 转换后填入 `expectedLifeYears` ref，保持与表单内部状态一致。
- R11. 被 AI 填入的字段显示浅蓝色背景（CSS variable `--ai-fill-bg`，深色模式自动适配），字段右侧显示 AI 图标（✨ 或 sprite icon）。用户修改该字段后，AI 样式标识立即消失。
- R12. 当 `confidence == "low"` 时，AI 填入的字段额外显示"建议仅供参考"tooltip，提示用户核实。
- R13. 名称字段旁显示小型状态指示：加载中显示 spinner，完成显示"AI 已补全 N 个字段"（N > 0 时），失败或超时静默不显示任何提示。
- R14. 用户可对任意 AI 填入字段直接修改，修改后该字段视为用户手填值，不再被后续 AI 补全覆盖（即使用户再次修改名称触发新一轮补全）。
- R14a. `tag_names` 返回后，在标签字段下方以 Chip 形式展示"AI 建议标签：电子产品 · 办公"，用户点击某个 Chip 后将该名称精确匹配现有标签填入 `tag_ids`；找不到匹配标签则跳过（不自动创建）。建议 Chip 在用户手动操作标签字段后消失。
- R15. 编辑已有资产时（`isEdit == true`）不触发 AI 补全，避免覆盖用户已有数据。

**对话式录入（Phase 2，本版不实现）**

- R16. 本版不实现对话式录入（自然语言 → 表单预填）。预留 `AssetFormPage.vue` 顶部的"自然语言描述"入口位置，Phase 2 时填充。

---

## Success Criteria

- 新增资产时，`expected_lifespan_days` 字段的填写率（非空）相比基线提升 ≥ 40%（通过后台统计验证）。
- AI 补全触发到结果展示 < 3 秒（P90）。
- AI 建议的 `category_id` 准确率 ≥ 85%（人工抽样 20 个常见资产名称验证）。
- `ai_enabled == False` 时表单行为与未接入 AI 前完全一致，无任何 UI 差异。
- 用户已填写的字段在 AI 补全后保持不变（零覆盖）。

---

## Scope Boundaries

- 不包含对话式录入（Phase 2）。
- 不包含基于家庭历史数据的个性化建议（如"你家同类资产平均寿命是X天"）——首版只用 LLM 通用知识。
- 不包含补全结果的用户反馈机制（"这个建议准确吗？"）——首版不收集反馈。
- 不包含批量资产导入时的 AI 补全。
- `confidence` 字段仅用于前端展示 tooltip，不影响是否填入字段的逻辑。

---

## Key Decisions

- **失焦触发** — 不打断用户输入节奏，体验自然；防抖触发在用户输入慢时会产生多余请求。
- **直接填入 + 可撤销** — 摩擦最小；弹出确认卡片增加一步操作，用户会习惯性点"取消"。
- **仅填入空白字段** — 核心安全原则：AI 永远不覆盖用户已有输入，消除用户对"AI 乱改我的数据"的顾虑。
- **`ai_enabled == False` 时静默降级** — 表单对未开启 AI 的家庭行为完全一致，无降级感知，无需条件渲染大量 UI 分支。
- **脱敏：只发资产名称 + 类别列表** — 建议接口不需要任何家庭数据，脱敏成本为零，隐私风险最低。

---

## Dependencies / Assumptions

- 依赖 Phase 0 基础设施（`agent/` 模块、`ai_enabled` 开关、限速中间件）与体检报告共享建设。
- 假设 LLM 对常见消费品（手机、电脑、家电、车辆）的预期寿命有足够的通用知识，无需额外训练数据。
- `AssetForm.vue` 当前通过 `@submit` 事件向父组件传递数据，AI 补全直接操作表单内部响应式状态，不影响提交流程。
- 系统类别列表（21个）在前端已通过 `categoryStore` 加载，可直接传入建议请求，无需额外接口。

---

## Outstanding Questions

### Resolve Before Planning

无阻塞问题。

### Deferred to Planning

- **[影响 R11][技术]** `--ai-fill-bg` CSS variable 需要在全局主题文件中定义，确认深色模式下的色值（建议：浅蓝 `rgba(0, 120, 255, 0.08)`，深色模式 `rgba(0, 120, 255, 0.15)`）。
- **[影响 R7][需要研究]** LLM prompt 工程：如何构造 prompt 使返回值严格符合枚举约束？考虑使用 Anthropic structured output 或 pydantic-ai 的 `result_type` 约束。
- **[影响 R13][技术]** "AI 已补全 N 个字段"提示的展示位置：名称字段下方 inline 还是页面顶部 toast？inline 更精准，toast 更显眼。

---

## Next Steps

→ `/ce:brainstorm`（创意 #3：固定资产老化预警与换购建议）
