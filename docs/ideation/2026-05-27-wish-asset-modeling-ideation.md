# Wish 模型资产化 — Ideation 记录

**日期:** 2026-05-27  
**聚焦问题:** 当前儿童心愿实现，是否缺少了实现时间？购入时间？资产关联？能否从大人视角把心愿也资产化？  
**方法:** Compound Engineering ce-ideate（6 框架并行发散 → 对抗性过滤）  
**原始候选:** 48 条  
**最终幸存:** 7 条

---

## 幸存 Ideas（按可信度排序）

### #1 fulfilled_at + purchase_date 原子回写（95%，工作量：低）

**核心:** 在 `realize_wish()` 的原子事务内补写 `Wish.fulfilled_at = now()`；若用户传入了实际购买日期，也同步到 `Asset.purchase_date`。  
**解决的问题:** 心愿详情页无法显示"何时实现"；父母侧时间线也缺少这个锚点。  
**实施路径:**
1. Alembic migration：`wishes` 表新增 `fulfilled_at TIMESTAMP NULL`
2. `wish_service.realize_wish()` 结尾：`wish.fulfilled_at = datetime.now(timezone.utc)`（Python 3.12 已弃用 `utcnow()`，使用 aware datetime）
3. `WishResponse` schema 新增 `fulfilled_at: datetime | None`
4. `WishDetailPage.vue` 展示"实现于 YYYY-MM-DD"

---

### #2 Asset.from_wish_id 反向引用 + 索引（92%，工作量：低-中）

**核心:** 在 `assets` 表新增可空 FK `from_wish_id -> wishes.id`，加复合索引 `(family_id, from_wish_id)`，实现双向导航：心愿 → 资产 / 资产 → 心愿来源。  
**解决的问题:** 现有 `Wish.realized_asset_id` 只能单向查；Asset 侧无法反溯"这件东西来自哪个心愿"。  
**实施路径:**
1. Alembic migration：`assets.from_wish_id` nullable FK + 索引（**必须先于服务代码变更部署**；`realize_wish()` 事务内访问 `asset.from_wish_id` 若列不存在会抛 `AttributeError` 导致整个事务回滚）
2. `realize_wish()` 同步写 `asset.from_wish_id = wish.id`
3. `AssetResponse` 新增 `from_wish_id: str | None`（SnowflakeBase 序列化 ID 为字符串，符合 CLAUDE.md bigint 规则）
4. 资产详情页展示"来自心愿：{name}"入口

---

### #3 儿童端 realized_asset_id 透出 + 跳转（90%，工作量：低-中）

**核心:** 儿童端 `ChildWish` API 已有 `realized_asset_id`；在儿童端心愿详情页加一个跳转入口，让孩子能看到"愿望实现了！点击查看"。  
**解决的问题:** 当前儿童端只有 ✅ 图标，无法感受到愿望与现实物品的连接感。  
**实施路径:**
1. 确认子端路由策略（见 Open Questions #OQ-1）：子端 SPA 无 `/assets` 路由，直接写 `router-link :to="/assets/..."` 会被 catch-all 静默重定向至首页。需先选定方案再实施。
2. 候选方案：(a) 子端新增 `/assets/:id` 详情页；(b) 跳转到现有 `/treasures`；(c) `window.location.href` 跨 SPA 跳转到主应用。
3. 方案确定后，在 `ChildWishDetailPage.vue` 对应位置加跳转入口。

> ⚠️ **注意：** 本条目已与原 #7（父端热修补）分离。父端 `WishDetailPage.vue:53` 的修复见下方 #7（已合并保留）。

---

### #4 心愿 = 大人承诺负债（88%，工作量：中）

**核心:** 将已审批、未实现的心愿建模为家庭资产负债表里的"或有负债"（承诺负债科目），赋予金额 = `expected_price`。父母在仪表盘可看到"承诺负债总额"。  
**解决的问题:** 直接回答"大人视角把心愿资产化"——不只是实现后变资产，实现前也在账里占位置。  
**实施路径:**
1. 新增 `wish_commitments` 聚合视图 or 在 Dashboard API 增加 `committed_wishes_total`
2. 过滤条件：`status='pending'` 且 `converts_to_asset=true`（注：当前 Wish status 枚举为 `pending/realized/cancelled`，不含 `approved`；若未来新增 `approved` 状态，届时扩展过滤条件）
3. 仪表盘新卡片"未兑现承诺 ¥XXX"
4. 点击进入心愿列表（父母侧）

---

### #5 Wish 生命周期事件进 Activity 表（85%，工作量：低-中）

**核心:** 在 `wishes` 的三个关键节点（创建/实现/取消）向现有 `activities` 表写入事件，`entity_type='wish'`，`entity_id=wish.id`。  
**解决的问题:** 现有 Activity 表记录金币收支，但心愿事件（"今天我的心愿实现了"）没有记录，AI 顾问和时间线报告因此盲区。  
**实施路径:**
1. `wish_service.create_wish()` 末尾 insert activity（type=`wish_created`）
2. `wish_service.realize_wish()` 末尾 insert activity（type=`wish_realized`, amount=`expected_price`）
3. 时间线页面渲染 `wish_*` 类型事件

---

### #6 已实现心愿 = 承诺档案（82%，工作量：中）

**核心:** 新增 `Wish.fulfillment_note` 字段（文本），保留已实现心愿作为"承诺档案"，支持周年纪念提醒（scheduler_worker 每年触发）。  
**解决的问题:** 实现后的心愿目前等同于死档；加入故事性使家庭记忆可回溯。  
**实施路径:**
1. Alembic migration：`wishes.fulfillment_note TEXT NULL`
2. `WishRealizeRequest` 增加可选 `fulfillment_note: str | None`
3. `realize_wish()` 写入 note
4. Scheduler worker 年度任务查 `fulfilled_at` 月日 → 推送通知

---

### #7 WishDetailPage 跳转链接热修补（父端）（80%，工作量：极低）

**核心:** `WishDetailPage.vue:53`（父端主应用）现有静态 `<div v-if="wish.realized_asset_id">{{ t('wish.realizedAsset') }}</div>`，改为可点击的 `<router-link>`，一行修复。  
**解决的问题:** 父母在心愿详情看到"已转为资产"字样但无法导航，用户体验断链。  
**说明:** 本条目仅覆盖父端主应用（`frontend/apps/main`）的 `WishDetailPage.vue`。子端跳转见 #3（需先解决路由问题）。  
**实施路径:**
```vue
<!-- Before -->
<div v-if="wish.realized_asset_id" class="hero-realized-info">{{ t('wish.realizedAsset') }}</div>
<!-- After -->
<router-link v-if="wish.realized_asset_id" :to="`/assets/${wish.realized_asset_id}`" class="hero-realized-info">
  {{ t('wish.realizedAsset') }} →
</router-link>
```

---

## 推荐实施顺序

| 优先级 | Idea | 理由 |
|--------|------|------|
| P0 | #7 热修补 | 一行，零风险，立即消除断链 |
| P0 | #1 fulfilled_at | 原子写，migration + 3 行代码 |
| P1 | #2 from_wish_id | 补全双向导航，配合 #3 |
| P1 | #3 儿童端跳转 | 提升孩子成就感，低工作量 |
| P2 | #5 Activity 记录 | 解锁 AI 顾问 + 时间线 |
| P3 | #4 承诺负债 | 需要仪表盘 UI，工作量较大 |
| P3 | #6 承诺档案 | 情感价值高但非核心路径 |

---

## 关键技术约束备忘

- `Wish.realized_asset_id` 已存在（单向）→ `Asset.from_wish_id` 是补全反向
- `realize_wish()` 已是原子事务 → fulfilled_at 只需在事务末尾加一行
- `SnowflakeBase` 自动序列化 ID 为字符串 → 新增 FK 字段无需手动 str()
- `redirect_slashes=False` → 新路由端点用 `""` 不用 `"/"`

---

## 待决问题（Open Questions）

**#OQ-1 儿童端跳转路由策略（阻塞 #3 实施）**  
子端 SPA 无 `/assets/:id` 路由，`router-link :to="/assets/..."` 会被 catch-all 静默重定向到首页。实施 #3 前需三选一：(a) 子端新增资产详情页；(b) 跳转至现有 `/treasures`；(c) `window.location.href` 跨 SPA 跳转主应用。  
*来源：ce-feasibility-reviewer（P0）*

**#OQ-2 Activity 表 entity_type 扩展策略（阻塞 #5 实施）**  
当前 `entity_type` 注释为 `asset/liability`。插入 `entity_type='wish'` 前需决定：(a) 正式扩展合法值域（更新注释 + 若有 CHECK 约束则加 migration + 修改所有读取 Activity 的查询以处理 `wish` 类型）；或 (b) 单独建 `wish_events` 表。若选 (a) 且跳过查询更新，时间线和 AI 顾问将静默排除心愿事件，#5 的核心价值落空。  
*来源：ce-scope-guardian-reviewer + ce-feasibility-reviewer + ce-adversarial（P1）*

**#OQ-3 #4 承诺负债的用户体验框架**  
将未兑现心愿展示为"或有负债"是会计思维，目标用户（家长）可能更接受"承诺清单"语义。同时 `expected_price` 由子女填写，无上限约束，会直接影响仪表盘数字。建议实施前确认：(a) 父母是否需要财务负债框架，还是数量+总额的承诺列表就足够；(b) 是否为 `expected_price` 设置父母确认或金额上限。  
*来源：ce-product-lens-reviewer（P2）*

**#OQ-4 #1 子端是否暴露 fulfilled_at**  
`WishResponse`（父端）新增 `fulfilled_at` 后，`ChildWishResponse`（子端）和子端服务查询是否同步更新？子端心愿详情页目前显示静态"已实现 ✅"标签，若期望展示"实现于 YYYY-MM-DD"，需纳入同一 PR 范围。  
*来源：ce-feasibility-reviewer（P2）*

**#OQ-5 #6 周年纪念推送的基础设施依赖**  
`scheduler_worker` 当前无推送通知分发机制（无 APNs/FCM client，无 notification model）。步骤 4"推送通知"实际是独立的基础设施项目，建议将 #6 拆为两个独立条目：(a) `fulfillment_note` 字段存储 + 详情页展示（独立价值，低工作量）；(b) 周年纪念推送（前置依赖：推送通知基础设施）。  
*来源：ce-scope-guardian-reviewer + ce-adversarial + ce-product-lens（P2）*
