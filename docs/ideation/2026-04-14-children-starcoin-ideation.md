---
date: 2026-04-14
topic: children-starcoin-gamification
focus: 为5-8岁儿童添加星星币积分系统，通过完成家务/学习任务赚取积分，兑换心愿，培养理财概念
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

## Rejection Summary

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

---

## Session Log
- 2026-04-14: Initial ideation — 40 raw candidates generated across 5 frames (pain/friction, unmet needs, inversion/automation, assumption-breaking, leverage/compounding), 2 adversarial critique passes (engineering + child UX), 3 cross-cutting combinations synthesized, 7 survivors ranked
- 2026-04-14: Added Idea #8 — 金银铜星星币视觉体系 (user-proposed: tiered coin SVG design with configurable exchange ratios and copper-to-currency peg)
