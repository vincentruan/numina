---
date: 2026-04-10
topic: ai-allocation-drift
---

# 资产分配漂移检测与再平衡提醒

## Problem Frame

家庭资产配置在牛市后静默漂移——一个从目标 60% 金融 / 40% 实物漂移到 80/20 的家庭不会注意到，直到市场下行。现有 Dashboard 的配置饼图只展示当前状态，没有目标对比，没有漂移预警。

本功能让家庭管理员设置目标配置（大类必填，类别级可选），系统每周检测实际配置与目标的偏差，超过阈值时在 Dashboard 推送再平衡建议卡片。

**核心约束：** 没有目标配置就没有漂移检测——功能仅对已设置目标配置的家庭激活。

```
管理员在 AI 配置页设置目标配置
（大类：实物/金融占比；可选：类别级占比）
         │
         ▼
每周定时任务（与创意 #3/#5 共享调度器实例，各自独立 job）
         │
         ▼
  查询所有 ai_enabled == True 且已设置目标配置的家庭
         │
         ▼
  总资产为零？ ──是──▶ 跳过，不生成
         │
         否
         ▼
  调用 get_allocation() 获取当前配置
         │
         ▼
  计算大类漂移 + 类别级漂移（已设置目标的类别）
         │
         ▼
  任一漂移超过阈值？ ──否──▶ 跳过，不生成
         │
         是
         ▼
  调用 LLM 生成再平衡建议文本
         │
         ▼
  写入 ai_allocation_alerts 表（UPSERT by family_id）
         │
         ▼
  用户进入 Dashboard → 配置漂移卡片
```

---

## Requirements

**AI 基础设施前提（依赖 Phase 0）**

- R0. 依赖 `docs/brainstorms/2026-04-10-001-ai-health-report-requirements.md` 中 R0-R6 的基础设施。
- R0a. 定时任务与创意 #3/#5 共享同一个 `AsyncIOScheduler` 实例，但各自注册独立的 scheduler job（本功能为每周一 08:00 Asia/Shanghai，健康报告为每月 1 日，两者触发频率不同，不能合并为同一 job）；各 job 用独立 try/except 包裹，互不影响。

**目标配置存储**

- R1. 新增 `ai_allocation_targets` 表，字段：`id`、`family_id`（FK，唯一索引，每个家庭只有一条记录）、`physical_target_pct`（实物资产目标占比，0-100）、`financial_target_pct`（金融资产目标占比，0-100）、`drift_threshold_pct`（漂移触发阈值，默认 10，范围 5-30，即实际偏离目标 ≥ N 个百分点时触发）、`category_targets`（JSON，类别级目标配置，可为 NULL）、`updated_at`。
- R2. `physical_target_pct + financial_target_pct` 必须等于 100，后端校验，不满足时返回 `422`。
- R3. `category_targets` JSON 结构：`{"category_id": target_pct, ...}`。**规则：若提供 `category_targets`，则其中所有条目的占比之和必须等于 100（即要么不填，要么全量填写所有类别）；部分填写（只填部分类别）不被允许，后端返回 `422`。** 为 NULL 时仅检测大类漂移。此约束解决了"部分类别有目标、其余类别无目标"时分母不一致导致的漂移计算错误（见 R8 说明）。
- R4. `PUT /api/v1/ai/allocation-target` 创建或更新当前家庭的目标配置；仅管理员（`role == 'owner'`）可调用。
- R5. `GET /api/v1/ai/allocation-target` 返回当前家庭的目标配置；无配置时返回 `{"configured": false}`。

**后端：漂移检测**

- R6. 每周定时任务扫描所有 `ai_enabled == True` 且 `ai_allocation_targets` 表中有记录的家庭，执行漂移检测。**总资产为零时跳过该家庭（避免除零），不生成预警。**
- R7. 大类漂移计算：
  - 前提：漂移检测服务直接查询数据库计算实物/金融资产总值，**不复用 `get_allocation()`**（该函数在总资产为零时将分母替换为 1，会产生错误的百分比；且不含 `asset_type` 字段，需额外关联 `Category` 表）。
  - 当前实物资产占比 = 实物资产总值 / 总资产值 × 100（总资产值 > 0 时才执行）
  - 大类漂移量 = |当前实物占比 - `physical_target_pct`|
  - 触发条件：大类漂移量 ≥ `drift_threshold_pct`
- R8. 类别级漂移计算（仅当 `category_targets` 不为 NULL）：
  - 对每个有目标的类别：类别漂移量 = |当前类别占比 - 目标占比|
  - 当前类别占比 = 该类别资产总值 / **全部资产总值** × 100（分母为全部资产，与大类漂移保持一致）
  - 触发条件：任一类别漂移量 ≥ `drift_threshold_pct`
  - **注意：** 由于 R3 要求 `category_targets` 必须覆盖所有类别（全量或不填），此处分母与目标之和的基准一致，计算结果有效。
- R9. 脱敏要求：发送给 LLM 的数据包含大类当前占比 vs 目标占比、触发漂移的类别名和漂移量；不包含精确金额、成员信息、资产名称。
- R10. LLM 生成再平衡建议文本（80-150字），包含：漂移现状描述 + 建议调整方向（增加/减少哪类资产）+ 简短理由；不给出具体金额建议（避免 LLM 幻觉）。
- R11. 新增 `ai_allocation_alerts` 表，字段：`id`、`family_id`（FK，唯一索引）、`drift_type`（`physical` / `category` / `both`）、`drift_summary`（JSON，见下方 schema）、`suggestion_text`（AI 生成建议）、`generated_at`、`is_dismissed`。
  - `drift_summary` JSON schema：
    ```json
    {
      "physical_current_pct": 72.5,
      "physical_target_pct": 40.0,
      "physical_drift": 32.5,
      "category_drifts": [
        {"category_id": "...", "category_name": "房产", "current_pct": 55.0, "target_pct": 30.0, "drift": 25.0}
      ]
    }
    ```
    `category_drifts` 仅包含实际触发漂移的类别（drift ≥ threshold）；大类未触发时 `physical_drift` 仍记录实际值供前端展示。
- R12. UPSERT by `family_id`（每个家庭只保留最新一条预警），覆盖旧记录并重置 `is_dismissed = False`。
- R13. `GET /api/v1/ai/allocation-alert` 返回当前家庭的漂移预警（若存在且未忽略）。
- R14. `POST /api/v1/ai/allocation-alert/dismiss` 标记 `is_dismissed = True`；下次定时任务 UPSERT 后重置。

**前端：目标配置设置**

- R15. `SettingsPage.vue` 的"AI 智能功能"入口下新增"资产配置目标"设置项（仅管理员可见）。
- R16. 配置页展示两个区域：
  - **大类配置（必填）**：实物资产目标占比滑块（0-100%），金融资产占比自动计算为 `100 - 实物占比`，实时展示两者比例；漂移阈值输入框（默认 10%，范围 5-30%，后端同步校验）。
  - **类别级配置（可选，可折叠）**：展示所有资产类别列表，每个类别有目标占比输入框；底部实时显示已填类别的占比总和，**必须填写全部类别且总和等于 100% 才允许保存**（部分填写时禁止保存并提示"请填写所有类别的目标占比"）。
- R17. 保存时调用 `PUT /api/v1/ai/allocation-target`；保存成功后展示"配置已保存，将在下次周报时生效"提示。

**前端：Dashboard 漂移卡片**

- R18. `DashboardPage.vue` 新增"配置漂移"卡片，仅当 `ai_enabled == true` 且有未忽略的漂移预警时展示，位于 overview 卡片之后。
- R19. 漂移卡片展示：
  - 漂移类型标签（"大类漂移" / "类别漂移" / "双重漂移"）
  - 当前 vs 目标配置对比（简洁文字，如"实物资产：当前 72% → 目标 40%，偏差 32%"）
  - AI 再平衡建议文本（最多 3 行，超出展开）
  - "忽略"按钮（右滑展开，与创意 #3 一致）
- R20. 点击漂移卡片跳转至 Dashboard 的配置饼图区域（页面内锚点滚动），让用户直观看到当前配置分布。
- R21. 当 `ai_enabled == false` 或未设置目标配置时，漂移卡片不渲染。

---

## Success Criteria

- 管理员能在 3 步内完成目标配置设置（进入设置 → 调整滑块 → 保存）。
- 大类漂移计算结果可通过手工验算验证（纯数学）。
- 漂移超过阈值时 Dashboard 正确展示预警卡片；未超过阈值时卡片不出现。
- 忽略后卡片消失，下次定时任务后重新出现。
- 未设置目标配置的家庭不触发任何漂移检测，Dashboard 无相关卡片。
- 总资产为零的家庭不触发漂移检测，不生成预警。

---

## Scope Boundaries

- 不包含再平衡操作的执行（只给建议方向，不提供具体买卖操作）。
- 不包含历史漂移趋势图（每家庭只保留最新一条预警，无历史存档）。
- 不包含自动目标配置建议（AI 不主动推荐目标，用户手动设置）。
- 类别级配置为可选——未填写类别目标时，仅检测大类漂移。
- 漂移阈值为家庭级统一设置，不支持大类和类别级分别设置不同阈值（首版简化）。
- 总资产为零时跳过漂移检测（避免除零）。

---

## Key Decisions

- **大类必填 + 类别级可选** — 降低设置门槛（只需设一个滑块）同时支持精细化需求；类别级配置折叠展示，不强迫用户填写。
- **类别级配置要么全填要么不填** — 避免部分填写时分母不一致导致漂移计算错误（当前类别占比基于全部资产，而目标只覆盖部分类别，两者不可比）。
- **每家庭只保留最新一条预警** — 漂移是持续状态，不需要历史存档；UPSERT 保证数据简洁。
- **漂移阈值用户可配置（默认 10%，范围 5-30%）** — 不同家庭对漂移的敏感度不同；固定阈值会导致部分家庭频繁收到无意义提醒。
- **与创意 #3/#5 共享 scheduler 实例，各自独立 job** — 统一运维，减少 scheduler 实例数量；但健康报告（月度）与漂移检测（周度）触发频率不同，不能合并为同一 job。
- **漂移检测不复用 `get_allocation()`** — 该函数在总资产为零时将分母替换为 1（`or 1` 哨兵值），会产生错误百分比；且不含 `asset_type` 字段。漂移检测服务直接查询数据库，先检查总资产 > 0 再计算。
- **Dashboard 卡片点击锚点滚动到饼图** — 无需新增页面，利用现有配置饼图作为可视化载体。
- **LLM 不给具体金额建议** — 避免幻觉；再平衡方向（增加/减少哪类）是确定性的，具体金额由用户自行决策。

---

## Dependencies / Assumptions

- 依赖 Phase 0 基础设施（`agent/` 模块、`ai_enabled` 开关、APScheduler）。
- 现有 `get_allocation()` 返回 `AllocationResponse`（含 `items: list[AllocationItem]`，每项有 `category_id`、`percentage`、`total`），**不直接用于漂移计算**（原因见 R7）；漂移检测服务直接查询数据库。
- `Category` 模型已有 `asset_type` 字段（`'physical'` / `'financial'`），大类漂移计算通过 JOIN `categories` 表区分实物/金融资产，无需扩展 `AllocationItem` schema。
- 总资产为零（新家庭）时跳过漂移检测，不生成预警。
- 假设家庭平均设置 2-5 个类别目标，漂移计算复杂度可控。

---

## Outstanding Questions

### Resolve Before Planning

无阻塞问题。

### Deferred to Planning

- **[影响 R0a][技术]** 与创意 #3/#5 共享 scheduler 实例时，各 job 的注册位置（统一在 `scheduler.py` 还是各自模块 `add_job`）和启动顺序需在规划时确认。
- **[影响 R20][技术]** Dashboard 配置饼图的 DOM 锚点 ID 需要在规划时确认，确保点击漂移卡片后能正确滚动到饼图位置。

---

## Next Steps

→ 7 个创意的 brainstorm 全部完成。建议下一步：`/ce:plan`（从 Phase 0 基础设施开始，按优先级顺序规划实现方案）。
