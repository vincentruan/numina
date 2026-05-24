---
date: 2026-04-14
last_updated: 2026-05-24
topic: children-starcoin-gamification
focus: 为5-8岁儿童添加星星币积分系统，通过完成家务/学习任务赚取积分，兑换心愿，培养理财概念
focus_round_2: 把每日任务设计成游戏关卡 + 跨心愿可达性可视化（K of N 可实现 / 距离最高优先级心愿差多少）, 通过可玩性激励培养延迟满足习惯
mode: repo-grounded
---

# Ideation: 儿童星星币系统 — 孩子视角的家庭资产管理

## Codebase Context

**项目形态:** Numina — 隐私优先的自托管家庭资产管理系统
- Backend: FastAPI + SQLAlchemy + SQLite (Python 3.11+)
- Frontend: Vue 3 + TypeScript + Vite + Vant 4 (移动端优先)
- 部署: Docker Compose + Nginx

**现有基础设施（可复用）:**
- `Wish` 模型已有 `expected_price`、`status`（pending/realized/cancelled）、`realized_asset_id`，以及完整的 `realize_wish()` 流程（Wish → Asset）
- `Activity` 模型已有 `type/entity_type/entity_id/amount` 事件追踪模式
- `AssetSnapshot` 模型已有每日快照模式（可复用于余额历史）
- 图片上传管道已存在（`/api/v1/upload/image`，magic byte 验证）
- `User.role` 当前为 `owner`/`member`，需扩展为 `child`
- 前端路由无角色守卫，所有35个路由对所有认证用户开放

**明显缺口:**
- 无儿童用户类型、无游戏化系统、无家务/任务模型、无积分账本
- 无 PIN/表情符号认证路径
- 无儿童专属 UI 路由树

**关键历史教训:**
- 儿童 PIN 认证需要与密码认证相同的时序攻击保护（bcrypt dummy hash）
- Vant 4 `van-field` 显示计算值时必须用 `:model-value`，不能用 `:value`

---

## Ranked Ideas

### 1. 儿童身份系统 (Child Identity System)
**Description:** 三合一基础设施：(a) `User.role` 扩展为 `child`；(b) 表情符号 PIN 认证——从12个表情符号网格中选4个序列，bcrypt 哈希存储，专用登录端点，保留时序攻击保护；(c) 独立的 `/child/*` 路由树，配套 `ChildLayout.vue`（大图标、亮色、最少文字、滑动交互），与成人 `MainLayout` 完全隔离。父母在家庭管理页创建子账户，无需注册流程。子账户 session 有效期2小时（vs 成人7天）。

**Rationale:** 这是整个功能的基础。没有儿童角色，就没有权限隔离；没有 PIN 认证，5岁孩子无法独立登录；没有独立路由树，孩子会看到资产折旧、负债管理等成人界面。三者不可分割，必须作为第一个里程碑交付。表情符号 PIN 优于数字 PIN，因为5-6岁儿童可能还不能可靠地识别数字，但能识别表情符号。

**Downsides:** 需要修改 auth 系统（新端点、新 token 声明）；`User.role` 的 String(10) 需要确认能容纳 'child'（可以）；前端需要新的路由守卫逻辑。

**Confidence:** 95%
**Complexity:** Medium
**Status:** Unexplored

---

### 2. 核心赚取循环 (Core Earn Loop)
**Description:** 三层完整赚取流程：(a) **家务模板**——父母创建可复用模板（扫地、刷牙、读书20分钟），设定星星币奖励和复发频率（每日/每周），系统自动生成当日实例；(b) **父母审批队列**——孩子标记完成后进入审批队列，父母一键批准/拒绝，24小时无操作自动批准（可配置）；(c) **故事化账本**——每笔交易以表情符号+叙事方式呈现（"你连续7天整理了床铺！+5颗星⭐"），视觉时间线，余额始终由 SUM() 计算，账本只增不改。

**Rationale:** 没有赚取机制，星星币只是一个数字。家务模板解决了父母每天手动创建任务的摩擦（这是所有家务 app 死亡的主要原因）。审批队列保留了父母认可的情感价值（"做得好！"），同时通过超时自动批准防止孩子因等待而失去动力。故事化账本让5岁孩子理解"我做了什么，得到了什么"——这是财务素养的起点。

**Downsides:** 需要新的 `Chore`/`Task` 模型和 `CoinTransaction` 账本模型；自动批准超时需要在读取时计算（`pending_since + timeout < now`），避免引入后台调度器。

**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

---

### 3. 心愿兑现流水线 (Wish Fulfillment Pipeline)
**Description:** 四层完整兑换流程：(a) **不透明积分**——Wish 模型新增 `star_coin_cost` 字段（整数，儿童可见），`expected_price` 保持父母专属；(b) **储蓄罐可视化**——每个心愿对应一个动画储蓄罐，随积分积累而填充（CSS fill 动画，无需物理引擎），孩子无需看数字，只看罐子满了多少；(c) **积分门槛触发**——当孩子积分余额达到 `star_coin_cost` 时，系统通知父母并提供一键 `realize_wish` 操作；(d) **心愿变资产**——复用现有 `realize_wish()` 流程，心愿转化为孩子名下的资产，出现在"我的宝贝"中。

**Rationale:** 这是整个系统的核心价值主张，且复用了最多现有基础设施。`realize_wish()` 已经处理了 Wish→Asset 的原子转换。储蓄罐解决了5-8岁儿童无法理解抽象数字的认知问题（Piaget 前运算阶段）。不透明积分防止孩子将努力货币化，避免"我的家务比他的值钱"的比较焦虑。

**Downsides:** `star_coin_cost` 与 `expected_price` 的关系需要父母手动设定（不自动换算，因为换算会破坏不透明性）；储蓄罐动画需要前端新组件。

**Confidence:** 95%
**Complexity:** Low-Medium
**Status:** Unexplored

---

### 4. 连续打卡与里程碑庆典 (Streaks & Milestone Celebrations)
**Description:** 在 `User` 或 `ChoreAssignment` 上追踪 `streak_count` 和 `last_completed_date`。连续完成同一家务 N 天后，当日奖励增加（7天连续 = 1.5x，14天 = 2x，上限2x）。里程碑（第一次完成家务、第一个心愿实现、累计50颗星）触发全屏彩纸动画和可收集徽章。连续中断不惩罚——只是失去加成机会，已赚取的积分永不消失。

**Rationale:** 连续打卡是消费类教育 app 中最强的日留存机制（Duolingo 数据：连续打卡用户留存率2.4倍）。复利加成将"坚持有回报"这一核心财务概念通过直接体验传递，而非说教。"不惩罚中断"的设计对5-8岁儿童至关重要——失去连续记录已经足够令人失望，不需要额外惩罚。

**Downsides:** 徽章系统需要 `Badge` 模型 + `UserBadge` 关联表 + 徽章图片资源；v1 可以只做连续计数器，徽章留 v2。

**Confidence:** 88%
**Complexity:** Low (streak only) / Medium (with badges)
**Status:** Unexplored

---

### 5. 我的宝贝 (My Treasures Gallery)
**Description:** 当心愿通过积分兑现后，生成的资产以"我的宝贝"画廊形式展示——视觉网格（非表格），每件物品显示照片、名称、获得日期、花费了多少颗星。不显示购买价格、当前价值、日均成本等成人字段。孩子可以为每件宝贝拍照（复用现有图片上传管道，`Asset.image_url`）。画廊底部显示汇总："你已经赚到了12件宝贝，共花费240颗星！"

**Rationale:** 将资产追踪从财务工具重新定义为"成就展示"。对6岁孩子来说，看到一排通过努力赚来的东西，是内在激励的最强来源。复用 `realize_wish()` 流程——心愿变资产的管道已存在，只需要儿童友好的展示层。图片上传管道已存在（`backend/data/uploads/images/` 目录已有日期分组结构）。

**Downsides:** 需要过滤掉成人资产字段；需要区分"儿童赚取的资产"和"家庭资产"（可通过 `Asset.user_id` 过滤，或新增 `is_child_earned` 标志）。

**Confidence:** 87%
**Complexity:** Low
**Status:** Unexplored

---

### 6. 亲子双视角仪表盘 (Asymmetric Parent-Child Dashboard)
**Description:** 同一数据，两种视角。**儿童视角**：储蓄罐（当前积分/目标）、今日家务列表、连续打卡火焰、"我的宝贝"入口——全部大图标、亮色、无数字超过999。**父母视角**：家务完成率、待审批队列、各孩子积分余额、心愿进度、一键奖励积分（附原因备注）、积分倍率调节（1x/1.5x/2x，用于"双倍星星周末"等家庭活动）。两个视角从同一 `CoinTransaction` 账本和 `ChoreCompletion` 记录计算。

**Rationale:** 父母和孩子需要根本不同的界面——不是同一界面的过滤版本，而是为各自目标设计的独立体验。父母需要管理和监督工具；孩子需要激励和进度可视化。积分倍率调节（"双倍星星周末"）让父母成为积极的经济参与者，而非只是审批机器，同时引入了"特殊事件"的概念，保持系统长期新鲜感。

**Downsides:** 两套 UI 组件；父母视角的积分经济指标需要新的聚合查询。

**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

---

### 8. 金银铜星星币视觉体系 (Tiered Coin Visual System)
**Description:** 星星币不是一个抽象数字，而是三种实体硬币：铜星币（基础单位）、银星币、金星币。三者兑换比例可配置（默认 10铜=1银，10银=1金）。铜币等值货币可配置（默认 1铜=1分钱，即100铜=1元）。每种硬币设计为独立 SVG——圆形硬币侧面倾斜展示（透视椭圆），正面花纹为一颗五角星，金/银/铜三种配色各有独立的金属光泽渐变。积分显示时自动换算并展示最高面值组合（如"2金 3银 5铜"），储蓄罐动画中硬币落入时按面值显示对应图标。

**Rationale:** 纯数字积分对5-8岁孩子缺乏实体感。金银铜分级让孩子直观感受到"积累"——铜币攒多了变成银币，银币攒多了变成金币，这个升级瞬间是强烈的正向反馈。三级体系也自然引入了"面值"概念（同样是财务素养的基础）。SVG 硬币可复用于储蓄罐动画、账本条目图标、里程碑庆典动画，是整个儿童 UI 的视觉语言基础。铜币锚定真实货币让父母能直观理解积分价值，同时对孩子保持不透明（孩子只看硬币，不看人民币）。

**Downsides:** 需要设计3个高质量 SVG（侧面透视硬币，有金属光泽渐变）；兑换比例配置需要新的家庭级配置字段；积分显示逻辑需要换算函数（总铜币数 → 金银铜组合）。

**Confidence:** 88%
**Complexity:** Low (SVG + 配置字段 + 显示组件)
**Status:** Unexplored

---

### 7. 兄弟姐妹积分赠送 (Sibling Coin Gifting)
**Description:** 同一家庭内的孩子可以互相赠送星星币。赠送流程：选择兄弟姐妹 → 输入数量（不超过余额）→ 添加表情符号原因 → 立即到账。所有转账记录在 `CoinTransaction` 账本中（`transaction_type='gift'`，`from_user_id` + `to_user_id`）。父母在家庭活动流中可见所有转账，但无需审批。每周汇总通知父母赠送模式。

**Rationale:** 真实的金钱在人与人之间流动。让兄弟姐妹互赠积分引入了自愿交换和机会成本的概念（赠出积分会延迟自己的心愿）。对多孩家庭，这也创造了一个社会安全网——积分赚得快的孩子可以帮助积分少的弟弟妹妹。实现成本低：双向账本条目 + 余额校验。

**Downsides:** 需要 `CoinTransaction` 账本先存在（依赖 Idea #2）；需要防止冲动赠送（可加确认步骤）；仅适用于多孩家庭。

**Confidence:** 72%
**Complexity:** Low (given ledger exists)
**Status:** Unexplored

---

## Round 2 Grounding (2026-05-24) — Task-as-Daily-Level + Cross-Wish Affordability

**已落地的相关基础设施**（Round 1 之后已交付，是 Round 2 的复用起点）:
- `ChildTasksPage.vue` 现状: 日期导航 + 平铺 chore 卡片列表 + ochre 余额 hero。任务完成→celebration → milestone → blind-box check。状态: `available` / `pending_approval`(CandleFlame) / `approved`(dim) / `rejected`(dim)。**无"今日清空"终态**, **无下一关预览**。
- `ChildWishesPage.vue` 现状: 按 status 分组的心愿列表, 每心愿独立 progress bar + 25/50/75% 星标 + "再做约 X 天家务"估算（7 天均值, ≥3 个有收入的天）。**无跨心愿视图**, **无 affordability 矩阵**。
- `ChildWishStats.priority_simulation[]` API **已经返回每个心愿的 `{ star_coin_cost, progress, covered, shortfall_for_high_priority }`** —— affordability 数学已在服务端, **缺的只是 UI**。
- 庆典素材库已就绪: `CandleFlame`, `FlyToTarget`, `LandingBurst`, `StreakLayer`, `TrailResidue`, `TreasureRevealPopup`, `MilestoneCelebration`（Teleport overlay, 20-particle confetti, Clay 颜色）。
- 金银铜 SVG 硬币 + `CoinDisplay`（animate-changes, tier-aware）已实现（Idea #8 已落地）。
- `useCelebration` 编排触发；`celebrationState.ts` 50-ID localStorage dedup；`useReducedMotion` 单例；`motionTokens.ts` 集中 durations / easings / scales / haptics。
- i18n 已有 `chore.*`, `wishes.*`, `challenge.*`, `home.*`, `ledger.*` 键集。`abandonWishHint` 已是跨心愿提示的雏形。

**Round 2 焦点的明显缺口**:
- 无"今日全部完成"庆典 / 关卡终态。dim != celebrate。
- 无跨心愿快照（"K 个可实现 / 共 N 个"）—— 服务端数据齐, UI 零。
- 无"如果我兑换 A, B/C 会延迟多少"的 trade-off 预演。
- 无下一关 / 明日预告。
- 无空任务日的 graceful 状态（当前等于死页）。
- 无连击中断的"宽限"机制（streak counter 只是数字, 没有"护身符"概念）。

**外部研究关键洞察**（Round 2, 与 Round 1 互补）:
- Duolingo / KhanKids: **单一蜿蜒线性路径**, 永不分支。3 个节点可见即可（已完成金星 / 当前脉动 / 下一个 dim / 未来雾化）。分支 = 5-7 岁 paralysis。
- 儿童银行类（GoHenry / Greenlight / RoosterMoney）**全部 silo 各心愿** —— 没有一家展示"K of N 可实现"。这是**未被占领的设计空间**。
- Mischel 棉花糖 NYU 2018 复制研究: 延迟能力是**情境性**的, 非固定特质。Kidd 2013: **对系统的信任 > 意志力**。"移动球门柱"（中途改心愿价格）会摧毁信任。
- 失败模式回避: >7 个每日任务 = overwhelm；ages 5-6 的数字 >100 不可推理；红 X / 哭脸 = 羞耻螺旋；single 锁路阻塞所有进度 = 卡死。
- 连击宽限（Duolingo streak freeze）: **永不展示零**。一日宽限是隐式补偿, 用户感知不到补偿何时启动。

## Topic Axes (Round 2)

1. **Daily quest progression** — 今日任务链的关卡形态、清空状态、下一关预览
2. **Cross-wish reachability viz** — 多心愿相对可达性的可视化
3. **Trade-off / opportunity-cost surface** — 兑换/分配时的机会成本可见性
4. **Pacing & loss aversion** — 多日节奏、连击/宽限/承诺
5. **Stuck & escape-valve states** — 空任务日、待审批、未设心愿的 graceful 出口

---

### 9. 今日关卡 (Daily Level Manifest + Day-Cleared Ring + Optional Earning Ceiling)
**Description:** 三层组合: (a) **`dailyLevel` view-model** —— 从现有 `GET /child/chores?date=` 派生 `{ stages, cleared_count, total_remaining, day_complete, next_node_index }`, 不改后端; (b) **关卡完成度环** —— `ChildTasksPage.vue` 顶部一个圆环, N 个段对应今日 N 件 chore, 顺时针随完成/批准点亮, 中心实时计数 "3/5"; (c) **Day Cleared 终态** —— 最后一段点亮触发"今日通关"全屏 overlay（复用 `LandingBurst` + `MilestoneCelebration`, 仅新增 `useCelebration` 的一个事件类型, 受 50-ID dedup 保护）; (d) **可选每日上限**（父母端配置, 默认关）—— 达上限后剩余 chore 仍可完成但不结算金币, 显示"明天再来挑战"的 sleeping-cat 灰态。
**Axis:** Daily quest progression
**Basis:** `direct:` `ChildTasksPage.vue` 当前是 `v-for` 平铺 + dim-on-done, 无终态。`ChildChallenge` schema (`target_type/current_progress/deadline`) 已是关卡形态。`useCelebration` 50-ID dedup 已就绪, 添加事件类型零迁移成本。
**Rationale:** 5-7 岁前运算阶段需要"事情完成了"的封闭形状信号。今天的页面只是变灰（缺位提示）, 不是出现提示（在位提示）。一个"今日通关"事件让大脑把胜利存档, 这是延迟满足的神经基础（要看到今天的赢, 才能为明天储蓄意志力）。可选上限解决"下午 5 点疯狂刷家务套现"的副作用, 训练 pacing 而非 acquisitiveness。
**Downsides:** 圆环组件 + `MilestoneCelebration` 变体 + 父母端上限配置 = 3 处新工作。可选上限默认关, 但需要父母端 UI 支持。"今日通关"事件需要受 `useReducedMotion` 闸控。
**Confidence:** 92%
**Complexity:** Medium
**Status:** Unexplored

---

### 10. 心愿星座图 (Wish Constellation Canvas with Traffic-Light Tint)
**Description:** 在 `ChildWishesPage.vue` 顶部新增一个跨心愿快照, 由两个可复用 primitive 组成: (a) **`reachabilityTint(balance, priority_simulation, wishId) → 'green'|'yellow'|'red'`** 纯函数 —— 绿 = 当前余额可兑, 黄 = 估算 ≤ 7 天达成, 红 = >7 天; (b) **`<WishConstellationGrid>`** 组件 —— 3 列照片网格, 每张心愿照片以 `tint` 决定的颜色光环包裹, 点击展开下方原有的状态分组卡片。顶部一行文案"你今天可以拿到 K 个 / 共 N 个 心愿"（用绿色心愿数, 不用百分比）。同一个 `tint` 函数也用于 home 页 hero 条、abandon-sheet 多心愿延迟提示、父母 dashboard 镜像。
**Axis:** Cross-wish reachability viz
**Basis:** `direct:` `ChildWishStats.priority_simulation[]` 已返回 `{star_coin_cost, progress, covered, shortfall_for_high_priority}` per wish —— UI 零、数据齐。`external:` GoHenry/Greenlight/RoosterMoney 全部 silo 各心愿（grounding 确认这是未占领空间）；色盲友好的红/黄/绿对 5-7 岁是预读知识。
**Rationale:** 5-8 岁无法心算"这个 67% / 320⭐ 对比那个 31% / 800⭐"。颜色边框是预数字的语义, 红绿灯每个孩子都懂。把"我现在能买什么"从隐藏推理变成一眼可见, 这是 Kidd 2013 信任机制的核心: 系统对自己透明 → 等待感觉理性。复用同一 tint 函数到多处, 单点维护多点收益。
**Downsides:** 父母仍可通过 `expected_price` 字段感知现实价值的不透明保留要求 —— `tint` 必须只读 `star_coin_cost`/`progress`, 不读价格。需要新增 i18n 键 `wishes.affordable.{green,yellow,red}` + `wishes.reachableCount`。"≤7 天" 黄色阈值需家庭可调（默认 7）。
**Confidence:** 95%
**Complexity:** Low-Medium
**Status:** Explored (selected for /ce-brainstorm 2026-05-24 — cross-wish bundle with #11, #12)

---

### 11. 决策望远镜 (Trade Telescope — Pre-Spend Delta Simulator)
**Description:** 一个纯客户端函数 `previewSpend(wishId, balance, priority_simulation) → { deltas: [{wish_id, before_progress, after_progress, days_added}], unlocks_now: [], locks_out: [] }`, 无 I/O, 5 处集成: (a) **兑换确认 sheet** —— 长按或 tap "redeem" 拦截一次, 显示其它心愿的 before→after progress 条 + "+N 天"标签, 配 600ms 动画延迟让孩子把兑换决定和后果在视觉上配对一次, 然后"我懂了"按钮才出现; (b) **abandon-task hint** —— 现有 `abandonWishHint` 升级成多心愿 delta; (c) **父母审批队列** —— 父母看到同样的 delta（"批准这次兑换会让 高优先级心愿延迟 7 天"）; (d) **What-if toy mode** —— 心愿网格里点击但不长按 → 1.5 秒幽灵预演 → 自动复位（不提交）; (e) **新孩子引导** —— 用合成数据演示 trade-off 的概念。
**Axis:** Trade-off / opportunity-cost surface
**Basis:** `direct:` 现有 `priority_simulation[]` 加客户端余额已足够, 零后端工作。当前兑换是 silent confirm（`ChildWishesPage.vue` redeem 行为）, 不存在 trade-off 提示面。`reasoned:` 机会成本对儿童（和大多数成人）不可推理, 必须空间化渲染。语言解释（"如果你买这个, 那个就要再等"）几秒后忘, 但其它心愿条**实时缩短**的画面是粘性的。
**Rationale:** Mischel/Kidd 2013 修正: 延迟满足训练的核心机制不是意志力, 而是让原因-结果对孩子可见。"消费现在 = 推迟未来"是这款产品声称要教的财务素养第一概念, 但当前 UI 在哪都不展示。同一函数 5 处复用, 是教育时刻倍增器。
**Downsides:** 600ms 强制延迟在儿童组可能感觉慢, 需 A/B 调整（200-800ms 区间）。`useReducedMotion` 命中时降级为静态 before/after 数字。父母端复用增加 admin UI 工作量但绑定父母信任（同一公平视图）。
**Confidence:** 88%
**Complexity:** Medium
**Status:** Explored (selected for /ce-brainstorm 2026-05-24 — cross-wish bundle with #10, #12)

---

### 12. 时光定价 (Time-Denominated Wish Prices — "≈ 12 个晴天")
**Description:** 心愿卡片在原有"还需 280⭐"旁边增加一个二级读数 `≈ 12 个晴天` / `≈ 4 个连击` —— 由现有 7-14 天滚动收入均值除以 `star_coin_cost - balance` 计算（与 `ChildWishesPage.vue` 已有的 "再做约 X 天家务" 逻辑同源, 仅扩展单位）。孩子偷懒时数字**实时变长**（昨天 12 → 今天 14）, 冲刺时变短（12 → 9）, 让懒惰可见, 让努力可感。"晴天 / 连击 / 周末" 单位由家庭设置选, 默认"天"。
**Axis:** Trade-off / opportunity-cost surface
**Basis:** `reasoned:` 5-7 岁孩子流利地用"睡几觉到生日 / 几天到周末"推理时间, 远比三位数算术早。`direct:` 现有"再做约 X 天家务"逻辑（`ChildWishesPage.vue`）已经做了天数估算, 此为单位扩展。
**Rationale:** 一个 6 岁的孩子不能心算 280-145, 但**绝对**理解"再过 9 天"。把 `star_coin_cost` 翻译成时间单位, 让心愿追求与算术能力解耦, 同时让 pacing 具象化: 偷懒时心愿物理上变远, 这比一个停滞的进度条更可读。也是对"系统在帮我看到努力"的信任信号。
**Downsides:** 7 天均值在初期（< 3 个赚取日）不稳定, 需"再做几天才能精确估算"的占位文案。家庭单位选择需父母端 UI。如果父母大幅调整 `star_coin_cost`, 时间数字会跳变 —— 这违背"不移动球门柱"原则, 需父母端调价时弹出"会让孩子的预估时间从 12 天变 25 天"警告（与 idea #11 共用 `previewSpend` 思路）。
**Confidence:** 86%
**Complexity:** Low
**Status:** Explored (selected for /ce-brainstorm 2026-05-24 — cross-wish bundle with #10, #11)

---

### 13. 时光信件 (Future-Me Promise Letter)
**Description:** 当孩子标星一个新心愿（创建/激活）时, 弹出一个 30 秒小向导用 emoji + 录音 + 贴纸记录"我为什么想要这个 / 我得到时会怎么开心" —— 30 秒上限, 一次完成, 锁到该心愿。在 25/50/75% 进度里程碑触发时, 信件作为 "Future-Me 说:" overlay 短暂呈现（复用 `MilestoneCelebration`）。100% 兑换庆典时信件作为内嵌音/图回放。父母端不可见信件内容（避免变成审查工具）, 仅可见信件存在与否的指示器。
**Axis:** Pacing & loss aversion
**Basis:** `external:` Kidd 2013 棉花糖修正研究: **承诺者的可信度**是延迟满足的真正变量, 不是意志力。让孩子同时是承诺者和接收者, 把信任路径内化, 系统只是见证者。
**Rationale:** 大多数 chore app 优化"多少"但从不捕捉"为什么"。"为什么"是支撑度过艰难一周的情感燃料。半路想放弃时, 父母最常听到的孩子台词是"我忘了为什么想要"或"我现在不那么想要了" —— 信件为这两种放弃精确兜底。也是对延迟满足训练的 reframe: 从"等待系统"到"信守过去自己的承诺"。
**Downsides:** 录音功能需要麦克风权限, iOS Safari 在 PWA 场景下有限制, 需要降级到纯 emoji + 贴纸方案。30 秒上限的强制简化对 7-10 岁可能太短。父母端可见与否要清晰文案保护（避免父母看不到 → 误解 → 不信任系统）。
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

---

### 14. 护身符代币 (Streak Freeze Token — Inventory Item)
**Description:** 把"连击宽限"从隐式逻辑提升为一个**一等可拥有物品** `streak_freeze_token`, 与 我的宝贝 (#5) 在同一 inventory 容器里展示。获取: 每完成 7 天连击自动入库 1 枚 / 父母手动赠予 1 枚 / 兄弟姐妹通过现有 #7 赠送通道转赠。消耗: 漏一天时**自动**消费 1 枚, 连击数字**永远不显示零**, 仅显示 ❄️ 雪花替代图标。库存为 0 时漏一天 → 连击重置为 1, 但 `MilestoneCelebration` 不展示"你失去了"的损失文案, 而是"新一周开始啦, 你的护身符还有 0 枚"的中性叙事。
**Axis:** Pacing & loss aversion
**Basis:** `direct:` 我的宝贝 inventory 容器（#5）+ 父母赠予 chain（#2 的 ApprovalQueue）+ 兄弟姐妹赠送 rail（#7）三条 rail 都已存在, 添加新物品类型几乎零容器工作。`external:` Duolingo streak freeze 范式（grounding 引用: "永不展示零, 用 1 日宽限"）。
**Rationale:** 当前 #4 的连击是数字 + 倍率加成, 缺的是**漏一天怎么办**。让护身符可见可拥有, 漏掉时孩子看到"消耗了一枚护身符", 这是**Object 优于 Feature**的设计原则: 一个可拥有的东西自带情感和库存焦虑, 比一个隐式 freeze 标志强 10 倍。也让"努力 7 天 = 多一枚护身符"的复利更直观。同时是 inventory 容器的第一个非心愿/资产物品, 为未来盲盒拉票、家庭店铺等扩展铺路。
**Downsides:** 连击 schema 需要小改（区分 reset-to-zero 和 freeze-consumed 两种状态）。父母赠予逻辑需要新流。"库存为 0 漏一天"的中性叙事文案对孩子的接受度需要测试。
**Confidence:** 85%
**Complexity:** Low (复用 inventory 容器) — Medium (后端 schema 微调)
**Status:** Unexplored

---

### 15. 自由探险任务 + 候鸟审批 (Free-Play Side-Quest + Visible Approval ETA)
**Description:** 两个互补 primitive 解决"卡死"状态: (a) **`kind: 'side'` discriminator** 加到现有 `ChildChallenge` schema, 让父母可挂可选副任务（"今天给奶奶画一幅画"、"帮忙搬购物袋"）—— **永不算入今日关卡 (#9)**, 不影响 day_complete, 完成给独立小奖（不挤占主路径）。当 `ChildTasksPage` 在某天出现"主任务全部 pending_approval / 全部完成 / 父母没派任务"三种"卡死"形态时, 自动展示"今天的探险队 ⛺"模块（≤2 个 side quest, 永远存在 fallback 的"今天画一幅画" 默认 quest）; (b) **CandleFlame 倒计时弧** —— 在现有的 pending-approval 蜡烛外包一圈薄 SVG 弧, 反向消耗到自动批准 deadline（24h 默认, 与 #2 的 timeout 同源）, 最后 1h 弧线轻微呼吸, 配 i18n 文案"审批中, 你还可以做这些 ↓"高亮非 pending 任务。
**Axis:** Stuck & escape-valve states
**Basis:** `direct:` `ChildChallenge` schema 已有 `target_type/target_value/current_progress/deadline`, 添加 discriminator 是字段扩展。`CandleFlame` 已存在但仅为 binary 闪烁, 缺时间维度。`pollForApproval` 已每 5s 轮询 10min 但孩子看不到倒计时。`external:` ABCmouse 研究: 线性强制流必须配并行自由玩耍出口（grounding 确认）, 否则卡死会被孩子归因为"系统坏了"。
**Rationale:** 当前空任务日 / 全 pending 日 / 父母遗忘日 = 死页, 给孩子"系统坏了"的潜信号, 也诱导父母用低质任务喂内容。两个 primitive 把卡死变成 feature: side quest 提供有意义的轻微选择, ETA 弧把无尽等待变成有界等待 —— 后者本身就是 24h 尺度的延迟满足训练。
**Downsides:** side quest 需要"什么算 quest"的设计边界（避免父母滥用为隐性家务派发）。ETA 弧 + 现有 candle 动画需要 motion 预算审计, 防止移动端低端机卡顿。fallback 默认 quest 内容需要内置文化中性的 5-10 个备选（避免重复）。
**Confidence:** 82%
**Complexity:** Medium
**Status:** Unexplored

---



| # | Idea | Reason Rejected |
|---|------|-----------------|
| 2 | No Separate Child UI — Filtered View | 成人财务 UI 对6岁孩子是敌对体验；条件渲染无法解决根本的认知负荷问题 |
| 11 | StarCoin Exchange Rate Board | 直接破坏 Idea #3 的不透明积分设计；汇率是5-8岁无法理解的抽象概念 |
| 14 | Coin Ledger with Story-Based History | 故事生成是展示层优化，已被 Idea #2 的故事化账本吸收；不是独立产品想法 |
| 16 | Family Coin Economy Dashboard | 已合并入 Idea #6 的父母视角；"通货膨胀指标"对家庭积分系统是过度设计 |
| 17 | The Broken Promise Ledger | 命名有害（暗示父母违约）；核心功能已被 Idea #3 的储蓄罐进度条覆盖 |
| 18 | Chore Marketplace with Variable Pricing | 为5岁孩子设计的劳动力市场竞价系统；教的是套利而非责任感 |
| 19 | Coin Decay and Piggy Bank Interest Rate | 积分衰减惩罚不活跃用户（如度假）；需要后台调度器；对目标年龄段是敌对设计 |
| 21/38 | Sibling Coin Gifting (duplicate) | 已保留为 Idea #7；此处为重复条目 |
| 24 | Wish Voting: Family Democracy | 孩子赚够积分后家庭投票否决心愿会摧毁对系统的信任；父母在心愿创建时已有控制权 |
| 27 | Chore Template Library with Adaptive Coin Pricing | 基于完成率自动降低家务价值会惩罚一致性——恰恰是要奖励的行为 |
| 29/40 | Coin Splitting: Save/Spend/Share Buckets | 50/30/20 是成人预算框架；对5岁孩子的认知负荷是破坏性的；需要调度器计算利息 |
| 31 | Family Economy Simulation | 央行、家庭债券、股市模拟——这是经济学博士的想象，不是儿童功能 |
| 32 | Streaks with Retroactive Discovery | 回溯模式检测对已经继续前进的孩子毫无意义；实时反馈才有效 |
| 33 | Auto-Verify Chore via Photo + Timer | 移除父母认可环节；5岁孩子会拍墙壁然后自动获批 |
| 34 | Negotiation Mode | 教孩子与父母谈判家务价格会制造家庭冲突，不是财务素养 |
| 37 | Parent-Invisible Child Dashboard (as separate idea) | 已合并入 Idea #1（儿童身份系统）的 /child/* 路由树；不是独立想法 |
| 39 | Smart Chore Scheduling: Fairness Algorithm | 算法不知道5岁孩子不能倒垃圾；移除儿童选择权，把系统变成任务管理器 |
| 6 | Parent as Central Bank (standalone) | 已合并入 Idea #6 的父母视角（积分倍率调节） |
| 7/25 | Coin Ledger (duplicate) | 已合并入 Idea #2 的故事化账本；两个条目描述同一基础设施 |
| 8 | Child Account Without Password — QR Login | QR 需要两台设备；已被 Idea #1 的表情符号 PIN 覆盖 |
| 10/30 | Photo Proof (duplicate) | 两个条目描述同一功能；可作为 Idea #2 的可选扩展，不是独立想法 |
| 13 | My Stuff Museum with Wear Tracking | 磨损追踪是成人资产管理概念；已合并入 Idea #5，去掉磨损部分 |
| 22 | Visual Coin Jar with Physics Animation | 物理引擎对移动端低端设备性能有风险；CSS fill 动画（Idea #3）达到90%效果，成本10% |
| 23 | PIN Login with Emoji Keypad (standalone) | 已合并入 Idea #1（儿童身份系统） |
| 26 | Wish-to-Asset Pipeline (standalone) | 已合并入 Idea #3（心愿兑现流水线） |
| 28 | Parent-Child Paired Dashboard (standalone) | 已合并入 Idea #6（亲子双视角仪表盘） |
| 35 | Streak Engine with Compound Interest | 已合并入 Idea #4（连续打卡）；复利加成是实现细节，不是独立想法 |
| 36 | Wish Fulfillment Autopilot (standalone) | 已合并入 Idea #3（心愿兑现流水线）的触发通知部分 |

### Round 2 Rejections (2026-05-24)

| # | Idea | Reason Rejected |
|---|------|-----------------|
| R2-01 | 时段关卡分章 (morning/afternoon/evening chapters) | 与 Idea #9 的"今日关卡环"功能重叠且更复杂；需要后端 `time_of_day` 字段；3 章 × 2 任务的硬切分对单任务日不友好 |
| R2-02 | 心愿排队挂表 (single shared 0→100% rail with all jars) | 与 Idea #10 的星座网格描述同一跨心愿 viz；连续轨道 vs 离散网格中, 网格的红/黄/绿语义对 5-7 岁更可读 |
| R2-03 | 儿童自预言任务 (bedtime self-prophecy) | 与现有 #2 父母派发模型直接冲突；自预言准确率作为元指标对儿童元认知要求过高（5-7 岁尚未发展）；可作 #2 的可选层在更年长用户中重新评估 |
| R2-04 | 默认完成清单 (Default-Complete Checklist) | "默认完成 + 主动招认未做"违反 Kidd 2013 信任契约（系统说谎）；孩子习得"沉默 = 通过"是错误的诚信训练；父母端审计成本高 |
| R2-05 | 自动汇流单一管道 (single-pipe auto-routing to top wish) | 削弱孩子对 #3 储蓄罐的代理感, 训练的是"被动接收"而非"主动选择"；移除了机会成本的可见时刻（一切都自动了） |
| R2-06 | 隐藏连击数字 (Hidden Streak Count) | 直接撤销 #4 的可见连击和 streak badge；孩子无法把日常行为和未来庆典连接, 因果链断裂；与 Idea #14 护身符代币（让计数继续可见但永不归零）方案更优 |
| R2-07 | 反向迷雾 (Reverse Fog over un-chosen wishes) | 与 #10 星座图的红/黄/绿 tint 解决同一感知问题；雾化语义对 5 岁是"消失" = 失去, 不及红绿灯传统语义清晰 |
| R2-08 | 休息关 / Rest-Day Reframe | 与 Idea #15 的 "side quest 模块在卡死状态自动出现" 同效；独立 "休息关"会与 #9 的 day_complete 终态产生终态冲突（哪个庆典先放？） |
| R2-09 | 跨心愿地平线 / 水位上升模型 | 与 #10 同义；水位金属隐喻 vs 红绿灯, 后者跨文化、跨年龄更普世；研究指出"水位"对 5-6 岁的物理直觉不稳定 |
| R2-10 | 任务银行 / 周末爆发关 (deferred-tasks weekend burst) | "今天的活推到周末"违反"做完即结算"的可信反馈环；x1.2 倍数复利对儿童不可推理；需要 deadline 调度 |
| R2-11 | Wish Sticker Album (gold/silver/bronze KPI flip) | 概念好但与 #10 星座图重叠；KPI 从 "balance" 翻转到 "claimable count" 是有价值的子论点, 已在 #10 的"K of N"文案中吸收 |
| R2-12 | Constellation Allocation Board (route at earn-time) | 复杂度过高（每完成任务都要选去向）, 与 5-7 岁工作记忆容量冲突；与 #11 决策望远镜（spend-time 而非 earn-time）的认知负荷曲线相反, 望远镜更轻 |
| R2-13 | Weekly Energy Budget (7-day battery instead of streak) | 与现有 #4 连击的日级反馈循环冲突；周级抽象对 5-7 岁过远；和 Idea #14 护身符的"漏一天有兜底"目标重叠但更激进 |
| R2-14 | Translucent Opportunity-Cost Preview at spend time | 与 Idea #11 决策望远镜本质相同；已并入 #11 |
| R2-15 | Spending-as-Victory Card (verb flip) | "兑换是胜利"概念好但与现有 #5 我的宝贝、Idea #13 时光信件回放重叠；增加 Victory Card gallery 是第三个相册容器, 维护成本过高 |
| R2-16 | DaySegment / Strava-style Day Records | 数据聚合层重构, 不是产品想法；可作 Idea #9 落地后的内部 refactor, 不是独立 ideation 出口 |
| R2-17 | Story Beat Stamp (typed event from narrative) | 数据层 typing 重构, 与 Idea #9 落地后会自然发生；不需要独立 idea 槽 |
| R2-18 | 蜂巢心愿板 / Honeycomb Wish Board | 视觉变体, 与 #10 星座图同效；蜂巢的"采蜜"语义需新插画工作；红/黄/绿光环已是足够的可达性信号 |
| R2-19 | 闸门运河 / Lock-and-Dam Canal Streaks | 漂亮的"水永不倒流"隐喻但 = #14 护身符的"永不归零"语义包装；需要全新水位 SVG 资源；与 #14 选其一 |
| R2-20 | 今夜星空 / Tonight's Constellation day-cleared ritual | 与 #9 的"今日通关"庆典同效；"星座命名"需要图形资源 + 文案集；增量价值不抵成本 |
| R2-21 | 心愿地铁图 / Wish Subway Transfer Map | 与 #11 决策望远镜的"多心愿 delta"同效；地铁线路图视觉对国际化用户的文化普适性较窄 |
| R2-22 | 面包发酵中 / Sourdough Proofing 空日 reframe | 与 #15 side-quest 同效；"面团发酵"对 5 岁孩子要解释比"今天的探险队"门槛高 |
| R2-23 | 草药保鲜罐 / Apothecary's Perishable Herbs | 引入"过期 = 失去 bonus"机制, 即使被限制在 bonus 层也违反"永不让孩子感觉失去"原则；3 天 shelf life 对 5-7 岁仍是过长的预测窗口 |
| R2-24 | 灯塔与帆船 / Lighthouse & Sailboat | 与 #10 星座图（多心愿）的设计哲学相反（单顶心愿独占 home）；现有 home 的 top-wish preview 已部分实现该意图 |
| R2-25 | 调车场货运列车 / Freight Train Marshalling | 与 #5 自动汇流（已被 R2-05 拒绝）相似；"开关切换"的视觉对低端机性能压力大 |
| R2-26 | The Single Evolving Wish (1-at-a-time hard limit) | 强制单心愿剥夺孩子的多元目标体验, 与现有产品心愿创建流冲突；与 #10 跨心愿 viz 的产品方向相反 |
| R2-27 | Stake-Your-Streak Wager (loss bet) | 让儿童在金钱性资源上下注, 即使是星币, 引入赌博模式启蒙；与 Numina"延迟满足训练"目标根本冲突；作者本身在 meeting test 中已自我标记为不安全 |
| R2-28 | Sympathy Coin on Miss (parent-only failure currency) | 让"失败"产生货币是把失败正向化的可疑机制；父母端"sympathy coin 解锁宽限"不如 Idea #14 护身符直接（同样的兜底, 没有"失败 = 赚币"的混淆信号） |
| R2-29 | Sibling-Only Visibility / Hidden-Self Mode | 让孩子看不到自己的进度违反"系统对自己透明"的 Kidd 2013 信任原则；多孩家庭 minority feature, 维护负担与受众不匹配 |
| R2-30 | Seasonal Quest / No-Today Mode | 移除"今天"的概念与现有日审批节奏冲突；4-8 周路径地图对 5-7 岁过长的时间感知 |
| R2-31 | Tamagotchi Wish (wilts when neglected) | 模拟"心愿死亡"是儿童产品的损失厌恶反模式；即使可选, "心愿生病"画面会让孩子焦虑或负罪 |

---

## Session Log
- 2026-04-14: Initial ideation — 40 raw candidates generated across 5 frames (pain/friction, unmet needs, inversion/automation, assumption-breaking, leverage/compounding), 2 adversarial critique passes (engineering + child UX), 3 cross-cutting combinations synthesized, 7 survivors ranked
- 2026-04-14: Added Idea #8 — 金银铜星星币视觉体系 (user-proposed: tiered coin SVG design with configurable exchange ratios and copper-to-currency peg)
- 2026-05-24: Round 2 extension — focus on "task-as-daily-game-level" + cross-wish affordability viz for delayed-gratification training. 48 raw candidates across 6 frames (pain, inversion/removal, assumption-breaking, leverage, cross-domain analogy, constraint-flipping) over 5 explicit axes (daily quest / reachability viz / trade-off / pacing / stuck-states). After dedupe + adversarial filtering: 7 new survivors (#9-#15) added, 31 rejected (R2-01..R2-31). Existing 8 survivors preserved with their `Status: Unexplored` markers untouched. Round 2 leverages newly-landed celebration components (CandleFlame, FlyToTarget, LandingBurst, StreakLayer, TrailResidue) and the `ChildWishStats.priority_simulation[]` server-side affordability data that has no UI yet.
- 2026-05-24: Ideas #10 + #11 + #12 selected for the cross-wish bundle. Brainstorm at `docs/brainstorms/2026-05-24-child-cross-wish-bundle-requirements.md`. Plan at `docs/plans/2026-05-24-002-feat-child-cross-wish-bundle-plan.md`. v1 ship cut completed across U1-U9 on branch `feat/child-game-opt`.
