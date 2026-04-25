# 移除 Dashboard Bundle 缓存设计文档

**日期：** 2026-04-26  
**状态：** 已批准，待实现  
**范围：** backend `dashboard` router + `cache/factory.py`；frontend `stores/dashboard.ts` + `api/dashboard.ts`

---

## 背景与问题

### 现有缓存体系

后端共有三个缓存实例：

| 缓存实例 | 用途 | TTL | 评估 |
|---|---|---|---|
| `rate_limit_cache` | 登录/注册/刷新 token 频率限制 | 60s–3600s | 合理，保留 |
| `captcha_payload_cache` | 验证码 payload 注册表 | 短暂 | 合理，保留 |
| `dashboard_cache` | dashboard bundle 整包缓存 | 60–90s random | **移除** |

### 核心缺陷

`GET /dashboard/bundle` 将 overview、allocation、trend、home-assets、low-usage、expiring-soon 打包缓存，key 为 `dashboard:bundle:{family_id}`。

**Bug 1：cache key 粒度错误（数据正确性问题）**  
`default_currency` 是 user 级别字段，但 cache key 是 family 级别。同一 family 内不同成员使用不同货币偏好时，会命中同一缓存，导致其中一方看到错误货币的数据。

**Bug 2：invalidation 路径不完整**  
以下写操作会导致 dashboard 数据变化，但未触发 invalidation：
- `PUT /auth/profile`（修改 `default_currency`）
- 汇率 scheduler 更新（`fetch_and_store_rates()`）

**Bug 3：TTL 随机化是 workaround，不是解法**  
60–90s 随机 TTL 用于避免缓存雪崩，但掩盖了 invalidation 不完整的根本问题。

### 为什么不修复而是移除

Dashboard bundle 缓存的收益前提是"数据变化不频繁"，但 dashboard 数据聚合自多个可变输入（资产、负债、汇率、用户货币偏好），invalidation 路径难以穷举。对于自托管小家庭场景，DB 查询量小，60–90s 缓存的性能收益可忽略不计，而维护成本和数据一致性风险不成比例。

---

## 方案

### 后端

**删除以下内容：**

1. `backend/app/services/cache/factory.py`
   - `_dashboard_cache` 全局变量
   - `get_dashboard_cache()` 函数
   - `reset_dashboard_cache()` 函数
   - `invalidate_dashboard_bundle()` 函数

2. `backend/app/routers/dashboard.py`
   - `GET /dashboard/bundle` 整个接口
   - `get_dashboard_cache` import

3. `backend/app/routers/assets.py`
   - 所有 `invalidate_dashboard_bundle(user.family_id)` 调用
   - `invalidate_dashboard_bundle` import

4. `backend/app/routers/liabilities.py`
   - 所有 `invalidate_dashboard_bundle(user.family_id)` 调用
   - `invalidate_dashboard_bundle` import

**保留不动：**
- 所有现有子接口（`/overview`、`/allocation`、`/trend`、`/top-assets`、`/daily-cost-ranking`、`/low-usage-assets`、`/investment-returns`、`/states-summary`、`/home-assets`、`/expiring-soon`）
- `rate_limit_cache` 和 `captcha_payload_cache`

### 前端

**`fetchAll()` 改为两阶段加载：**

```
Phase 1（并发，阻塞 loading）:
  Promise.all([fetchOverview(), fetchStatesSummary()])
  → loading = false，首屏关键数据可见

Phase 2（并发，后台静默，不阻塞）:
  Promise.all([fetchAllocation(), fetchTrend(), fetchLowUsageAssets(), fetchExpiringSoonAssets()])
```

`homeAssets` 由 `DashboardPage` mount 后通过 `fetchAssetsPage()` 单独触发，不纳入 `fetchAll()`。

**删除以下内容：**

1. `frontend/src/api/dashboard.ts`
   - `getDashboardBundle()` 函数
   - 相关 `DashboardBundleResponse` 类型引用

2. `frontend/src/stores/dashboard.ts`
   - `fetchAll()` 内对 `getDashboardBundle()` 的调用，替换为两阶段并发请求

---

## 数据流对比

**改前：**
```
mount
  → fetchAll()
  → GET /dashboard/bundle  (缓存 60-90s, family 级 key)
  → 一次性填充所有 state
  → loading = false
```

**改后：**
```
mount
  → fetchAll() Phase 1: GET /overview + /states-summary  (并发)
  → loading = false，首屏可见
  → fetchAll() Phase 2: GET /allocation + /trend + /low-usage + /expiring-soon  (并发，后台)
  → fetchAssetsPage()  (独立触发)
```

---

## 不在本次范围内

- `ExchangeRateService._cache` 无 TTL 问题——进程级汇率缓存永不过期，应单独处理
- `DataStatsPage` 里的 `fetchAll()` 调用——改完后自然适配，无需额外处理
- `cache/__init__.py` 的 `__all__` 清理——跟随本次删除一并处理

---

## 验证标准

- [ ] `GET /dashboard/bundle` 返回 404
- [ ] 资产/负债的增删改操作后，dashboard 数据实时反映变化（无缓存延迟）
- [ ] 不同货币偏好的家庭成员各自看到正确货币的数据
- [ ] `DashboardPage` 首屏 overview + states-summary 先于 allocation/trend 渲染
- [ ] 后端无 `dashboard_cache` 相关代码残留
- [ ] 前端无 `getDashboardBundle` 相关代码残留
