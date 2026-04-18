---
date: 2026-04-17
topic: performance-caching
focus: 前端弱网优化 + 后端缓存层设计
---

# Ideation: 性能优化与缓存设计

## Codebase Context

- **Backend:** FastAPI + SQLAlchemy + SQLite（支持 MySQL/PostgreSQL），JWT auth，family-scoped 多租户
- **Frontend:** Vue 3 + TypeScript + Vite + Vant 4（移动端 UI）+ ECharts + Pinia
- **Infrastructure:** Docker Compose + Nginx 反向代理
- **已有缓存基础设施:** `backend/app/services/cache/` 已有 `MemoryCacheBackend` + `CacheFactory`（支持升级到 Redis），但 dashboard 查询未使用
- **已有 Snapshot 基础设施:** `AssetSnapshot` 模型已有 `breakdown` JSON 列（nullable，未使用）
- **主要痛点:**
  - 前端无资源优化（无压缩、无代码分割、无懒加载）
  - Dashboard 每次请求触发 7+ 个独立 API 调用
  - 后端无缓存，所有聚合查询每次都打 DB
  - Nginx 无压缩配置，静态资源无长效缓存头

---

## Ranked Ideas

### 1. 使用已有缓存基础设施缓存 Dashboard 聚合结果
**Description:** `backend/app/services/cache/` 已有 `MemoryCacheBackend`，但 dashboard 查询完全未使用。对 `get_overview`（最重的聚合查询）添加缓存，key: `dashboard:overview:{family_id}`，TTL: 60s，在任何 asset/liability 写操作时失效。
**Rationale:** 缓存基础设施已经存在，不用它是浪费。`get_overview` 对所有资产+负债做全表扫描并在 Python 循环中做汇率转换，是最贵的查询。20 行代码改动。
**Downsides:** 进程内缓存在多 worker 部署下会有一致性问题（但 Numina 默认单 worker，且已有 Redis 升级路径）。
**Confidence:** 95%
**Complexity:** Low
**Status:** Unexplored

---

### 2. Nginx 启用 gzip/brotli + 静态资源长效缓存头
**Description:** Nginx 配置加 `gzip on; gzip_types text/javascript application/json;`。Vite 已输出内容哈希文件名（`/assets/index-[hash].js`），对这些文件设置 `Cache-Control: public, max-age=31536000, immutable`；`index.html` 设置 `no-cache`。
**Rationale:** 基础设施已就绪，Nginx 只是没有利用。3G 网络下 300KB 未压缩 JS vs 90KB gzip 是 3 秒 vs 1 秒的差距。纯配置改动，零代码风险，对所有用户每次访问永久生效。
**Downsides:** 无实质缺点。
**Confidence:** 95%
**Complexity:** Low（约 10 行 Nginx 配置）
**Status:** Unexplored

---

### 3. Dashboard Bundle 端点（7 个请求合并为 1 个）
**Description:** 新增 `GET /api/v1/dashboard/bundle`，在服务端调用现有 service 函数，将 overview、allocation、trend、top-assets、daily-cost、low-usage、investment-returns 合并为一个 JSON 响应返回。
**Rationale:** Dashboard 当前发起 7+ 个独立 API 调用。200ms 延迟的移动网络上，仅往返延迟就达 1.4 秒。合并为一个请求后降至约 220ms。复用现有 service 函数，无业务逻辑改动。
**Downsides:** 新增一个端点；如果只需要部分数据，客户端仍然获取全量。
**Confidence:** 90%
**Complexity:** Medium
**Status:** Unexplored

---

### 4. 前端路由懒加载 + ECharts 代码分割
**Description:** `frontend/src/router/` 中所有页面改为动态 `() => import('./pages/XPage.vue')`。ECharts 仅在访问 Dashboard 时加载。Vite 原生支持，无需额外依赖。
**Rationale:** ECharts 约 700KB（minified）。用户打开 app 查看单个资产时不应该下载图表渲染代码。路由级分割是一次性改动，永久限制初始加载成本，无论后续添加多少功能。
**Downsides:** 首次访问 Dashboard 时有小延迟（图表代码按需加载）。
**Confidence:** 90%
**Complexity:** Low（每个路由一行改动）
**Status:** Unexplored

---

### 5. HTTP 缓存头（稳定端点加 Cache-Control + ETag）
**Description:** 对 `/api/v1/categories`、`/api/v1/family/members`、`/api/v1/family/info` 添加 `Cache-Control: private, max-age=300` 和 `ETag` 头。浏览器发送 `If-None-Match`，未变化时返回 304。
**Rationale:** 系统分类（21 个）启动时 seed 一次，永不变更。家庭成员列表仅在邀请/移除时变化。这些端点每次页面导航都被调用。304 响应在弱网下完全消除 payload 传输。
**Downsides:** 家庭成员变更后最多 5 分钟内其他设备看到旧数据（可接受）。
**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

---

### 6. JWT 中嵌入 family_id 和 role
**Description:** 登录时将 `family_id` 和 `role` 编码进 JWT payload。`get_current_user` 依赖从 token 中读取，不再查 `users` 表。
**Rationale:** 每个认证请求当前都通过 `get_current_user` 做一次 DB 查询来解析 `family_id` 和 `role`。嵌入 JWT 消除每个请求的一次 DB 往返。
**Downsides:** 角色变更在 access token 过期前（15 分钟）不生效。家庭 app 场景可接受。
**Confidence:** 85%
**Complexity:** Medium
**Status:** Unexplored

---

### 7. 系统分类作为编译时常量（消除 DB 查询）
**Description:** 21 个系统分类已在 `backend/app/seed/` 中硬编码，运行时从不变更。将其提取为 Python/TypeScript 常量，消除 DB 查询。
**Rationale:** 把编译时常量存在数据库里是架构假设错误。每次资产表单加载都查询分类表，纯属浪费。
**Downsides:** 系统分类如需变更，需要代码部署而非 DB migration（但自项目创建以来从未变更过）。
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

---

### 8. 资产变更时 Upsert 当日 Snapshot（日内实时更新）
**Description:** `PUT /assets/{id}/value` 时，对今日日期做 `AssetSnapshot` upsert。`breakdown` JSON 列（已存在，nullable）同步更新。日调度器和变更路径写同一行，唯一约束（family_id + snapshot_date）保证正确性。
**Rationale:** 当前趋势图只显示昨日数据，用户更新资产价值后要等到第二天才能在图表上看到变化。Upsert 让趋势图日内实时反映变更，且完全符合现有 schema 设计。
**Downsides:** 每次资产价值更新多一次 DB upsert（开销极小）。
**Confidence:** 80%
**Complexity:** Low
**Status:** Unexplored

---

### 9. Pinia Store sessionStorage 启动缓存（即时渲染）
**Description:** 成功 API 响应后将 overview 数据写入 `sessionStorage`。App 启动时立即从 sessionStorage 渲染，同时后台发起真实 API 请求。显示小型"刷新中"指示器。`sessionStorage` 在 tab 关闭时自动清除，数据不会超过一个会话旧。
**Rationale:** 移动用户频繁关闭重开 app。弱网下空白加载屏是最令人沮丧的体验。sessionStorage 避免了 localStorage 的数据过期复杂性，同时实现即时渲染。
**Downsides:** 需要 UI 指示器避免用户误以为数据是最新的。
**Confidence:** 75%
**Complexity:** Low
**Status:** Unexplored

---

### 10. 乐观 UI（资产增删改立即反映）
**Description:** `useAssetStore` 的 create/update/delete 操作先更新本地 Pinia store，再等待服务端确认。服务端报错时回滚并通知用户。
**Rationale:** 写操作延迟是移动端最直观的 UX 痛点。用户点击"保存"后期望立即看到结果，1-2 秒等待感觉像 bug。Store 已有资产列表，本地变更只是数组操作。
**Downsides:** 服务端拒绝时需要回滚逻辑和用户通知。
**Confidence:** 80%
**Complexity:** Medium
**Status:** Unexplored

---

### 11. Store 级别请求去重（防止并发重复请求）
**Description:** Dashboard store 中，如果 `fetchOverview()` 被调用时上一个请求还在 in-flight，返回同一个 Promise 而不是发起新请求。用 `Map<string, Promise>` 追踪 in-flight 请求。
**Rationale:** `fetchAll()` 已用 `Promise.all` 并发发起 7 个请求。当多个组件独立调用同一个 fetch 时，会产生重复并发请求。前端去重，零后端改动，5 行代码。
**Downsides:** 极少数情况下可能返回略旧的数据（in-flight 期间）。
**Confidence:** 75%
**Complexity:** Low
**Status:** Unexplored

---

### 12. Store 级别 Staleness Guard（避免重复网络请求）
**Description:** Pinia store 中加 `lastFetchedAt` + TTL（如 2 分钟）。如果数据足够新，跳过网络请求。
**Rationale:** 最常见用户流：打开 app → 看 dashboard → 点击资产 → 返回 → 再看 dashboard。最后一步重新拉取所有数据，但什么都没变。弱网下这是 1-3 秒的无谓等待。
**Downsides:** 另一个家庭成员在其他设备更新数据时，当前用户最多 2 分钟内看到旧数据。
**Confidence:** 75%
**Complexity:** Low
**Status:** Unexplored

---

### 13. Service Worker 静态资源缓存（仅 App Shell）
**Description:** 使用 `vite-plugin-pwa` 配置 Service Worker，仅对 JS/CSS/字体/图标使用 `CacheFirst` 策略。不缓存任何 API 响应。重复访问时 app shell 从缓存即时加载。
**Rationale:** SW 静态资源缓存与离线能力无关。预缓存 JS/CSS bundle 意味着重复访问时 app 从缓存即时加载，SW 在后台拉取更新。约 10 行 vite-plugin-pwa 配置。
**Downsides:** SW 更新机制需要正确配置，否则用户可能长期使用旧版本。
**Confidence:** 70%
**Complexity:** Low
**Status:** Unexplored

---

### 14. Nginx 静态资源 Preload Hints
**Description:** Nginx 对初始 HTML 响应添加 `Link: </assets/index.js>; rel=preload; as=script` 头，让浏览器在解析 HTML 时就开始获取主 JS bundle。
**Rationale:** 当前架构有顺序依赖链：加载 HTML → 解析 JS → 启动 Vue → 挂载组件 → 发起 API。Preload hint 在基础设施层打破这个链，无需改动应用代码。3 行 Nginx 配置。
**Downsides:** 效果依赖浏览器实现；对已缓存资源无额外收益。
**Confidence:** 65%
**Complexity:** Low
**Status:** Unexplored

---

### 15. AI 端点独立超时配置（两档超时）
**Description:** `frontend/src/api/index.ts` 请求拦截器中：匹配 `/api/v1/ai/` 的请求设置 120s 超时，其余端点设置 10s。
**Rationale:** AI 报告生成和 WebSocket AI 对话需要更长超时，而数据端点应快速失败以便用户重试。当前全局 15s 超时对两类端点都不合适。5 行代码。
**Downsides:** 无实质缺点。
**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

---

### 16. 利用 AssetSnapshot.breakdown 列缓存分配数据
**Description:** `AssetSnapshot` 模型已有 `breakdown` JSON 列（nullable，未使用）。日调度器写 snapshot 时同步填充 breakdown。`get_allocation` 历史数据从 snapshot 读取，无需重新聚合。
**Rationale:** 该列显然是为此目的设计的，只是从未被填充。利用现有 schema，不增加新表，不改变架构。
**Downsides:** 当日 breakdown 仍需实时计算（直到当日 snapshot 写入）。
**Confidence:** 70%
**Complexity:** Low
**Status:** Unexplored

---

## Session Log
- 2026-04-17: 初始 ideation — 4 个并行 agent 生成约 32 个候选，首轮过滤保留 8 个，用户反馈过于激进，重新评估后所有 11 个被拒绝想法均找到可行的 scaled-down 版本，最终 16 个 ideas 全部保留
