# Remove Dashboard Bundle Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除有缺陷的 `/dashboard/bundle` 缓存接口，修复 family 级 cache key 与 user 级货币偏好不匹配的数据正确性 bug，前端改为两阶段并发加载。

**Architecture:** 后端删除 `dashboard_cache` 实例及所有引用它的代码（factory、router、assets、liabilities、import_ 共 5 个文件）；前端 `fetchAll()` 拆成 Phase 1（overview + states-summary，阻塞 loading）和 Phase 2（allocation + trend + low-usage + expiring-soon，后台静默），`api/dashboard.ts` 删除 bundle 相关代码。

**Tech Stack:** Python 3.11 + FastAPI（backend）；Vue 3 + TypeScript + Pinia（frontend）；pytest（backend tests）；vue-tsc + vitest（frontend checks）

---

## File Map

| 文件 | 操作 |
|---|---|
| `backend/app/services/cache/factory.py` | 删除 `_dashboard_cache`、`get_dashboard_cache`、`reset_dashboard_cache`、`invalidate_dashboard_bundle` |
| `backend/app/services/cache/__init__.py` | 无需改动（bundle 相关函数未在 `__all__` 中导出） |
| `backend/app/routers/dashboard.py` | 删除 `GET /dashboard/bundle` 路由及 `get_dashboard_cache` import |
| `backend/app/routers/assets.py` | 删除所有 `invalidate_dashboard_bundle` 调用及 import |
| `backend/app/routers/liabilities.py` | 删除所有 `invalidate_dashboard_bundle` 调用及 import |
| `backend/app/routers/import_.py` | 删除 `invalidate_dashboard_bundle` 调用及 import |
| `frontend/src/api/dashboard.ts` | 删除 `DashboardBundleResponse` 接口和 `getDashboardBundle()` 函数 |
| `frontend/src/stores/dashboard.ts` | 重写 `fetchAll()` 为两阶段并发加载 |

---

## Task 1: 清理 backend cache factory

**Files:**
- Modify: `backend/app/services/cache/factory.py`

- [ ] **Step 1: 删除 factory.py 中的 dashboard cache 代码**

将 `backend/app/services/cache/factory.py` 中以下内容全部删除：

```python
# 删除这个全局变量（第19行）
_dashboard_cache: CacheBackend | None = None
```

```python
# 删除 get_dashboard_cache 函数（第86-105行）
def get_dashboard_cache() -> CacheBackend:
    """Get or create the dashboard bundle cache backend.
    ...
    """
    global _dashboard_cache
    if _dashboard_cache is None:
        if settings.CACHE_BACKEND == "redis":
            _dashboard_cache = RedisCacheBackend(settings.REDIS_URL)
        else:
            _dashboard_cache = MemoryCacheBackend()
    return _dashboard_cache


def reset_dashboard_cache() -> None:
    """Reset dashboard cache for testing.
    ...
    """
    global _dashboard_cache
    if _dashboard_cache is not None:
        _dashboard_cache.clear()
    _dashboard_cache = None


def invalidate_dashboard_bundle(family_id: str) -> None:
    """Invalidate dashboard bundle cache for a specific family.
    ...
    """
    cache = get_dashboard_cache()
    cache.delete(f"dashboard:bundle:{family_id}")
```

删除后，`factory.py` 只保留 `_rate_limit_cache`、`_captcha_payload_cache` 及其对应的 get/reset 函数，文件末尾不应有任何 dashboard 相关代码。

- [ ] **Step 2: 验证 factory.py 无残留**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
grep -n "dashboard" app/services/cache/factory.py
```

期望输出：无任何输出（空）。

- [ ] **Step 3: 运行 cache 相关测试**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run pytest tests/test_cache.py tests/test_cache_config.py -v
```

期望：所有测试 PASS。如有失败，检查测试是否引用了已删除的函数，按 Task 5 处理。

- [ ] **Step 4: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
git add app/services/cache/factory.py
git commit -m "refactor(cache): remove dashboard bundle cache from factory"
```

---

## Task 2: 清理 dashboard router

**Files:**
- Modify: `backend/app/routers/dashboard.py`

- [ ] **Step 1: 删除 bundle 路由及其 import**

在 `backend/app/routers/dashboard.py` 中：

1. 删除第 22 行的 import：
```python
# 删除这一行
from app.services.cache.factory import get_dashboard_cache
```

2. 删除整个 `get_bundle` 路由函数（第 136-173 行）：
```python
# 删除从 @router.get("/bundle") 到函数结尾的全部内容
@router.get("/bundle")
def get_bundle(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get all dashboard data in a single request.
    ...
    """
    cache = get_dashboard_cache()
    cache_key = f"dashboard:bundle:{user.family_id}"
    # ... 整个函数体
```

同时删除文件顶部不再需要的 `import random`（如果只被 bundle 路由使用）。

检查：`random` 是否还被文件其他地方使用：
```bash
grep -n "random" /Users/vincentruan/geek_space/github/numina/backend/app/routers/dashboard.py
```
如果只在 bundle 路由中出现，一并删除 `import random`。

- [ ] **Step 2: 验证 dashboard router 无残留**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
grep -n "bundle\|dashboard_cache\|get_dashboard_cache\|random" app/routers/dashboard.py
```

期望输出：无任何输出。

- [ ] **Step 3: 运行 lint 检查**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run ruff check app/routers/dashboard.py
```

期望：无错误。

- [ ] **Step 4: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
git add app/routers/dashboard.py
git commit -m "refactor(dashboard): remove /bundle endpoint"
```

---

## Task 3: 清理 assets router

**Files:**
- Modify: `backend/app/routers/assets.py`

- [ ] **Step 1: 删除 assets.py 中所有 invalidate_dashboard_bundle 调用**

在 `backend/app/routers/assets.py` 中：

1. 删除第 25 行的 import：
```python
# 删除这一行
from app.services.cache.factory import invalidate_dashboard_bundle
```

2. 删除以下所有调用行（共 11 处，每处单独一行）：
```python
invalidate_dashboard_bundle(user.family_id)
```

涉及的路由函数：`create_asset`、`update_asset`、`delete_asset`、`update_value`、`sell_asset`、`retire_asset`、`reactivate_asset`、`batch_archive_assets`、`batch_update_category`、`batch_update_tags`、`batch_update_status`。

- [ ] **Step 2: 验证无残留**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
grep -n "invalidate_dashboard_bundle\|dashboard_cache" app/routers/assets.py
```

期望输出：无任何输出。

- [ ] **Step 3: 运行 lint**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run ruff check app/routers/assets.py
```

期望：无错误。

- [ ] **Step 4: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
git add app/routers/assets.py
git commit -m "refactor(assets): remove dashboard cache invalidation calls"
```

---

## Task 4: 清理 liabilities router 和 import_ router

**Files:**
- Modify: `backend/app/routers/liabilities.py`
- Modify: `backend/app/routers/import_.py`

- [ ] **Step 1: 清理 liabilities.py**

在 `backend/app/routers/liabilities.py` 中：

1. 删除第 15 行的 import：
```python
# 删除这一行
from app.services.cache.factory import invalidate_dashboard_bundle
```

2. 删除以下所有调用行（共 4 处）：
```python
invalidate_dashboard_bundle(user.family_id)
```

涉及的路由函数：`create_liability`、`update_liability`、`delete_liability`、`record_payment`。

- [ ] **Step 2: 清理 import_.py**

在 `backend/app/routers/import_.py` 中：

1. 删除第 14 行的 import：
```python
# 删除这一行
from app.services.cache.factory import invalidate_dashboard_bundle
```

2. 删除第 140 行的调用：
```python
invalidate_dashboard_bundle(user.family_id)
```

- [ ] **Step 3: 验证无残留**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
grep -rn "invalidate_dashboard_bundle\|dashboard_cache\|get_dashboard_cache" app/routers/
```

期望输出：无任何输出。

- [ ] **Step 4: 运行 lint**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run ruff check app/routers/liabilities.py app/routers/import_.py
```

期望：无错误。

- [ ] **Step 5: 运行后端全量测试**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run pytest tests/ -v
```

期望：所有测试 PASS。

- [ ] **Step 6: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
git add app/routers/liabilities.py app/routers/import_.py
git commit -m "refactor(liabilities,import): remove dashboard cache invalidation calls"
```

---

## Task 5: 清理 frontend api/dashboard.ts

**Files:**
- Modify: `frontend/src/api/dashboard.ts`

- [ ] **Step 1: 删除 DashboardBundleResponse 接口和 getDashboardBundle 函数**

在 `frontend/src/api/dashboard.ts` 中，删除以下内容（第 18-30 行）：

```typescript
// 删除这个接口
export interface DashboardBundleResponse {
  overview: DashboardOverview
  statesSummary: StatesSummaryResponse
  homeAssets: Record<string, Asset[]>
  allocation: AllocationResponse
  trend: TrendResponse
  lowUsageAssets: LowUsageItem[]
  expiringSoon: ExpiringSoonItem[]
}

// 删除这个函数
export function getDashboardBundle() {
  return http.get<DashboardBundleResponse>('/dashboard/bundle')
}
```

删除后文件从 `export function getOverview()` 开始。

- [ ] **Step 2: 验证无残留**

```bash
grep -n "Bundle\|bundle" /Users/vincentruan/geek_space/github/numina/frontend/src/api/dashboard.ts
```

期望输出：无任何输出。

- [ ] **Step 3: 运行 typecheck**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
npm run typecheck
```

期望：无类型错误。如有错误，说明 `DashboardBundleResponse` 还被其他文件引用，按错误提示逐一修复。

- [ ] **Step 4: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
git add src/api/dashboard.ts
git commit -m "refactor(api): remove getDashboardBundle and DashboardBundleResponse"
```

---

## Task 6: 重写 frontend stores/dashboard.ts 的 fetchAll()

**Files:**
- Modify: `frontend/src/stores/dashboard.ts`

- [ ] **Step 1: 重写 fetchAll() 为两阶段加载**

将 `frontend/src/stores/dashboard.ts` 中的 `fetchAll()` 函数（第 106-131 行）替换为：

```typescript
async function fetchAll(): Promise<void> {
  // Dedup: if a request is already in-flight, return the same Promise
  if (_fetchPromise !== null) {
    return _fetchPromise
  }

  loading.value = true
  _fetchPromise = (async () => {
    try {
      // Phase 1: critical data — blocks loading indicator
      await Promise.all([fetchOverview(), fetchStatesSummary()])
    } finally {
      loading.value = false
      _fetchPromise = null
    }

    // Phase 2: secondary data — fires in background, does not block
    Promise.all([
      fetchAllocation(),
      fetchTrend(),
      fetchLowUsageAssets(),
      fetchExpiringSoonAssets(),
    ]).catch(() => {
      // Phase 2 failures are non-critical; individual fetch functions
      // do not throw by default, so this is a safety net only
    })
  })()

  return _fetchPromise
}
```

注意：`fetchOverview`、`fetchStatesSummary`、`fetchAllocation`、`fetchTrend`、`fetchLowUsageAssets`、`fetchExpiringSoonAssets` 这些函数已在 store 中定义，直接调用即可，无需修改它们。

同时删除 `fetchAll()` 内原有的对 `getDashboardBundle` 的 import 引用（如果 `getDashboardBundle` 是在函数内部 import 的，一并删除；如果是文件顶部 import，检查并删除）：

```bash
grep -n "getDashboardBundle\|DashboardBundleResponse" /Users/vincentruan/geek_space/github/numina/frontend/src/stores/dashboard.ts
```

如有残留，删除对应行。

- [ ] **Step 2: 验证 store 无残留**

```bash
grep -n "bundle\|Bundle\|getDashboardBundle" /Users/vincentruan/geek_space/github/numina/frontend/src/stores/dashboard.ts
```

期望输出：无任何输出。

- [ ] **Step 3: 运行 typecheck**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
npm run typecheck
```

期望：无类型错误。

- [ ] **Step 4: 运行前端测试**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
npm run test:run
```

期望：所有测试 PASS。

- [ ] **Step 5: Commit**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
git add src/stores/dashboard.ts
git commit -m "refactor(store): replace bundle fetch with two-phase concurrent loading"
```

---

## Task 7: 全量验证

- [ ] **Step 1: 后端全量 lint + 类型检查**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run ruff check app/
uv run mypy app/
```

期望：无错误。

- [ ] **Step 2: 后端全量测试**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run pytest tests/ -v
```

期望：所有测试 PASS。

- [ ] **Step 3: 前端全量类型检查**

```bash
cd /Users/vincentruan/geek_space/github/numina/frontend
npm run typecheck
```

期望：无类型错误。

- [ ] **Step 4: 全局残留扫描**

```bash
grep -rn "dashboard_cache\|get_dashboard_cache\|reset_dashboard_cache\|invalidate_dashboard_bundle\|getDashboardBundle\|DashboardBundleResponse\|/dashboard/bundle" \
  /Users/vincentruan/geek_space/github/numina/backend/app \
  /Users/vincentruan/geek_space/github/numina/frontend/src
```

期望输出：无任何输出。

- [ ] **Step 5: 验证子接口仍正常工作**

启动后端后，确认以下接口均返回 200：
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/dashboard/states-summary`
- `GET /api/v1/dashboard/allocation`
- `GET /api/v1/dashboard/trend`
- `GET /api/v1/dashboard/low-usage-assets`
- `GET /api/v1/dashboard/expiring-soon`

确认 bundle 接口已移除：
- `GET /api/v1/dashboard/bundle` → 期望 404

- [ ] **Step 6: Final commit（如有未提交内容）**

```bash
cd /Users/vincentruan/geek_space/github/numina
git status
```

如有未提交文件，按实际情况 add + commit。
