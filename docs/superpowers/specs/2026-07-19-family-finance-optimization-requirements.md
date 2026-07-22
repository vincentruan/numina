# Numina 家庭财务优化 — 需求清单与批次规划

> **状态**：需求已确认，待 P0 批次逐条设计
> **日期**：2026-07-19
> **来源**：main app 全 7 模块 UI/UX 审视（ui-ux-pro-max skill）
> **决策**：①C 全做(P0-P2) / ②B 财务 hub / ③C AI 主动+被动 / ④A 心愿手动 / ⑤A 分 3 批 / ⑥C hub 概览首屏

---

## 1. 背景与目标

Numina 当前定位是"家庭资产可视化仪表盘"，用户诉求是"家庭财务优化/花销控制/财富增值"。核心 gap：六个模块是六个独立工具，而非一条财务决策链。

**目标闭环**：
```
总览(诊断) → 负债(止血) → 花销控制(节流) → 心愿(目标储蓄) → 财富增值(开源) → AI(教练贯穿)
```

**四个已确认关键决策**：

| 决策 | 选择 | 连锁影响 |
|------|------|---------|
| ① 范围 | C — P0+P1+P2 全做 | 约 31 项，分 3 批 |
| ② 导航 | B — 财务 hub | 心愿/负债/资产合并为 `/finance` 内 sub-tab；导航 6→5 |
| ③ AI 触点 | C — 主动+被动 | Dashboard 主动推送(8h 缓存复用报告机制) + 负债/心愿详情被动按钮 |
| ④ 心愿数据 | A — 纯手动 | wish 表加 3 字段(saved_amount/target_date/monthly_saving)，无预算依赖 |
| ⑤ 节奏 | A — 分 3 批 | P0(8)→P1(13)→P2(10)，每批 spec→plan→实现→验证 |
| ⑥ hub 结构 | C — 概览首屏 | `/finance` 首屏财务概览卡(净资产+月还+心愿进度)+下钻 tab |

---

## 2. 批次划分

- **P0 批（8 项）** — 打通财务闭环核心价值：心愿储蓄化 + 负债还款策略 + AI 教练触点
- **P1 批（13 项）** — 体验一致性与信息流连贯性：财务 hub 落地、删死页/孤儿、下钻、加载态、导航降级
- **P2 批（10 项）** — i18n 合规与可访问性

> P1 含 N1(财务 hub 落地) 与 ⑥C 概览首屏，是 P1 中改动最大的单项，单独成子计划。

---

## 3. 需求项总表（32 项）

### 域 1：心愿模块（Wishes）— 储蓄目标化

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| W1 | P0 | 心愿增加储蓄进度字段 | 后端 wish 表加 `saved_amount`/`target_date`/`monthly_saving`；详情页进度条 `已存 ¥X / ¥Y (Z%)` |
| W2 | P0 | Afford bar 逻辑重构 | 从"净资产够买"改为"按月存节奏预计 N 月达成"=`(price-saved)/monthly_saving` |
| W4 | P0 | 心愿优先级 AI 建议 | 多心愿时给"本月建议优先为 X 存 ¥Y"，基于优先级+距 target_date 天数+月存 |
| W5 | P0 | 高息负债与心愿联动提示 | 高息负债未清前，提示"建议优先还债(利率 18%)而非低优先级心愿" |
| W6b | P3 | 心愿→资产转化回链 | realized 且 converts_to_asset 时显示"已转化为资产"并回链 |
| W6 | P2 | 去 emoji 兜底 + 硬编码 ¥ | SVG icon + useCurrency |

### 域 2：负债模块（Liabilities）— 还款策略化

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| L1 | P0 | AI 建议还款顺序 | 详情页 avalanche(高利率优先) 每笔利息成本/月 vs snowball(低余额优先) |
| L2 | P0 | 利息成本预测 | "预计总利息 ¥X，若每月多还 ¥Y 可省 ¥Z、提前 N 月还清" |
| L4 | P1 | 快捷还款加"一次性还清"按钮 | dialog 加按钮，金额=remaining_amount |
| L5 | P1 | PaymentCountdown 语义修正 | 基于"下次还款日"而非"开始日" |
| L3 | P1 | 列表 banner 月度还款总览 | "本月待还总额"(可选占月收入比，本期不接收入则只显总额) |
| L6 | P2 | 去 ¥ 硬编码 | useCurrency |
| L7 | P3 | linked_asset 联动 | 显示"抵押物现值 vs 剩余贷款" |

### 域 3：总览/分析（Dashboard/Analytics/Insights）

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| D2 | P0 | Dashboard 处方性 AI 教练卡片 | 主动推送(③C)，复用 8h 缓存机制，1-2 条可操作建议直跳资产/负债 |
| D1 | P1 | 修复 owner 待审批不可见 | PendingApprovalsSection 接入 DashboardPage(fetch 了不渲染) |
| D3 | P1 | NetWorthCard 净资产/总负债可点 | 下钻到 `/finance?tab=liabilities` 或 `/assets` |
| D4 | P1 | 环比加绝对金额 | 百分比 + `+¥X` |
| D5 | P1 | 删 /stats 死页 | DataStatsPage + 路由移除(recentAssetsCount 永远 0) |
| D6 | P1 | 删 2 孤儿组件 | AlertCards.vue / UpcomingPaymentsCard.vue |
| D7 | P1 | 加载态修正 | 区分 loading(skeleton) vs empty |
| D8 | P3 | 保值率拆实物/金融 | 金融资产用期间收益率 |
| D9 | P2 | 修假 affordance | 低使用率 is-link 补 click / 领奖台 chip 去 pointer |
| D10 | P2 | StatusSummaryGrid a11y | `<button role=tab aria-selected>` 键盘可达 |

### 域 4：AI 模块（Hub/Chat/Report）— 教练触点化

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| A1 | P0 | AI 教练触点嵌入其他模块 | 拆 A1a(Dashboard 主动，与 D2 合并) + A1b(负债/心愿详情被动按钮) |
| A2 | P1 | AIHub 上传死桩 | 实现或移除入口(triggerFileUpload NPE) |
| A3 | P1 | AIReport 统一渲染管线 | 废弃 legacy 分支，消除三种格式不一致 |
| A4 | P2 | score-poor 绿改红 | `#4caf50`→红/橙(语义错误) |
| A5 | P2 | SECTION_LABELS 迁 i18n | 硬编码中文 `t('aiReport.section.*')` |
| A6 | P3 | 报告 PDF/图片导出 | |
| A7 | P2 | AI tab 加可见文字标签 | |

### 域 5：儿童管理（Baby）

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| B4 | P1 | "全部"日历模式提示 | 提示展示哪个孩子或聚合视图 |
| B5 | P2 | 卡片补 a11y | role=button + 键盘 handler |
| B3 | P2 | fulfilled 组移除 rejected | 分组分开 |
| B2 | P2 | 优先级短标签迁 i18n | 去 emoji `🔥高` 等 |
| B1 | P3 | 可选教育联动 | 家务→真实记账"教育奖励金"(需产品决策) |

### 域 6：设置/家庭（Settings/Family）

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| F3 | P1 | 子卡片 pending 数改本孩子 | 非家庭级重复 |
| F7 | P1 | Family 页加入 KeepAlive | cachedTabs |
| S1 | P2 | 主题色服务端持久化 | user settings API |
| S2 | P2 | 非 owner 隐藏 is-link 箭头 | |
| S3 | P2 | 主题选项去 emoji | `🌓`/`☀️`/`🌙` |
| F2 | P2 | clipboard 改用 copyToClipboard util | |
| F6 | P2 | section heading 去 emoji + h2 语义 | |

### 域 7：导航与跨模块连贯性

| ID | 批 | 需求 | 数据/实现要点 |
|----|----|------|--------------|
| N1 | P1 | 财务 hub 落地(②B+⑥C) | 新建 FinanceHubPage，首屏概览卡(净资产+月还+心愿进度)+三 tab(资产|负债|心愿)；导航 6→5 |
| N2 | P2 | 跨模块 a11y 整改 | div+@click→button+role+键盘 |
| N3 | P2 | 币种统一 | 硬编码 ¥ 全走 useCurrency |

---

## 4. P0 批次（8 项）— 本轮设计目标

| ID | 需求 | 所属域 |
|----|------|--------|
| W1 | 心愿储蓄进度字段 | 心愿 |
| W2 | Afford bar 逻辑重构 | 心愿 |
| W4 | 心愿优先级 AI 建议 | 心愿 |
| W5 | 高息负债与心愿联动提示 | 心愿 |
| L1 | AI 建议还款顺序 | 负债 |
| L2 | 利息成本预测 | 负债 |
| D2 | Dashboard 处方性 AI 教练卡片 | 总览 |
| A1 | AI 教练触点嵌入(A1a+A1b) | AI |

> 注：D2 与 A1a 合并为同一需求（Dashboard 主动推送 AI 教练卡片），故 P0 实际独立项为 8。

**P0 的内在依赖**：
- W1 → W2（进度字段是 afford bar 重构前提）
- W1 → W4（AI 建议需要月存数据）
- L1 + L2 共享负债利息计算逻辑（可抽公共 util）
- D2/A1a（主动推送）与 A1b（被动按钮）共享 AI 教练 prompt 模板
- W5 依赖 L1（需识别"高息"负债）

---

## 5. 待办

- [x] 需求清单成文（本文档）
- [x] P0 八项逐条设计确认 → [p0-family-finance-core-design.md](./2026-07-19-p0-family-finance-core-design.md)
- [x] P0 spec 落地 → writing-plans 出实现计划 → 已实现（[Plan A](../plans/2026-07-19-plan-a-finance-coach-capability.md) + [Plan B](../plans/2026-07-19-plan-b-p0-business-touchpoints.md)，8/8 项完成）
- [x] P1 批次 plan 落地（含 N1 财务 hub，单独子计划）→ [N1 子计划](../plans/2026-07-21-p1-n1-finance-hub-plan.md) + [其余 12 项](../plans/2026-07-21-p1-remaining-12-items-plan.md)（status: complete）
- [x] P1 批次实现 + 验证（N1 + 14 项，2026-07-22 全部完成）
- [x] P2 批次 plan 落地 → [P2 计划](../plans/2026-07-22-p2-compliance-a11y-plan.md)（status: complete）
- [x] P2 批次实现 + 验证（17 项，2026-07-22 全部完成；A5/S2 已满足跳过）

---

## 附：决策回溯

- **②B 财务 hub**：心愿/负债/资产从顶级 tab 降为 `/finance` sub-tab，导航 6→5
- **⑥C 概览首屏**：`/finance` 首屏展示财务概览卡（净资产+月还+心愿进度），再进 tab 下钻
- **③C AI**：Dashboard 用主动推送（复用 8h 缓存报告机制，新增轻量"教练建议"capability）；负债/心愿详情用被动按钮（跳 `/ai/chat` 带 context）
- **④A 心愿**：纯手动存入，无预算/收入依赖；W2 预测公式 `(price-saved)/monthly_saving`
