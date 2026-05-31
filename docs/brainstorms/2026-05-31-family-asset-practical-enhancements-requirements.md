---
date: 2026-05-31
topic: family-asset-practical-enhancements
source: 2026-04-17-family-asset-enhancement-ideation.md (Ideas #4, #5)
---

# 家庭资产实用增强：负债倒计时 + Agent 心愿建议

## Problem Frame

家庭资产管理的两个高频痛点未被覆盖：

1. **负债还款日无提醒** — `Liability` 模型已有 `start_date`、`monthly_payment`、`end_date` 字段，但 UI 仅展示静态数字，用户必须自己心算下次还款日。家庭理财最高频的焦虑是"这个月还款日是哪天"。
2. **心愿积分定价无参考** — 父母审核心愿时面对空白输入框（`ApproveChildWishRequest.star_coin_cost`），要么随便填（太容易/太难），要么放弃审核。系统已有 `CoinTransaction` 历史数据，可以自动建议合理积分值。

## Requirements

### Part A: 负债月供计划 + 还款日倒计时

- R1. `LiabilityDetailPage.vue` 顶部（value-card 下方）新增倒计时卡片："距下次还款还有 N 天"
- R2. 计算逻辑（前端）：基于 `start_date` 推算每月同日为还款日，取下一个未来日期
- R3. 月末边界处理：若 start_date 为 29/30/31 日，当月天数不足时取当月最后一天
- R4. `start_date` 为空时的降级：不显示倒计时卡片，仅展示静态负债信息（`start_date` 在模型中为 nullable）
- R5. `end_date` 已过期的负债：若当前日期 > `end_date`，不显示倒计时（贷款已结清）
- R6. 仅对 `is_active=True` 的负债显示倒计时
- R7. Dashboard 新增"即将到期"提醒区域：展示 7 天内到期的负债列表
- R8. 后端新增 `GET /dashboard/upcoming-payments?days=7` 端点，返回 `{ items: [{ liability_id, name, amount, due_date }] }`
- R9. 倒计时视觉：≤3 天显示红色警告色，4-7 天显示橙色提醒色，>7 天显示默认色
- R10. 无负债或无即将到期时，该提醒区域不渲染
- R11. 多笔负债同日到期时，合并展示总金额并列出各项明细

### Part B: 心愿积分建议值（纯计算，非 Agent/LLM）

- R12. 心愿审核页面（父母侧 `/family/child-wishes/{id}/approve` 流程）新增"建议积分"提示区域
- R13. 建议值计算：`suggested_cost = daily_avg_earning × target_days`，其中 `target_days` 提供 7/14/30 天三档
- R14. `daily_avg_earning` = 过去 7 天 `CoinTransaction` 中 `transaction_type IN ('chore_earn', 'parent_grant')` 且 `amount > 0` 的总额 / `max(actual_days, 3)`（分母至少为 3，避免仅 1-2 天数据时建议值虚高）
- R15. 展示门槛：实际有记录天数 < 3 时，视为数据不足，不展示建议值
- R16. 后端新增 `GET /family/children/{child_id}/earning-rate` 端点，返回 `{ daily_avg: float, suggested_7d: int, suggested_14d: int, suggested_30d: int, data_days: int }`
- R17. `data_days` 字段告知前端实际统计了多少天的数据，前端据此决定展示置信度
- R18. 前端展示："建议设为 {suggested_7d} 颗星（约 7 天可实现）"，父母可一键采纳或手动修改
- R19. 数据不足时（`data_days < 3`）显示"数据不足，暂无建议"，不展示建议值
- R20. 纯 SQL 聚合实现，不调用 LLM
- R21. `suggested_*` 值先向上取整（`math.ceil`），再取 `max(result, 1)` 确保最小为 1 星。当 `daily_avg = 0` 时整体触发数据不足降级（R19），不展示建议值
- R22. 建议值上限：单个建议不超过 9999 星（防止异常数据导致天文数字）

## Edge Cases

- **负债无 `start_date`**：跳过倒计时展示，不报错
- **负债 `monthly_payment` 为空**：倒计时仍可展示（日期计算不依赖金额），但 Dashboard 提醒中金额显示为"—"
- **闰年 2月29日**：start_date 为 1月31日时，2月取28日（非闰年）或29日（闰年）— 取当月最后一天逻辑自动处理
- **孩子无任何 CoinTransaction 记录**：`data_days = 0`，触发数据不足降级
- **孩子仅有支出记录（`wish_spend`）无收入**：`daily_avg = 0`，所有建议值为 0 → 触发下限保护，显示"数据不足"
- **多个孩子**：每个孩子独立计算 earning-rate，端点按 `child_id` 隔离
- **还款日恰好是今天**：倒计时显示"今天还款"而非"0 天"

## Acceptance Criteria

- [ ] 负债详情页显示"距下次还款还有 N 天"倒计时（仅 `is_active=True` 且 `start_date` 非空）
- [ ] Dashboard 提醒区域展示 7 天内到期的负债
- [ ] 月末边界正确处理（如 1月31日 → 2月28日）
- [ ] `start_date` 为空或 `end_date` 已过期时优雅降级
- [ ] 心愿审核页显示建议积分值（基于 `chore_earn` + `parent_grant` 交易）
- [ ] 建议值基于实际赚取历史计算，非 LLM
- [ ] 历史数据不足时（< 3 天）优雅降级
- [ ] 建议值有上限保护（≤ 9999）和下限保护（≥ 1 或不展示）
- [ ] 多笔负债同日到期时，Dashboard 合并展示总金额并可展开明细
- [ ] 所有新增 UI 字符串通过 i18n（`zh-CN.ts` + `en-US.ts`）
- [ ] 新端点遵循项目 URL 规范（无尾斜杠，SnowflakeBase 序列化）

## Out of Scope

- 家务公平性审计（多孩统计）— 中等复杂度，单独迭代
- 财商教育一句话（chore_narrative 扩展）— 依赖 prompt 工程，单独迭代
- 负债优化路径规划（雪球/雪崩法）— 已在 ideation 中 rejected
- 自定义还款日（允许用户覆盖 start_date 推算的日期）— 可作为后续增强
- 还款提醒推送通知（notification channel 集成）— 依赖 notification 子系统，单独迭代
- 建议值的 AI 解释文案（如"基于小明过去一周平均每天赚 5 颗星"）— 可后续增强
