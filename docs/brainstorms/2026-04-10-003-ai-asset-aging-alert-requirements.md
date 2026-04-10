---
date: 2026-04-10
topic: ai-asset-aging-alert
---

# 固定资产老化预警与换购建议

## Problem Frame

Numina 已存储 `expected_lifespan_days`、`annual_maintenance_cost`、`usage_frequency` 等字段，后端也已实现 `get_expiring_soon_assets()`（90天阈值检测）和 `get_low_usage_assets()`，但这些数据完全被动——用户看到"剩余30天"的数字，却不知道该做什么。

本功能在现有检测逻辑之上增加 AI 叙事层：为每项接近或超出预期寿命的资产生成具体的换购建议，以 Dashboard 推送卡片形式主动呈现，将被动数据转化为前瞻性行动提示。

**依赖关系：** 此功能依赖创意 #2（智能资产录入助手）提升 `expected_lifespan_days` 字段填写率；字段填写率低时覆盖面窄，但功能本身对已填写字段的资产立即生效。

```
每周定时任务（周一 08:00 Asia/Shanghai）
         │
         ▼
  查询家庭所有 ai_enabled == True 的家庭
         │
         ▼
  对每个家庭：扫描符合 R3 触发条件的资产（status == 'in_use'，阈值180天）
         │
         ▼
  有符合条件的资产？ ──否──▶ 跳过，不生成
         │
         是
         ▼
  对每项资产构造脱敏 prompt（类别+剩余天数+维护成本区间+使用频率）
         │
         ▼
  调用 LLM 生成单项建议文本（同一家庭内串行）
         │
         ▼
  写入 ai_asset_alerts 表（UPSERT：同一 asset_id 覆盖旧记录，is_dismissed 重置为 False）
         │
         ▼
  用户进入 Dashboard → 读取缓存建议 → 渲染预警卡片
```

---

## Requirements

**AI 基础设施前提（依赖 Phase 0）**

- R0. 依赖 `docs/brainstorms/2026-04-10-001-ai-health-report-requirements.md` 中 R0-R6 的基础设施。

**后端：定时生成**

- R1. 新增 `ai_asset_alerts` 表，字段：`id`、`family_id`、`asset_id`（FK，`ON DELETE CASCADE`）、`alert_type`（`expiring_soon` / `overdue` / `high_maintenance`）、`suggestion_text`（AI 生成的中文建议）、`severity`（`warning` / `critical`）、`remaining_days`（生成时快照，`high_maintenance` 专属预警此字段为 `NULL`）、`generated_at`、`is_dismissed`（用户已忽略标志）。
- R2. APScheduler 每周一 08:00 Asia/Shanghai（随机偏移 0-15 分钟）扫描所有 `ai_enabled == True` 的家庭，为符合条件的资产生成建议，写入 `ai_asset_alerts` 表（UPSERT by `asset_id`：覆盖旧记录并将 `is_dismissed` 重置为 `False`，使本周新建议对用户重新可见）。
- R3. 触发条件（满足任一即生成）；仅扫描 `status == 'in_use'` 且未归档（`is_archived == False`）的资产：
  - `expiring_soon`：`remaining_days <= 180` 且 `remaining_days > 0`（需 `purchase_date` 和 `expected_lifespan_days` 均不为 NULL）
  - `overdue`：`remaining_days <= 0`（需 `purchase_date` 和 `expected_lifespan_days` 均不为 NULL）
  - `high_maintenance`：`annual_maintenance_cost > current_value * 0.15`（需 `current_value > 0` 且 `annual_maintenance_cost` 不为 NULL，避免除零）
- R4. 脱敏要求：发送给 LLM 的 prompt 包含资产类别名、`remaining_days`（`high_maintenance` 专属预警此字段省略）、`annual_maintenance_cost`（金额区间而非精确值：<500 / 500-2000 / 2000-5000 / >5000）、`usage_frequency`、`asset_type`；不包含资产名称、精确金额、成员信息。
- R5. 每项资产的建议文本长度控制在 50-120 字，语气务实简洁，包含：现状描述 + 建议行动（继续使用 / 关注维修 / 考虑换购）+ 简短理由。
- R6. 单次定时任务中，同一家庭的 LLM 调用串行执行（避免并发超出 API rate limit）；单个家庭处理失败不影响其他家庭。
- R7. `GET /api/v1/ai/asset-alerts` 返回当前家庭所有未忽略的预警列表，按 `severity` 降序排列；同等 severity 内，有 `remaining_days` 的记录按 `remaining_days` 升序排在前，`remaining_days` 为 NULL 的 `high_maintenance` 预警排在最后。
- R8. `POST /api/v1/ai/asset-alerts/{id}/dismiss` 将指定预警标记为 `is_dismissed = True`，不再在 Dashboard 展示；下次定时任务 UPSERT 时 `is_dismissed` 重置为 `False`，预警重新出现。

**前端：Dashboard 预警卡片**

- R9. `DashboardPage.vue` 新增"资产预警"卡片区，位于 Dashboard 顶部（overview 卡片之后）；当无预警时该区域不渲染（不占位）。
- R10. 每条预警以 Vant `Cell` 列表项展示：左侧资产类别 icon、中间"[类别名] · [alert_type 中文]"+ AI 建议文本（最多显示2行，超出省略）、右侧 severity 色点（warning=橙，critical=红）。
- R11. 点击预警项跳转至对应 `AssetDetailPage.vue`，并高亮显示完整 AI 建议文本（通过 route query 参数传递 `highlight=true`）。
- R12. 每条预警右侧有"忽略"按钮（Vant `SwipeCell` 左滑展开），点击后调用 dismiss 接口，该条预警从列表中移除（带 slide-out 动画）。
- R13. 预警卡片区标题显示"资产预警（N）"，N 为当前未忽略预警数量；N > 0 时标题左侧显示红点。
- R14. 当 `ai_enabled == False` 时，预警卡片区不渲染，不展示任何占位或引导。

**alert_type 中文映射**

| alert_type | 中文显示 | severity 默认值 |
|---|---|---|
| `expiring_soon` | 即将到期 | `warning` |
| `overdue` | 已超期 | `critical` |
| `high_maintenance` | 维护成本偏高 | `warning` |

---

## Success Criteria

- 定时任务每周成功运行，`ai_asset_alerts` 表有新记录写入（可通过日志验证）。
- Dashboard 预警卡片在有未忽略预警时正确渲染，无预警时不占位。
- 忽略操作后预警从列表消失，下次定时任务后重新出现。
- 发送给 LLM 的 prompt 中不包含精确金额或资产名称（可通过日志验证）。
- 建议文本长度在 50-120 字范围内（后端校验，超出则截断或重试一次）。
- 资产被删除后，对应预警记录自动级联删除，不出现孤立预警。

---

## Scope Boundaries

- 不包含用户自定义预警阈值（180天和15%维护比率为固定值，首版不可配置）。
- 不包含预警的推送通知（App Push / 微信通知）——用户进入 Dashboard 时被动看到。
- 不包含"换购价格估算"——建议文本只给行动方向，不给具体价格（避免 LLM 幻觉金额）。
- 不包含资产维修记录追踪——`high_maintenance` 触发条件基于 `annual_maintenance_cost` 字段，不基于实际维修记录。
- `is_dismissed` 在下次定时任务 UPSERT 时自动重置，不提供永久忽略选项。
- 已归档（`is_archived == True`）或非 `in_use` 状态的资产不触发预警扫描。

---

## Key Decisions

- **定时后台生成** — 用户进入 Dashboard 时直接读取缓存，响应即时；避免实时生成的等待感。
- **每项资产独立建议** — 精准可操作，用户知道具体该对哪项资产做什么；汇总建议信息密度低。
- **Dashboard 推送卡片** — 融入现有浏览流程，无需新增导航入口；资产详情页内嵌过于被动。
- **同一资产旧记录 UPSERT 覆盖** — 避免历史建议堆积；用户每周看到的是最新评估，不是历史存档。
- **`is_dismissed` 随 UPSERT 重置** — 防止用户忽略后永远看不到更新的建议；每周重新评估是否仍需关注。
- **`asset_id` FK ON DELETE CASCADE** — 资产删除后预警自动清理，避免 Dashboard 出现指向已删除资产的孤立预警卡片。
- **`remaining_days` 存入表中** — R7 排序需要此字段；`high_maintenance` 专属预警无寿命概念，存 NULL 并在排序时置后。

---

## Dependencies / Assumptions

- 依赖 Phase 0 基础设施（`agent/` 模块、`ai_enabled` 开关、APScheduler）。
- 依赖创意 #2（智能资产录入助手）提升 `expected_lifespan_days` 字段填写率，但本功能对已填写字段立即生效。
- 定时任务扫描逻辑独立实现（不直接复用 `get_expiring_soon_assets()`），原因：现有函数返回 `ExpiringSoonItem` schema 对象且绑定 `User` 上下文，定时任务需要跨家庭批量扫描原始 `Asset` 模型行；阈值扩展到 180 天可参考现有逻辑。
- `high_maintenance` 触发条件要求 `current_value > 0` 且 `annual_maintenance_cost IS NOT NULL`，否则跳过该资产（避免除零和空值误判）。
- 假设每个家庭平均有 3-10 项符合条件的资产，每周 LLM 调用量可控。
- 新建家庭无资产时，定时任务对该家庭无操作（符合 R3 的资产集合为空，直接跳过）。
- 所有预警均被用户忽略后，Dashboard 预警区域不渲染（R9 已覆盖）；下次定时任务 UPSERT 后预警重新出现。

---

## Outstanding Questions

### Resolve Before Planning

无阻塞问题。

### Deferred to Planning

- **[影响 R2][技术]** 多实例部署时定时任务重复触发问题（与体检报告 R9 相同）——需要分布式锁或幂等设计，规划时统一处理。
- **[影响 R11][技术]** `AssetDetailPage.vue` 通过 `route.query.highlight` 高亮 AI 建议的具体实现：需要确认详情页是否已有 `notes` 或建议展示区域可复用。
- **[影响 R3][需要研究]** `high_maintenance` 的 15% 阈值是否合理？可在规划时通过测试数据验证，首版硬编码，后续可配置化。

---

## Next Steps

→ `/ce:brainstorm`（创意 #4：负债优化建议）
