---
title: 儿童积分游戏化系统架构模式
date: 2026-04-17
category: best-practices
module: children-gamification
problem_type: best_practice
component: development_workflow
severity: high
related_components:
  - database
  - testing_framework
  - documentation
applies_when:
  - 构建亲子关系的游戏化功能（积分、心愿、任务）
  - 父母仪表盘需要展示多个孩子的聚合指标
  - FastAPI 项目中需要组织 Pydantic Schema
  - 编写 E2E 测试套件验证路由权限守卫
  - 编写调用 API 的 Shell 脚本（部署/种子数据）
tags:
  - n-plus-one
  - batch-endpoint
  - schema-organization
  - e2e-route-manifest
  - parent-child-dashboard
  - alembic-migration
  - fastapi
  - vue3
---

# 儿童积分游戏化系统架构模式

## Context

在为 Numina（家庭资产管理系统）构建儿童星星币游戏化功能时，代码审查暴露了七个相互关联的问题：

1. **N+1 查询性能问题**：父母仪表盘加载孩子余额时，每个孩子发一次 HTTP 请求（5 个孩子 = 5 次请求）
2. **LEFT JOIN 重复行**：`/child/treasures` 端点使用 LEFT JOIN 关联 coin_transactions，当一个心愿有多笔交易时，同一资产出现多次
3. **Schema 组织违规**：Pydantic Schema 内联定义在 Router 文件中，违反了项目约定（Schema 应在 `schemas/` 目录）
4. **迁移部署文档缺失**：没有文档说明需要在启动应用前运行 `alembic upgrade head`，导致现有数据库出现 `OperationalError: no such column`
5. **父母仪表盘缺乏粒度**：只展示家庭聚合数据，无法看到每个孩子的完成率、心愿进度
6. **E2E 路由清单不完整**：路由清单同步检查缺少 10 条子系统路由；儿童认证页面（ChildSelect、ChildPinLogin、ChildBind）是 PUBLIC 路由（不受成人认证状态影响），但清单中没有对应分类
7. **Shell 脚本响应格式脆弱**：种子脚本使用 `jq -r '.access_token'`，但 API 返回 `{data: {access_token: ...}}` 信封格式

最终结果：394 个后端测试 ✅、19 个前端单元测试 ✅、57 个 Playwright E2E 测试 ✅ 全部通过。

## Guidance

### 1. 批量端点模式（N+1 防治）

**原则**：当需要为多个父实体加载关联数据时，创建专用批量端点，用单次 GROUP BY 查询获取所有数据。

**Before（N+1 问题）**：
```typescript
// frontend/src/api/family.ts
// 5 个孩子 = 5 次 HTTP 请求
const balances = await Promise.all(
  childIds.map(id => api.get(`/child/${id}/balance`))
)
```

**After（批量端点）**：
```python
# backend/app/routers/family.py
@router.get("/children/balances")
def get_all_child_balances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChildBalanceResponse]:
    """单次 GROUP BY 查询获取所有孩子余额。"""
    rows = (
        db.query(
            User.id,
            User.display_name,
            func.coalesce(func.sum(CoinTransaction.amount), 0).label("balance"),
        )
        .outerjoin(CoinTransaction, CoinTransaction.user_id == User.id)
        .filter(User.family_id == current_user.family_id, User.role == "child")
        .group_by(User.id)
        .all()
    )
    return [ChildBalanceResponse(id=r.id, display_name=r.display_name, balance=r.balance) for r in rows]
```

```typescript
// frontend/src/api/family.ts
export async function getAllChildBalances(): Promise<ChildBalanceResponse[]> {
  const resp = await api.get<ApiResponse<ChildBalanceResponse[]>>('/family/children/balances')
  return resp.data.data
}
```

**适用场景**：仪表盘展示多个实体的聚合统计、批量操作、亲子关系数据加载。

---

### 2. LEFT JOIN 去重模式

**原则**：使用 LEFT JOIN 关联事务/事件数据时，在结果处理阶段用 `seen` 集合去重，避免数据库层面的复杂性。

**Before（重复行）**：
```python
# 一个心愿有 3 笔交易 → 同一资产出现 3 次
rows = db.query(Asset, CoinTransaction).outerjoin(
    CoinTransaction, CoinTransaction.ref_id == Asset.wish_id
).filter(Asset.user_id == child_user_id).all()
return [_to_response(asset, tx) for asset, tx in rows]  # 重复！
```

**After（应用层去重）**：
```python
rows = db.query(Asset, CoinTransaction).outerjoin(
    CoinTransaction, CoinTransaction.ref_id == Asset.wish_id
).filter(Asset.user_id == child_user_id).all()

seen: set[str] = set()
result = []
for asset, tx in rows:
    if asset.id not in seen:
        result.append(_to_response(asset, tx))
        seen.add(asset.id)
return result
```

**适用场景**：LEFT JOIN 关联多对一或多对多关系时，只需要唯一的主实体。

---

### 3. Schema 组织约定

**原则**：所有 Pydantic 请求/响应 Schema 定义在 `backend/app/schemas/` 目录，每个领域一个文件。Router 只导入，不内联定义。

**Before（内联 Schema，违规）**：
```python
# backend/app/routers/coins.py
from pydantic import BaseModel

class SiblingResponse(BaseModel):  # ❌ 不应在 router 中定义
    id: str
    display_name: str

class GiftRequest(BaseModel):      # ❌
    recipient_id: str
    amount: int
```

**After（专用 Schema 文件）**：
```python
# backend/app/schemas/coin.py  ← 新建文件
from pydantic import BaseModel, ConfigDict

class SiblingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str

class GiftRequest(BaseModel):
    recipient_id: str
    amount: int

class GiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    new_balance: int

class ChildBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str
    balance: int
```

```python
# backend/app/routers/coins.py
from app.schemas.coin import SiblingResponse, GiftRequest, GiftResponse  # ✅ 只导入
```

**适用场景**：FastAPI 项目中所有 Pydantic Schema，无例外。

---

### 4. Alembic 迁移部署文档

**原则**：在 `backend/CLAUDE.md` 中明确记录部署顺序：迁移必须在应用启动前运行。

**应添加到 `backend/CLAUDE.md` 的内容**：
```markdown
## Alembic

> **IMPORTANT — Deployment order:** Always run `uv run alembic upgrade head` **before** starting the app.
> The app calls `Base.metadata.create_all()` on startup which creates tables for fresh installs,
> but it does **not** apply Alembic migrations to existing databases. Skipping this step will cause
> `OperationalError: no such column` on any endpoint that reads newly added columns.
```

**根本原因**：`Base.metadata.create_all()` 只对全新数据库有效；对已有数据库，新增列只能通过 Alembic 迁移添加。

---

### 5. 亲子双视角仪表盘设计

**原则**：父母仪表盘应展示每个孩子的可操作指标（完成率、心愿进度），并支持每孩子操作（手动赠币）。使用批量端点高效获取数据。

**关键指标**：
- 每孩子任务完成率：`(completed_chores / total_chores) * 100`
- 每孩子心愿进度：`balance / star_coin_cost`（前端计算）
- 手动赠币入口：父母可向特定孩子赠予积分

**前端实现模式**（`frontend/src/pages/FamilyPage.vue`）：
```typescript
// 并行加载所有孩子数据
const [balances, choreStats] = await Promise.all([
  getAllChildBalances(),
  getChildrenChoreStats(),
])

// 合并为每孩子视图
const childCards = children.value.map(child => ({
  ...child,
  balance: balances.find(b => b.id === child.id)?.balance ?? 0,
  completionRate: choreStats.find(s => s.id === child.id)?.completion_rate ?? 0,
}))
```

**适用场景**：任何需要展示多个子实体聚合指标的父级仪表盘。

---

### 6. E2E 路由清单维护（PUBLIC_ROUTES 分类）

**原则**：在 `tests/lib/routes.ts` 中维护三类路由清单，并通过同步检查测试确保与 `frontend/src/router/index.ts` 保持一致。

**三类路由**：
```typescript
// tests/lib/routes.ts

/** 需要成人认证。未认证访问 → 重定向到 /login */
export const PROTECTED_ROUTES: RouteEntry[] = [
  { name: 'Dashboard', path: '/' },
  { name: 'ChildHome', path: '/child' },
  { name: 'ChildTreasures', path: '/child/treasures' },
  // ...
]

/** 仅限访客。已认证访问 → 重定向到 / */
export const GUEST_ROUTES: RouteEntry[] = [
  { name: 'Login', path: '/login' },
  { name: 'Register', path: '/register' },
]

/**
 * 公开路由 — 不受成人认证状态影响。
 * 这些是儿童专属认证页面，使用独立的 session 机制。
 * 已认证的成人用户不会被重定向离开这些路由。
 */
export const PUBLIC_ROUTES: RouteEntry[] = [
  { name: 'ChildSelect', path: '/child/select' },
  { name: 'ChildPinLogin', path: '/child/pin' },
  { name: 'ChildBind', path: '/child/bind' },
]
```

**同步检查测试**（`tests/e2e/auth-guards.spec.ts`）：
```typescript
test('routes.ts covers all route names in frontend/src/router/index.ts', () => {
  const knownNames = new Set([
    ...PROTECTED_ROUTES.map(r => r.name),
    ...GUEST_ROUTES.map(r => r.name),
    ...PUBLIC_ROUTES.map(r => r.name),  // ← PUBLIC_ROUTES 必须包含在内
  ])
  const missing = routerNames.filter(name => !knownNames.has(name))
  expect(missing).toHaveLength(0)
})
```

**关键点**：PUBLIC_ROUTES 中的路由不测试重定向行为，只需出现在同步检查的 `knownNames` 集合中，防止同步检查误报。

**适用场景**：每次向 `frontend/src/router/index.ts` 添加新路由时，必须同步更新 `tests/lib/routes.ts`。

---

### 7. Shell 脚本 API 响应信封处理

**原则**：Shell 脚本调用 API 时，使用防御性 jq 表达式同时处理直接响应和信封包装响应。

**Before（脆弱）**：
```bash
TOKEN=$(curl -s "$BASE_URL/auth/login" -d '...' | jq -r '.access_token')
# 若 API 返回 {data: {access_token: ...}} 则 TOKEN 为 null
```

**After（防御性）**：
```bash
# 同时处理直接响应和信封响应
TOKEN=$(curl -s "$BASE_URL/auth/login" -d '...' | jq -r '.access_token // .data.access_token')

# 数组响应需先检查类型
COUNT=$(curl -s "$BASE_URL/assets" -H "Authorization: Bearer $TOKEN" | \
  jq -r 'if type == "array" then length
          elif (.data | type) == "array" then .data | length
          elif (.data.total | type) == "number" then .data.total
          else 0 end' 2>/dev/null || echo "0")
```

**适用场景**：所有调用 Numina API 的 Shell 脚本（种子数据、部署脚本、CI 脚本）。

## Why This Matters

| 模式 | 不遵循的后果 |
|------|------------|
| 批量端点 | N+1 性能悬崖，5 个孩子 = 5 次请求，随孩子数量线性增长 |
| LEFT JOIN 去重 | 同一资产在宝藏页面出现多次，用户体验损坏 |
| Schema 组织 | Schema 散落在 Router 中，无法复用，难以发现 |
| 迁移文档 | 现有数据库启动后立即报 `OperationalError: no such column` |
| 亲子仪表盘 | 父母无法看到每个孩子的进度，无法精准激励 |
| 路由清单维护 | E2E 同步检查误报，或漏测新路由的权限守卫 |
| 防御性 Shell 脚本 | 种子/部署脚本静默失败，TOKEN 为 null，后续操作全部失败 |

## When to Apply

- **批量端点**：仪表盘展示多个实体的聚合数据；父子关系数据加载；任何 N+1 场景
- **LEFT JOIN 去重**：查询主实体并 JOIN 其关联事务/事件，只需唯一主实体
- **Schema 组织**：FastAPI 项目中所有 Pydantic Schema，无例外
- **迁移文档**：每次添加 Alembic 迁移后，确认 `backend/CLAUDE.md` 中有部署顺序说明
- **亲子仪表盘**：父母需要查看每个孩子的独立指标或对特定孩子执行操作
- **路由清单**：每次向 `frontend/src/router/index.ts` 添加新路由时
- **防御性 Shell 脚本**：所有调用 Numina API 的自动化脚本

## Examples

### 完整的批量端点 + 前端集成

```python
# backend/app/schemas/coin.py
class ChildBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str
    balance: int

# backend/app/routers/family.py
@router.get("/children/balances", response_model=list[ChildBalanceResponse])
def get_all_child_balances(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChildBalanceResponse]:
    rows = (
        db.query(User.id, User.display_name,
                 func.coalesce(func.sum(CoinTransaction.amount), 0).label("balance"))
        .outerjoin(CoinTransaction, CoinTransaction.user_id == User.id)
        .filter(User.family_id == current_user.family_id, User.role == "child")
        .group_by(User.id)
        .all()
    )
    return [ChildBalanceResponse(id=r.id, display_name=r.display_name, balance=r.balance)
            for r in rows]
```

```typescript
// frontend/src/api/family.ts
export interface ChildBalanceResponse {
  id: string
  display_name: string
  balance: number
}

export async function getAllChildBalances(): Promise<ChildBalanceResponse[]> {
  const resp = await api.get<ApiResponse<ChildBalanceResponse[]>>('/family/children/balances')
  return resp.data.data
}
```

### 测试覆盖

```python
# backend/tests/test_family.py
def test_get_all_child_balances_batch(client, auth_headers):
    """批量端点应在单次请求中返回所有孩子余额。"""
    # 创建 2 个孩子并赠币
    child1 = create_child(client, auth_headers, "小明")
    child2 = create_child(client, auth_headers, "小花")
    grant_coins(client, auth_headers, child1["id"], 50)
    grant_coins(client, auth_headers, child2["id"], 30)

    resp = client.get("/api/v1/family/children/balances", headers=auth_headers)
    assert resp.status_code == 200
    balances = {b["id"]: b["balance"] for b in resp.json()["data"]}
    assert balances[child1["id"]] == 50
    assert balances[child2["id"]] == 30
```

## Related

- `backend/app/routers/family.py` — 批量端点实现（`GET /family/children/balances`, `GET /family/children/chore-stats`）
- `backend/app/schemas/coin.py` — 积分相关 Schema 定义
- `backend/app/routers/treasures.py` — LEFT JOIN 去重实现
- `tests/lib/routes.ts` — 路由清单（含 PUBLIC_ROUTES）
- `tests/e2e/auth-guards.spec.ts` — 路由同步检查测试
- `tests/seed-accounts.sh` — 防御性 jq 表达式示例
- `docs/ideation/2026-04-14-children-starcoin-ideation.md` — 儿童积分系统设计原始构想
- `docs/plans/2026-04-15-001-feat-core-earn-loop-plan.md` — 核心赚取循环实现计划
