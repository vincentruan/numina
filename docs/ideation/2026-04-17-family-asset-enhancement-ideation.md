---
date: 2026-04-17
topic: family-asset-enhancement
focus: 第一性原理 × 孩童视角 × Agent增强
---

# Ideation: 家庭资产管理系统三维增强

## Codebase Context

**项目形态：** Vue 3 + FastAPI + SQLite，38个页面，基于角色的访问控制（owner/member/child）

**已实现能力：**
- 核心：资产（实物/金融）、负债、心愿、分类、标签、快照
- 儿童经济：金币交易、家务（赚取）、宝贝（消费）、里程碑、PIN登录
- AI能力：报告、预警、处置建议、配置漂移、负债分析、聊天、资产建议
- 家庭：多成员、邀请码、角色管理、导入/导出

**已记录的架构模式：**
- Append-only金币账本（不可变交易历史）
- 快照式家务实例（保留创建时的模板状态）
- PII脱敏 + 策略守卫 + 审计日志（agent层）
- 批量端点防N+1（`/family/children/balances`）
- 缓存后端抽象（memory/Redis，fail-fast策略）

**关键缺口（来自代码扫描）：**
- 家务审批队列无角标通知，父母不知道孩子在等待
- 心愿进度显示百分比，孩子无法理解抽象数字
- 负债是静态快照，无月供计划或还款日倒计时
- `chore_narrative.py` 已生成审批叙事，但无财商教育内容
- `ChoreInstance` 有 `child_user_id`，但无跨孩子公平性统计
- 儿童首页英雄区是余额数字，任务完成是次要信息

---

## Ranked Ideas

### 1. 任务优先的儿童首页（翻转英雄区）
**Description:** 将 `ChildHomePage.vue` 的英雄区从「余额数字」改为「今日任务完成环」——圆形进度条显示 completed/total，中心显示今日可获得的总星星币。余额降级为副标题。完成所有任务后，首屏变为庆祝状态。

**Rationale:** 孩子打开 app 的核心动机是「完成任务赚币」，不是「查余额」。当前信息层级倒置——结果（余额）比行动（任务）更突出。`todayChores` 数据已在同一个 `onMounted` 中加载，只需重排 UI 优先级，无需新 API。

**Downsides:** 需要重新设计英雄区组件；余额降级可能让部分用户感到信息减少。

**Confidence:** 88%

**Complexity:** Low

**Status:** Unexplored

---

### 2. 家务审批角标通知
**Description:** 在 `AppTabBar.vue` 的「家庭」tab 上增加 `van-badge`，显示待审批家务数量。数据来自现有 `GET /family/chore-approvals` 端点（已返回 pending 列表），前端在 `FamilyPage` 或全局 store 中轮询计数。

**Rationale:** 孩子提交任务后进入「pending_approval」死区，父母不知道。审批延迟直接破坏即时反馈循环——完成行为和获得奖励之间的时间越长，行为强化越弱。这个问题不需要新功能，只需把现有数据暴露在正确位置。

**Downsides:** 需要轮询或 store 级别的状态管理；角标数字可能在父母处理后有短暂延迟。

**Confidence:** 92%

**Complexity:** Low

**Status:** Unexplored

---

### 3. 心愿「还需几天家务」计算
**Description:** 在 `ChildWishesPage.vue` 的进度条下方，显示「再做约 X 天家务就能实现 🎯」。基于近7天金币交易计算日均赚取速率（`coins_per_day_avg`），前端计算 `days_to_afford = ceil((cost - balance) / daily_avg)`。数据来自现有 `/child/coins/ledger` 端点。

**Rationale:** 孩子的时间感知是具体的（今天、明天），不是抽象的（47%）。把抽象进度翻译成可操作的行动，直接降低放弃心愿的概率，也让家务的激励闭环更紧密。当前 `ChildWishesPage.vue` 只渲染 `Math.round((wish.progress ?? 0) * 100) + '%'`，是一个已识别的设计意图和实现之间的裂缝。

**Downsides:** 日均速率在孩子刚开始使用时数据不足（需要至少7天历史）；需要处理「无历史数据」的边界状态。

**Confidence:** 85%

**Complexity:** Low

**Status:** Unexplored

---

### 4. Agent 预填心愿积分建议值
**Description:** 父母审核心愿时，Agent 自动计算并预填 `star_coin_cost` 建议值：「按孩子最近7天平均赚取速率，建议设为 X 颗星（约 N 天可实现）」。父母可接受或修改。计算逻辑是纯 SQL 聚合（`CoinTransaction` 历史），不需要 LLM。

**Rationale:** 空白输入框是决策摩擦的最高形式。父母要么随便填（导致心愿太容易或太难），要么放弃审核。Agent 已有家庭上下文（`orchestrator._build_context`），`CoinTransaction` 历史已存在。这是 agent 能力最自然的嵌入点——不是「AI 分析报告」，而是「帮你填一个数」。

**Downsides:** 需要在心愿审核 UI 中增加建议值展示区域；建议值可能因孩子赚币速率波动而不稳定。

**Confidence:** 82%

**Complexity:** Low–Medium

**Status:** Unexplored

---

### 5. 负债月供计划 + 还款日倒计时
**Description:** 在 `LiabilityDetailPage.vue` 顶部增加「距下次还款还有 N 天」倒计时，基于 `start_date + monthly_payment` 在前端计算 `next_payment_date`（每月同日）。同时在 dashboard `overview` 中增加 `upcoming_payments`（7天内到期的负债列表），在 `AlertCards.vue` 中展示。

**Rationale:** 家庭理财最高频的焦虑是「这个月还款日是哪天、还了没有」。当前 UI 只显示静态数字，用户必须自己心算。`Liability` 模型已有 `start_date`、`monthly_payment`、`end_date` 字段，`AlertCards.vue` 已存在于 dashboard 可复用。这是负债管理从「记录工具」到「提醒工具」的关键一步。

**Downsides:** 还款日计算需要处理月末边界（如2月28日、31日问题）；需要后端增加 `upcoming_payments` 聚合端点。

**Confidence:** 87%

**Complexity:** Low–Medium

**Status:** Unexplored

---

### 6. 家务公平性审计（跨孩子统计）
**Description:** 增加 `/family/chore-fairness` 端点，统计过去 N 天各孩子的完成率、获得金币、streak 分布。在 `ChoreApprovalsPage.vue` 或 `FamilyPage.vue` 中展示横向对比。Agent 可选地给出「小明本周做了 12 个家务，小红只做了 3 个，建议调整分配」的建议。

**Rationale:** 多孩家庭最常见的矛盾是「凭什么他比我少做」。父母现在只能靠感觉判断是否公平，没有数据支撑。`ChoreInstance` 已有 `child_user_id` 和 `date_bucket`，一个 GROUP BY 查询即可实现。这是 chore 系统从「记录工具」升级为「家庭管理工具」的关键一步。

**Downsides:** 仅对多孩家庭有价值（单孩家庭无意义）；「公平」的定义因家庭而异，统计数据可能被误读。

**Confidence:** 75%

**Complexity:** Medium

**Status:** Unexplored

---

### 7. 审批通过时的财商教育一句话
**Description:** 在家务审批通过时，`chore_narrative.py` 生成的叙事中增加一句财务素养小知识，把孩子的行为和家庭资产连接起来。例如：完成「整理玩具」→「你知道吗？保存好的玩具可以送给弟弟妹妹或者卖掉换新玩具 🎮」。这是在现有 LLM 调用中加一个 prompt 变体，不需要新 API 端点或数据模型。

**Rationale:** `chore_narrative.py` 已存在并生成审批叙事，现有叙事是纯机械确认（「你完成了扫地！获得 5 颗星」）。把叙事扩展为一句财务素养小知识，成本是在现有 LLM 调用中加一个 prompt 变体。这是 agent 能力最低摩擦的嵌入点，也是 Numina 区别于普通家务 app 的核心差异化。

**Downsides:** LLM 生成的教育内容质量不稳定，需要 prompt 工程和内容审核；对年龄较小的孩子（3-5岁）可能过于复杂。

**Confidence:** 78%

**Complexity:** Low

**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 2 | 余额变成「感受」（视觉填充条） | 孩子理解数字没有问题；隐藏余额会造成购买力混淆 |
| 8 | 孩子行为模式识别 + 个性化任务推荐 | 太模糊（「分析模式」如何实现？），成本高，无证据家庭需要算法任务分配 |
| 9 | 孩子财商教育进度追踪 + 里程碑增强 | 「财商阶段」定义不清，代码库中无对应模型，更适合作为 brainstorm 主题 |
| 10 | 跨期消费决策模拟器（孩子版） | #3 已覆盖核心洞察（还需几天），「模拟器」UI 过于模糊 |
| 11 | 孩子金币消费分析 | 代码库中金币消费交易（spend）数据不足，无法分析不存在的数据 |
| 12 | 心愿兑现主动提示横幅 | 父母已能在家庭页看到孩子心愿，增加横幅是噪音而非信号 |
| 13 | 资产「共有者」维度 | 资产已有 user_id 作用域，共有所有权增加复杂度但无明确家庭痛点 |
| 15 | 资产折旧曲线建模 | 折旧模型复杂（非线性、资产特定），current_value 已可手动编辑 |
| 16 | 资产价值自动更新（外部价格源） | 需要外部 API 集成 + 定时任务，大多数家庭资产（车、家具）无 ticker |
| 17 | 家庭净资产里程碑庆典 | 家庭不需要净资产游戏化，「庆典」实现过于模糊 |
| 18 | 月度净资产变化故事横幅 | 趋势图已覆盖月度变化，文字横幅是冗余 |
| 19 | 负债优化路径规划（雪球/雪崩法） | 需要摊销计划生成 + 优化算法，成本高于价值 |
| 20 | 资产配置漂移自动再平衡建议 | 需要投资组合优化算法 + 税务建模，大多数家庭不做再平衡 |
| 23 | Agent 给孩子「为什么」解释层 | 与 #7 重叠，但 #7 更具体（叙事扩展 vs 独立解释层） |
| 24 | Agent 事件驱动/定时触发 | 无事件总线或调度器基础设施，成本高于未验证的价值 |
| 25 | AI 聊天有记忆的顾问 | 需要聊天历史持久化 + 上下文管理，当前 agent 是无状态端点 |
| 26 | AI 报告「一句话摘要」推送首页 | 「摘要」内容未定义，现有 agent 已返回分析文本，增加缓存是过早优化 |
| 27 | 家庭财务健康度时间序列 + 预测性告警 | 「健康度」公式未定义，需要时间序列预测模型，成本高 |
| 28 | 资产生命周期处置决策树 | 家庭知道何时处置资产，「决策树」是过度工程化 |
| 29 | 家庭财务知识图谱 + 自然语言查询 | 需要知识图谱构建 + NLU，当前 agent 是简单 prompt 分析 |
| 30 | 家务公平性审计（已升级为 #6） | 已升级为 survivor |

---

## Session Log
- 2026-04-17: Initial ideation — 30 candidates generated across 6 frames, 7 survivors after adversarial filtering
