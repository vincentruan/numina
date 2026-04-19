---
date: 2026-04-17
status: completed
type: feat
origin: docs/brainstorms/2026-04-17-performance-caching-requirements.md
---

# feat: Performance Caching — Dashboard Bundle + Static Asset Cache

## Problem Frame

(see origin: docs/brainstorms/2026-04-17-performance-caching-requirements.md)

Dashboard 每次加载触发 7 个并发 API 请求，弱网下往返开销达 1.4 秒。后端已有 `MemoryCacheBackend` 但未用于业务查询。Nginx 静态资源无长效缓存头，稳定端点无 HTTP 缓存头。

**目标：** 7 个请求 → 1 个；静态资源命中浏览器缓存；稳定端点 5 分钟内免重复拉取。

---

## High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│  frontend/nginx.conf                                        │
│  /assets/*.js|css  → Cache-Control: public, max-age=1y, immutable │
│  /index.html       → Cache-Control: no-cache               │
└─────────────────────────────────────────────────────────────┘
         │ proxy_pass (透传响应头)
┌─────────────────────────────────────────────────────────────┐
│  FastAPI                                                    │
│                                                             │
│  GET /dashboard/bundle                                      │
│    ├── cache hit  → return cached dict (JSONResponse)       │
│    └── cache miss → call 7 services → model_dump → cache.set│
│                                                             │
│  GET /categories, /family/members, /family/info             │
│    └── response.headers["Cache-Control"] = "private, max-age=300" │
│                                                             │
│  POST/PUT/DELETE assets/* + liabilities/*                   │
│    └── after service returns → invalidate_dashboard_bundle()│
└─────────────────────────────────────────────────────────────┘
         │
┌─────────────────────────────────────────────────────────────┐
│  MemoryCacheBackend (singleton via get_dashboard_cache())   │
│  key: dashboard:bundle:{family_id}                          │
│  TTL: random.randint(60, 90) seconds                        │
│  value: dict (bundle JSON, model_dump'd)                    │
└─────────────────────────────────────────────────────────────┘
```

**Bundle 响应结构（7 个 key）：**
```python
{
  "overview":       OverviewResponse.model_dump(),
  "statesSummary":  dict (get_states_summary),
  "homeAssets":     dict (get_home_assets, limit=5),
  "allocation":     AllocationResponse.model_dump(),  # {items, total}
  "trend":          TrendResponse.model_dump(),        # period="month"
  "lowUsageAssets": list[LowUsageItem.model_dump()],
  "expiringSoon":   list[ExpiringSoonItem.model_dump()] # days_threshold=90
}
```

**Key decisions:**
- 失效在 router 层调用（service 返回后），不修改 service 签名
- Bundle 任一 service 失败 → fail fast，返回 500，不缓存部分结果
- 内存缓存仅支持单 worker 部署；多 worker 需升级 Redis（已有接口）
- `batch_export_assets` 是只读操作，不失效缓存
- `POST /import/json` 需要失效缓存（批量写入影响最大）

---

## Implementation Units

### Unit 1 — 新增 `get_dashboard_cache()` 单例

**文件：** `backend/app/services/cache/factory.py`

在现有 `_captcha_payload_cache` 单例之后，按相同模式添加：
- `_dashboard_cache: CacheBackend | None = None`
- `get_dashboard_cache() -> CacheBackend` — 支持 `settings.CACHE_BACKEND == "redis"` 分支（与现有两个单例完全一致）
- `reset_dashboard_cache() -> None` — 供测试用，与 `reset_rate_limit_cache()` 模式一致

**测试文件：** `backend/tests/test_dashboard.py`（现有文件，在 fixture 中调用 `reset_dashboard_cache()`）

**测试场景：**
- `get_dashboard_cache()` 两次调用返回同一实例（单例）
- `reset_dashboard_cache()` 后再次调用返回新实例
- 默认 backend 为 `MemoryCacheBackend`（非 Redis 配置下）

---

### Unit 2 — 新增 `invalidate_dashboard_bundle()` 工具函数

**文件：** `backend/app/services/cache/factory.py`（或新建 `backend/app/services/dashboard_cache.py`）

```python
def invalidate_dashboard_bundle(family_id: str) -> None:
    cache = get_dashboard_cache()
    cache.delete(f"dashboard:bundle:{family_id}")
```

这是一个纯工具函数，供所有写 router 调用。放在 `factory.py` 末尾即可，无需新文件。

**测试场景：**
- 调用后对应 key 从缓存中消失
- 调用时 key 不存在不报错（`MemoryCacheBackend.delete` 对不存在的 key 应静默）

---

### Unit 3 — 新增 `GET /api/v1/dashboard/bundle` 端点

**文件：** `backend/app/routers/dashboard.py`

**逻辑：**
1. 从 `get_dashboard_cache()` 读取 `dashboard:bundle:{user.family_id}`
2. 命中 → 直接 `return JSONResponse(cached_dict)`
3. 未命中 → 依次调用 7 个 service 函数（使用固定默认参数）
4. 任一 service 抛出异常 → 不缓存，向上传播（FastAPI 返回 500）
5. 全部成功 → 构建 bundle dict（所有 Pydantic model 调用 `.model_dump()`）
6. `cache.set(key, bundle_dict, ttl_seconds=random.randint(60, 90))`
7. `return JSONResponse(bundle_dict)`

**固定参数：**
- `get_trend(db, user, period="month")`
- `get_home_assets(db, user, limit=5)`
- `get_expiring_soon_assets(db, user, days_threshold=90)`

**新增 Pydantic schema：** `backend/app/schemas/dashboard.py` 中新增 `DashboardBundleResponse`（可选，用于 OpenAPI 文档；实际返回走 `JSONResponse` 绕过 response_model 验证）

**测试文件：** `backend/tests/test_dashboard.py`

**测试场景：**
- 首次请求（cache miss）→ 返回 200，响应包含全部 7 个 key
- 第二次请求（cache hit）→ 返回 200，内容与第一次相同，未重新调用 service（可通过 mock 验证）
- 写操作后请求（cache invalidated）→ 返回新数据
- 模拟某个 service 抛出异常 → 返回 500，缓存中无该 key
- 未认证请求 → 返回 401
- `allocation` 响应包含 `items` 和 `total` 两个字段
- TTL 在 60–90 秒范围内（mock `random.randint` 验证）

---

### Unit 4 — 资产写端点添加缓存失效

**文件：** `backend/app/routers/assets.py`

在以下每个 handler 的 service 调用返回后，添加 `invalidate_dashboard_bundle(user.family_id)`：

| Handler | 路径 |
|---|---|
| `create_asset` | `POST /assets/` |
| `update_asset` | `PUT /assets/{asset_id}` |
| `delete_asset` | `DELETE /assets/{asset_id}` |
| `update_value` | `PUT /assets/{asset_id}/value` |
| `sell_asset` | `POST /assets/{asset_id}/sell` |
| `retire_asset` | `POST /assets/{asset_id}/retire` |
| `reactivate_asset` | `POST /assets/{asset_id}/reactivate` |
| `batch_archive_assets` | `POST /assets/batch/archive` |
| `batch_update_category` | `PUT /assets/batch/category` |
| `batch_update_tags` | `PUT /assets/batch/tags` |
| `batch_update_status` | `PUT /assets/batch/status` |

**不添加：** `batch_export_assets`（只读）

**Import 添加：** `from app.services.cache.factory import invalidate_dashboard_bundle`

**测试文件：** `backend/tests/test_assets.py`（现有文件）

**测试场景：**
- 创建资产后，`dashboard:bundle:{family_id}` key 从缓存中消失
- 更新资产价值后，缓存失效
- 跨 family 隔离：family A 的写操作不影响 family B 的缓存

---

### Unit 5 — 负债写端点添加缓存失效

**文件：** `backend/app/routers/liabilities.py`

在以下每个 handler 的 service 调用返回后，添加 `invalidate_dashboard_bundle(user.family_id)`：

| Handler | 路径 |
|---|---|
| `create_liability` | `POST /liabilities/` |
| `update_liability` | `PUT /liabilities/{liability_id}` |
| `delete_liability` | `DELETE /liabilities/{liability_id}` |
| `record_payment` | `PUT /liabilities/{liability_id}/payment` |

**测试文件：** `backend/tests/test_liabilities.py`（现有文件）

**测试场景：**
- 记录还款后，缓存失效
- 负债删除后，缓存失效

---

### Unit 6 — import/json 端点添加缓存失效

**文件：** 找到 `POST /import/json` 的 router 文件（根据 flow 分析，位于某个 import router）

在 `db.commit()` 之后添加 `invalidate_dashboard_bundle(user.family_id)`。

**测试场景：**
- 批量导入后，缓存失效

---

### Unit 7 — 稳定端点添加 HTTP 缓存头

**文件：**
- `backend/app/routers/categories.py`
- `backend/app/routers/family.py`

在以下 3 个 GET handler 的签名中注入 `response: Response`，并在返回前添加：
```python
response.headers["Cache-Control"] = "private, max-age=300"
```

| 端点 | 文件 |
|---|---|
| `GET /api/v1/categories` | `categories.py` → `list_categories` |
| `GET /api/v1/family/members` | `family.py` → `get_members` |
| `GET /api/v1/family/info` | `family.py` → `get_family` |

**Import 添加：** `from fastapi import Response`（如未导入）

**测试场景：**
- `GET /categories` 响应头包含 `Cache-Control: private, max-age=300`
- `GET /family/members` 响应头包含 `Cache-Control: private, max-age=300`
- `GET /family/info` 响应头包含 `Cache-Control: private, max-age=300`

---

### Unit 8 — frontend/nginx.conf 添加静态资源缓存头

**文件：** `frontend/nginx.conf`

在现有图片/字体 location 块之前，新增两个 location 块：

```nginx
# Vite 内容哈希 JS/CSS — 永久缓存
location ~* \.(js|css)$ {
    expires 1y;
    add_header Cache-Control "public, max-age=31536000, immutable";
    try_files $uri =404;
}

# SPA 入口 — 每次检查更新
location = /index.html {
    add_header Cache-Control "no-cache";
    try_files $uri =404;
}
```

现有图片/字体规则（`\.(png|svg|ico|webp|jpg|jpeg|gif|woff|woff2|ttf|eot)$`）保持不变。

**验证：** 构建后访问 `/assets/index-[hash].js`，响应头应包含 `Cache-Control: public, max-age=31536000, immutable`。

---

### Unit 9 — 前端新增 `getDashboardBundle()` API 函数

**文件：** `frontend/src/api/dashboard.ts`

新增：
```typescript
export function getDashboardBundle() {
  return http.get<DashboardBundleResponse>('/dashboard/bundle')
}
```

**文件：** `frontend/src/types/index.ts`（或 `dashboard.ts`）

新增 `DashboardBundleResponse` interface，字段与 backend bundle dict 对应：
```typescript
interface DashboardBundleResponse {
  overview: DashboardOverview
  statesSummary: StatesSummaryResponse
  homeAssets: Record<string, Asset[]>
  allocation: { items: AllocationItem[]; total: number }
  trend: { points: TrendPoint[] }
  lowUsageAssets: LowUsageItem[]
  expiringSoon: ExpiringSoonItem[]
}
```

---

### Unit 10 — 前端 `fetchAll()` 切换至 bundle 端点

**文件：** `frontend/src/stores/dashboard.ts`

将 `fetchAll()` 改为：
```typescript
async function fetchAll() {
  loading.value = true
  try {
    const res = await getDashboardBundle()
    const data = res.data
    overview.value = data.overview
    statesSummary.value = data.statesSummary
    homeAssets.value = data.homeAssets
    allocation.value = data.allocation.items
    allocationTotal.value = data.allocation.total
    trend.value = data.trend.points
    lowUsageAssets.value = data.lowUsageAssets
    expiringSoonAssets.value = data.expiringSoon
  } finally {
    loading.value = false
  }
}
```

原有 `fetchOverview()`、`fetchStatesSummary()` 等独立函数**保留不删除**（其他页面可能单独调用）。

**验证：** `npm run build` 无类型错误；Dashboard 页面正常加载所有数据。

---

## Sequencing

```
Unit 1 (cache singleton)
  └── Unit 2 (invalidate helper)
        ├── Unit 3 (bundle endpoint)      ← 依赖 Unit 1+2
        ├── Unit 4 (assets invalidation)  ← 依赖 Unit 2
        ├── Unit 5 (liabilities invalidation) ← 依赖 Unit 2
        └── Unit 6 (import invalidation)  ← 依赖 Unit 2

Unit 7 (HTTP cache headers)  ← 独立，可并行
Unit 8 (nginx config)        ← 独立，可并行

Unit 9 (frontend API)
  └── Unit 10 (fetchAll migration) ← 依赖 Unit 3 + Unit 9
```

**推荐顺序：** 1 → 2 → 3 → 4+5+6（并行）→ 7+8（并行）→ 9 → 10

---

## Test Strategy

**现有测试套件：** `backend/tests/` 36 个测试，全部使用 in-memory SQLite + function-scope fixture。

**关键：** 在 `conftest.py` 的 `db` fixture 中添加 `reset_dashboard_cache()` 调用，防止缓存单例跨测试污染。

```python
# conftest.py — 在现有 db fixture 中添加
from app.services.cache.factory import reset_dashboard_cache

@pytest.fixture
def db():
    reset_dashboard_cache()  # 新增
    # ... 现有代码 ...
```

**新增测试：** 主要在 `test_dashboard.py` 中覆盖 Unit 3 的场景（见上）。Unit 4/5/6 的失效测试可作为现有测试的断言扩展，不需要新测试文件。

**前端验证：** `npm run build` 类型检查；浏览器 DevTools Network 面板验证请求数和缓存头。

---

## Risks & Mitigations

| 风险 | 缓解 |
|---|---|
| 多 worker 部署下缓存失效不传播 | 文档明确：内存缓存仅支持单 worker；多 worker 需设置 `CACHE_BACKEND=redis` |
| `get_states_summary` 未做汇率转换（pre-existing bug） | 本次不修复，在 bundle 响应中该字段保持现有行为；记录为已知问题 |
| `import/json` router 文件路径未确认 | Unit 6 实现前先定位文件 |
| `allocation.total` 字段名前端解构错误 | Unit 10 中明确 `data.allocation.total` → `allocationTotal.value` |
| nginx location 顺序影响匹配 | JS/CSS 规则放在图片/字体规则之前，避免被更宽泛的规则覆盖 |

---

## Dependencies / Assumptions

- 单 worker 部署（默认 Docker Compose 配置）
- `MemoryCacheBackend.delete()` 对不存在的 key 静默（不抛出）— 实现前确认
- Vite 默认输出 `build.assetsDir = "assets"`，nginx location `~* \.(js|css)$` 可匹配
- `POST /import/json` router 文件需在 Unit 6 实现前定位

---

## Outstanding Questions

### Deferred to Implementation

- [Affects Unit 6] `POST /import/json` 的 router 文件路径 — 实现时 `grep -r "import/json" backend/`
- [Affects Unit 3] `get_states_summary` 是否需要在 bundle 中修复汇率转换 — 建议作为独立 issue，不阻塞本次
- [Affects Unit 3] `MemoryCacheBackend.delete()` 对不存在 key 的行为 — 实现前读 `memory.py` 确认

## Next Steps

→ `/ce:work` 按 Unit 1 → 2 → 3 → ... 顺序执行
