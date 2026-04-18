---
date: 2026-04-17
topic: performance-caching
---

# 性能优化与缓存设计

## Problem Frame

Numina 是移动优先的自托管家庭资产管理应用，用户在弱网（3G/4G 不稳定）环境下访问时体验较差：

- Dashboard 每次加载触发 **7 个独立 API 请求**（fetchAll 并发调用：overview、states-summary、home-assets、allocation、trend、low-usage-assets、expiring-soon），在 200ms 延迟网络下仅往返开销就达 1.4 秒
- 后端已有缓存基础设施（`MemoryCacheBackend`）但**完全未用于业务查询**，dashboard 聚合每次都全表扫描
- Nginx 已开启 gzip，但静态资源**缺少长效缓存头**，每次访问都重新下载相同的 JS/CSS bundle
- 稳定端点（系统分类、家庭成员）**无 HTTP 缓存头**，每次导航都重复拉取不变的数据

## User Flow

```
用户打开 App（弱网）
        │
        ▼
   加载 index.html
        │
        ▼
   下载 JS/CSS bundle ──── 无 immutable 头，每次重新下载
        │
        ▼
   Vue 启动，挂载 Dashboard
        │
        ▼
   并发发起 7 个 API 请求 ──── 每个都打 DB，无缓存
        │
        ▼
   等待最慢的请求返回
        │
        ▼
   页面完整渲染
```

目标状态：

```
用户打开 App（弱网）
        │
        ▼
   加载 index.html（no-cache）
        │
        ▼
   JS/CSS bundle 命中浏览器缓存（immutable）──── 近零网络开销
        │
        ▼
   Vue 启动，挂载 Dashboard
        │
        ▼
   发起 1 个 /dashboard/bundle 请求
        │
        ├── 命中后端内存缓存 ──── 微秒级返回
        │
        └── 缓存未命中 ──── DB 聚合，写入缓存，返回
        │
        ▼
   页面完整渲染
```

## Requirements

**后端：Dashboard 内存缓存**

- R1. 在 `backend/app/services/` 中新增 dashboard 缓存层，复用现有 `MemoryCacheBackend`，不引入新依赖
- R2. 缓存 key 格式：`dashboard:bundle:{family_id}`，TTL：`60 + random(0, 30)` 秒（打散避免同时过期）
- R3. 以下写操作完成后主动调用 `cache.delete()` 失效对应 family 的缓存：
  - 资产创建 / 更新 / 删除 / 归档
  - 资产价值更新
  - 资产出售（sell）/ 退役（retire）/ 恢复（reactivate）
  - 所有 batch 操作（batch_archive、batch_update_category、batch_update_tags、batch_update_status）
  - 负债创建 / 更新 / 删除
  - 负债还款记录
- R4. 缓存失效仅影响当前 family（按 `family_id` 隔离），不影响其他家庭

**后端：Dashboard Bundle 端点**

- R5. 新增 `GET /api/v1/dashboard/bundle` 端点，覆盖前端 `fetchAll()` 并发调用的 7 个端点：`overview`、`states-summary`、`home-assets`、`allocation`、`trend`、`low-usage-assets`、`expiring-soon`，合并为单一 JSON 响应返回
- R6. Bundle 响应结构使用固定 key：`overview`、`statesSummary`、`homeAssets`、`allocation`、`trend`、`lowUsageAssets`、`expiringSoon`（domain-meaningful，独立于端点 URL 路径）
- R7. 原有 7 个独立端点**保留不删除**，保持向后兼容；`topAssets`、`dailyCostRanking`、`investmentReturns` 等其余端点不纳入 bundle，继续独立调用
- R8. Bundle 端点应用 R1-R4 的缓存层（命中缓存时直接返回，不重新调用 service 函数）

**前端：切换至 Bundle 端点**

- R9. `frontend/src/stores/dashboard.ts` 中的 `fetchAll()` 改为调用单一 `/dashboard/bundle` 端点
- R10. 从 bundle 响应中解构数据，分别填充各个 store state，保持现有 state 结构不变（其他组件无需改动）

**前端：Nginx 静态资源长效缓存**

- R11. Nginx 对 Vite 输出的内容哈希静态资源（`/assets/` 路径下的 `.js`、`.css` 文件）设置 `Cache-Control: public, max-age=31536000, immutable`
- R12. `index.html` 设置 `Cache-Control: no-cache`，确保每次访问都获取最新入口文件
- R13. 其他静态资源（字体、图片）沿用 `frontend/nginx.conf` 现有的 30 天缓存配置，不改动

**后端：稳定端点 HTTP 缓存头**

- R14. `GET /api/v1/categories` 响应添加 `Cache-Control: private, max-age=300`（5 分钟）
- R15. `GET /api/v1/family/members` 响应添加 `Cache-Control: private, max-age=300`
- R16. `GET /api/v1/family/info` 响应添加 `Cache-Control: private, max-age=300`
- R17. 家庭成员发生变更（邀请加入、移除成员、角色变更）时，相关端点的缓存头不需要主动失效——依赖 5 分钟 TTL 自然过期即可（家庭 app 场景可接受）

## Success Criteria

- Dashboard 首次加载的 fetchAll() 请求数从 7 个降至 1 个
- 重复访问时，JS/CSS bundle 命中浏览器缓存（Network 面板显示 `(disk cache)` 或 `304`）
- 同一 family 在 60 秒内的重复 dashboard 请求由内存缓存响应，不触发 DB 查询
- 资产/负债写操作后，下一次 dashboard 请求能获取到最新数据（缓存已失效）
- 所有现有后端测试继续通过（`uv run pytest tests/ -v`）
- 前端构建无类型错误（`npm run build`）

## Scope Boundaries

- **不做**：Redis 缓存层（现有 `MemoryCacheBackend` 已足够，Redis 是未来升级路径）
- **不做**：Service Worker / PWA 离线能力
- **不做**：Pinia store 持久化到 localStorage/sessionStorage
- **不做**：乐观 UI（独立改进，不在本次范围）
- **不做**：JWT 嵌入 family_id（独立改进，不在本次范围）
- **不做**：系统分类常量化（独立改进，不在本次范围）
- **不做**：ETag / 304 协商缓存（Cache-Control 已解决主要问题，ETag 只省带宽不省延迟，复杂度不值得）
- **不做**：ETag 失效的主动推送机制

## Key Decisions

- **Bundle 覆盖 fetchAll() 的 7 个端点**：bundle 端点是新增，不是替换。原 7 个端点保留兼容性，topAssets/dailyCostRanking/investmentReturns 继续独立调用
- **缓存粒度选 family 级别**：key 包含 `family_id`，不同家庭互不影响
- **写时主动失效 + TTL 打散兜底**：写操作触发主动 `cache.delete()` 保证数据准确性；TTL 采用 `60 + random(0, 30)` 秒打散，防止多个 family 缓存同时过期造成 DB 突刺（thundering herd）
- **HTTP 缓存头用 TTL 不用主动失效**：稳定端点（categories、members）5 分钟内的数据延迟对家庭 app 可接受，避免引入失效通知复杂度
- **Nginx 缓存头改在 `frontend/nginx.conf`**：Vite 哈希资源由 frontend 容器直接 serve，缓存头应在 frontend 容器的 nginx 配置中设置，主 nginx.conf 作为透明代理会自动透传响应头给浏览器

## Dependencies / Assumptions

- Vite 构建输出的 JS/CSS 文件名包含内容哈希（默认行为，已确认）
- 现有 `MemoryCacheBackend` 是进程内单例，单 worker 部署下行为正确；多 worker 场景下需升级到 Redis（已有接口，不在本次范围）
- `dashboard_service` 的各函数签名为 `func(db, user)` 或 `func(db, user, **kwargs)`，bundle 端点可直接调用

## Outstanding Questions

### Resolve Before Planning
_（无阻塞问题，可直接进入规划）_

### Deferred to Planning

- [Affects R5][Technical] bundle 端点中 `trend`、`expiring-soon` 等带可选参数的端点，bundle 中使用什么默认参数值？建议规划时直接查看前端 `fetchAll()` 的实际调用参数确认
- [Affects R8][Technical] 缓存序列化：bundle 响应存入缓存前应调用 `.model_dump()` 序列化为 dict，命中缓存时直接返回 `JSONResponse`，绕过 FastAPI response_model 验证——规划时确认 `MemoryCacheBackend` 存储行为与此兼容
- [Affects R1][Technical] 在 `cache/factory.py` 中新增 `get_dashboard_cache()` 单例，与现有 `get_rate_limit_cache()` 模式一致，供 assets.py / liabilities.py 路由 import 使用

## Next Steps

→ `/ce:plan` 进行结构化实现规划
